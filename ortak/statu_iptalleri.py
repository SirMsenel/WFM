"""Operasyonel statü iptali: rol, gerekçe, geçmişi koruma ve tek işlemde denetim."""
from uuid import uuid4
import pandas as pd
from ortak.calisma_alani_deposu import connect,loads,dumps
from ortak.statu_kapasite_raporu import capacity_visible
from ortak.roller_ve_yetkiler import init_governance,append_audit
from ortak.mola_servisi import init as init_breaks


def now_local():return pd.Timestamp.now(tz='Europe/Istanbul').tz_localize(None)

def init(path):
    init_breaks(path);init_governance(path)
    with connect(path) as db:db.execute('CREATE TABLE IF NOT EXISTS status_cancellations(id TEXT PRIMARY KEY,target_id TEXT NOT NULL,payload TEXT NOT NULL)')

def _require(state):
    if not capacity_visible(state.get('profile',{})):raise ValueError('Statü iptalini yalnızca Planlama ve yönetim yapabilir.')

def _targets(db):
    result=[]
    for r in db.execute('SELECT * FROM planned_breaks'):
        p=loads(r['payload']);result.append(dict(p,id='status:'+r['id'],record_id=r['id'],publication_id=r['publication_id'],source='planned_breaks',status=p.get('status','Planlı')))
    for r in db.execute('SELECT * FROM break_requests'):
        p=loads(r['payload']);result.append(dict(p,id='request:'+r['id'],record_id=r['id'],source='break_requests',status=r['status']))
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='coaching_openings'").fetchone():
        for r in db.execute("SELECT * FROM coaching_openings WHERE status='Açık'"):
            p=loads(r['payload']);result.append(dict(p,id='pool:'+r['id'],record_id=r['id'],publication_id=r['publication_id'],source='coaching_openings',status=r['status']))
    return result

def targets(state):
    _require(state);init(state['workspace_db_path'])
    with connect(state['workspace_db_path']) as db:return _targets(db)

def events(state,db=None):
    if db is None:
        _require(state);init(state['workspace_db_path'])
        with connect(state['workspace_db_path']) as c:return [dict(loads(r['payload']),id=r['id']) for r in c.execute('SELECT * FROM status_cancellations ORDER BY rowid DESC')]
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='status_cancellations'").fetchone():return []
    return [dict(loads(r['payload']),id=r['id']) for r in db.execute('SELECT * FROM status_cancellations')]

def blocks(db,eid,start,end):
    a,b=pd.Timestamp(start),pd.Timestamp(end)
    return any(str(r.get('employee_id'))==str(eid) and r.get('source')!='coaching_openings' and a<pd.Timestamp(r['end']) and pd.Timestamp(r['start'])<b for r in events({},db))

def cancel_targets(state,identifiers,reason,expected=None):
    _require(state)
    if not reason or not reason.strip():raise ValueError('Operasyonel iptal gerekçesi zorunlu.')
    if not identifiers or len(identifiers)!=len(set(identifiers)):raise ValueError('İptal edilecek farklı statüleri seçin.')
    from ortak.personel_deposu import list_people
    people={str(p['employee_id']):p for p in list_people(state,True)};path=state['workspace_db_path'];init(path);now=now_local();batch='SC-'+uuid4().hex[:12];output=[]
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE');lookup={r['id']:r for r in _targets(db)}
        for ident in identifiers:
            current=lookup.get(ident)
            if current is None or current.get('status') not in {'Planlı','Onaylı','Açık'}:raise ValueError('Seçilen statü değişmiş veya zaten iptal edilmiş. Listeyi yenileyin.')
            if expected is not None and dumps(expected.get(ident))!=dumps(current):raise ValueError('Statü başka oturumda değişti; listeyi yenileyin.')
            a,b=pd.Timestamp(current['start']),pd.Timestamp(current['end'])
            if b<=now:raise ValueError('Tamamlanmış veya geçmiş statü iptal edilemez.')
            left=max(a,now);person=people.get(str(current['employee_id']),{});event={'batch':batch,'target_id':ident,'employee_id':str(current['employee_id']),'name':person.get('full_name',current['employee_id']),'team_lead':person.get('team_lead'),'kind':current['kind'],'start':str(left),'end':str(b),'reason':reason.strip(),'actor':state['profile']['username'],'actor_name':state['profile'].get('full_name',state['profile']['username']),'created_at':str(now),'before':current,'source':current['source'],'publication_id':current.get('publication_id')};record_id=current['record_id'];event_id=batch+'-'+str(len(output))
            if current['source']=='coaching_openings':
                raw=db.execute('SELECT payload FROM coaching_openings WHERE id=?',(record_id,)).fetchone();p=loads(raw[0]);count=int(p.get('remaining_capacity',1))
                if count<=0:raise ValueError('Açık koçluk kontenjanı kalmadı.')
                p.update(remaining_capacity=0,cancelled_capacity=int(p.get('cancelled_capacity',0))+count,operation_cancelled=True,cancellation_id=event_id);event['cancelled_capacity']=count
                db.execute("UPDATE coaching_openings SET status='İptal',payload=? WHERE id=?",(dumps(p),record_id))
            else:
                table=current['source'];raw=db.execute('SELECT payload FROM '+table+' WHERE id=?',(record_id,)).fetchone();p=loads(raw[0]);canceled=dict(p,start=str(left),status='İptal',cancelled_at=str(now),cancelled_by=state['profile']['username'],cancellation_id=event_id)
                if a<now:
                    kept=dict(p,end=str(now),status=p.get('status','Planlı'));db.execute('UPDATE '+table+' SET payload=? WHERE id=?',(dumps(kept),record_id));cancel_id=event_id+'-part'
                    if table=='planned_breaks':db.execute('INSERT INTO planned_breaks VALUES(?,?,?)',(cancel_id,current.get('publication_id'),dumps(canceled)))
                    else:db.execute('INSERT INTO break_requests VALUES(?,?,?,?)',(cancel_id,str(current['employee_id']),'İptal',dumps(canceled)))
                else:
                    db.execute('UPDATE '+table+' SET payload=? WHERE id=?',(dumps(canceled),record_id))
                    if table=='break_requests':db.execute("UPDATE break_requests SET status='İptal' WHERE id=?",(record_id,))
                if current['kind']=='Koçluk':
                    if db.execute("SELECT 1 FROM sqlite_master WHERE name='manager_agenda'").fetchone():
                        if a<now:db.execute("UPDATE manager_agenda SET end=? WHERE id=? AND kind='Koçluk'",(str(now),record_id))
                        else:db.execute("DELETE FROM manager_agenda WHERE id=? AND kind='Koçluk'",(record_id,))
                    if p.get('opening_id') and db.execute("SELECT 1 FROM sqlite_master WHERE name='coaching_openings'").fetchone():
                        old=db.execute('SELECT payload,status FROM coaching_openings WHERE id=?',(p['opening_id'],)).fetchone()
                        if old:
                            opening=loads(old['payload']);opening['cancelled_capacity']=int(opening.get('cancelled_capacity',0))+1;opening['operation_cancelled']=True;db.execute('UPDATE coaching_openings SET payload=?,status=? WHERE id=?',(dumps(opening),old['status'] if int(opening.get('remaining_capacity',0)) else 'İptal',p['opening_id']))
                if db.execute("SELECT 1 FROM sqlite_master WHERE name='status_swap_requests'").fetchone():
                    for req in db.execute("SELECT * FROM status_swap_requests WHERE status IN ('Karşı personel onayı','Takım Lideri onayı')").fetchall():
                        data=loads(req['payload'])
                        if any(r['id']==record_id for r in data.get('before',[])):data.update(updated_at=str(now),cancel_reason=reason);db.execute("UPDATE status_swap_requests SET status='İptal',version=version+1,payload=? WHERE id=?",(dumps(data),req['id']))
            event['cancelled_minutes']=(b-left).total_seconds()/60*(int(event.get('cancelled_capacity',1)) if current['source']=='coaching_openings' else 1);db.execute('INSERT INTO status_cancellations VALUES(?,?,?)',(event_id,ident,dumps(event)));output.append(event)
        append_audit(db,'Operasyonel statü iptali',state['profile'],{'batch':batch,'reason':reason.strip(),'events':output})
    state.pop('_status_plan_cache',None)
    return output

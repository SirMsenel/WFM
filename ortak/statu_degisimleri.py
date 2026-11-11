"""Yemek/mola değişimi: eş personel rızası, lider onayı ve atomik yeniden kontrol."""
from uuid import uuid4
from copy import deepcopy
import pandas as pd
from ortak.calisma_alani_deposu import connect,loads,dumps
from ortak.personel import get_people
from ortak.roller_ve_yetkiler import init_governance,append_audit
from ortak.talep_servisi import now
from ortak.mola_servisi import init as init_breaks,records
from ortak.sabit_demo import history_rows
from modules.vardiya_plani.vardiya_motoru import bounds

def init(path):
    init_breaks(path);init_governance(path)
    with connect(path) as db:db.execute('CREATE TABLE IF NOT EXISTS status_swap_requests(id TEXT PRIMARY KEY,status TEXT NOT NULL,version INTEGER NOT NULL,payload TEXT NOT NULL)')


def validate(state,a,b,people,existing):
    if a['kind'] not in {'Yemek','Mola'} or a['kind']!=b['kind']:raise ValueError('Aynı statü türünü seçin: yemek ↔ yemek veya mola ↔ mola.')
    if str(a['employee_id'])==str(b['employee_id']):raise ValueError('Farklı bir personel seçin.')
    if a['start'][:10]!=b['start'][:10]:raise ValueError('Aynı gün içindeki statüler değiştirilebilir.')
    pa,pb=people[str(a['employee_id'])],people[str(b['employee_id'])]
    if (pa['work_type'],pa.get('language','tr'),pa.get('team_lead'))!=(pb['work_type'],pb.get('language','tr'),pb.get('team_lead')):raise ValueError('Aynı grup, dil ve ekip içinden uygun personel seçin.')
    durations=[(pd.Timestamp(r['end'])-pd.Timestamp(r['start'])).total_seconds() for r in (a,b)]
    if durations[0]!=durations[1]:raise ValueError('Değiştirilecek süreler eşit olmalı.')
    if min(pd.Timestamp(a['start']),pd.Timestamp(b['start']))<pd.Timestamp.now(tz='Europe/Istanbul').tz_localize(None):raise ValueError('Başlamış veya geçmiş statü değiştirilemez.')
    changed=[dict(a,start=b['start'],end=b['end']),dict(b,start=a['start'],end=a['end'])];roster=history_rows(state,a['start'][:10],a['start'][:10]);ids={a['id'],b['id']}
    for r in changed:
        eid=str(r['employee_id']);start,end=pd.Timestamp(r['start']),pd.Timestamp(r['end']);own=next((x for x in roster if str(x['employee_id'])==eid and (span:=bounds(x)) and pd.Timestamp(span[0])<=start and end<=pd.Timestamp(span[1])),None)
        if own is None:raise ValueError('Yeni saat personelin yayınlanmış vardiyasına sığmıyor.')
        if r['kind']=='Mola':
            rule=state.get('status_rules',{}).get('groups',{}).get(people[eid]['work_type'],{});span=bounds(own)
            if start<pd.Timestamp(span[0])+pd.Timedelta(minutes=rule.get('break_first_minutes',60)) or end>pd.Timestamp(span[1])-pd.Timedelta(minutes=rule.get('break_last_minutes',60)):raise ValueError('Vardiyanın ilk/son saat mola kuralına uymuyor.')
        if r['kind']=='Mola':
            rules=state.get('status_rules',{}).get('groups',{}).get(people[eid]['work_type'],{});limit=float(rules.get('break_per_hour_max',15))
            for hour in pd.date_range(start.floor('h'),(end-pd.Timedelta(seconds=1)).floor('h'),freq='h'):
                right=hour+pd.Timedelta(hours=1);total=max(0,(min(end,right)-max(start,hour)).total_seconds()/60)
                total+=sum(max(0,(min(pd.Timestamp(x['end']),right)-max(pd.Timestamp(x['start']),hour)).total_seconds()/60) for x in existing if x['id'] not in ids and str(x['employee_id'])==eid and x['kind']=='Mola' and x.get('status')!='İptal')
                if total>limit:raise ValueError('Yeni saatte saatlik mola kullanım sınırı aşılır.')
        if any(x['id'] not in ids and str(x['employee_id'])==eid and x.get('status')!='İptal' and start<pd.Timestamp(x['end']) and pd.Timestamp(x['start'])<end for x in existing):raise ValueError('Yeni statü saati başka statüyle çakışıyor.')
    return changed


def candidates(state,own_id):
    init(state['workspace_db_path']);all_rows=records(state);own=next((r for r in all_rows if r['id']==own_id),None)
    if own is None:return []
    with connect(state['workspace_db_path']) as db:published_ids={r[0] for r in db.execute('SELECT id FROM planned_breaks')}
    people={str(p['employee_id']):p for p in get_people(state)};valid=[]
    for other in all_rows:
        if other['id']==own_id or other['id'] not in published_ids:continue
        try:validate(state,own,other,people,all_rows);valid.append(other)
        except (ValueError,KeyError):pass
    return valid


def submit(state,own_id,other_id,reason):
    p=state['profile']
    if p.get('position')!='agent' or not reason.strip():raise ValueError('Personel kendi hesabından gerekçeyle değişim ister.')
    init(state['workspace_db_path']);all_rows=records(state);a=next((x for x in all_rows if x['id']==own_id),None);b=next((x for x in all_rows if x['id']==other_id),None)
    if a is None or b is None or str(a['employee_id'])!=str(p['employee_id']):raise ValueError('Kendi planlanmış statünü seçin.')
    # Only publication-backed statuses can be swapped; manual break reservations remain personal.
    with connect(state['workspace_db_path']) as db:
        if db.execute('SELECT COUNT(*) FROM planned_breaks WHERE id IN (?,?)',(own_id,other_id)).fetchone()[0]!=2:raise ValueError('İki yayınlanmış statü kaydı seçin.')
    people={str(x['employee_id']):x for x in get_people(state)};validate(state,a,b,people,all_rows);ident='SS-'+uuid4().hex[:12];payload={'id':ident,'before':[a,b],'reason':reason,'owner':p['username'],'peer':people[str(b['employee_id'])]['username'],'team_lead':p.get('team_lead'),'created_at':now()}
    with connect(state['workspace_db_path']) as db:db.execute('INSERT INTO status_swap_requests VALUES(?,?,?,?)',(ident,'Karşı personel onayı',1,dumps(payload)));append_audit(db,'Statü değişimi istendi',p,payload)
    return ident


def requests(state):
    init(state['workspace_db_path']);p=state['profile']
    with connect(state['workspace_db_path']) as db:rows=[dict(loads(x['payload']),status=x['status'],version=x['version']) for x in db.execute('SELECT * FROM status_swap_requests ORDER BY rowid DESC')]
    return [r for r in rows if p['username'] in {r['owner'],r['peer']} or p.get('position') in {'wfm','planning_manager','moderator'} or (p.get('position')=='tl' and p.get('full_name')==r['team_lead'])]


def decide(state,item,approve):
    path=state['workspace_db_path'];init(path);p=state['profile'];people={str(x['employee_id']):x for x in get_people(state)}
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE');saved=db.execute('SELECT * FROM status_swap_requests WHERE id=?',(item['id'],)).fetchone()
        if not saved or saved['version']!=item['version']:raise ValueError('Talep başka oturumda değişti; yenileyin.')
        req=loads(saved['payload']);status=saved['status']
        if status=='Karşı personel onayı':
            if p['username']!=req['peer']:raise ValueError('Önce karşı personelin onayı gerekli.')
            target='Takım Lideri onayı' if approve else 'Reddedildi'
        elif status=='Takım Lideri onayı':
            if not (p.get('position') in {'wfm','planning_manager','moderator'} or (p.get('position')=='tl' and p.get('full_name')==req['team_lead'])):raise ValueError('İlgili takım liderinin onayı gerekli.')
            target='Uygulandı' if approve else 'Reddedildi'
            if approve:
                existing=records(state,db);lookup={x['id']:x for x in existing};old=req['before']
                if any(lookup.get(r['id'])!=r for r in old):raise ValueError('Statü kayıtları değişmiş; yeni talep oluşturun.')
                check=dict(state);raw=db.execute("SELECT payload FROM work_state WHERE key='published_shift_plan'").fetchone()
                if raw:check['published_shift_plan']=loads(raw[0])
                changed=validate(check,*old,people,existing)
                for r in changed:
                    payload={k:v for k,v in r.items() if k!='id'};db.execute('UPDATE planned_breaks SET payload=? WHERE id=?',(dumps(payload),r['id']))
        else:raise ValueError('Talep sonuçlanmış.')
        req['updated_at']=now();db.execute('UPDATE status_swap_requests SET status=?,version=version+1,payload=? WHERE id=?',(target,dumps(req),req['id']));append_audit(db,'Statü değişim kararı',p,{'id':req['id'],'status':target,'before':req['before']})
    return target

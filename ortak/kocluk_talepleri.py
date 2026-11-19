"""Müşteri temsilcisinin uygun koçluk dilimi için TL'ye ilettiği talepler."""
from uuid import uuid4
import pandas as pd

from ortak.calisma_alani_deposu import connect,dumps,loads,init_db
from ortak.talep_servisi import now
from ortak.kocluk_alanlari import read,accepts


def init(path):
    init_db(path)
    with connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS coaching_requests(id TEXT PRIMARY KEY,status TEXT NOT NULL,payload TEXT NOT NULL)')


def _person(state,eid):
    from ortak.personel import get_people
    return next((p for p in get_people(state) if str(p['employee_id'])==str(eid)),None)


def eligible_slots(state,eid):
    """Slots are shown to the representative without exposing seat capacity."""
    from ortak.mola_servisi import records
    eid=str(eid);person=_person(state,eid)
    if not person:return []
    upcoming=[];busy=records(state)
    from ortak.demo_zamani import now as active_now
    current=pd.Timestamp(active_now(state))
    from ortak.personel import get_people
    leader=next((p for p in get_people(state) if p.get('position')=='tl' and p.get('full_name')==person.get('team_lead')),None)
    if not leader:return []
    from ortak.ajanda_servisi import init as init_agenda
    init_agenda(state['workspace_db_path'])
    with connect(state['workspace_db_path']) as db:
        agenda=[dict(row) for row in db.execute('SELECT start,end,kind FROM manager_agenda WHERE owner=?',(leader['username'],))]
    rule=state.get('status_rules',{}).get('groups',{}).get(person.get('work_type'),{})
    for opening in read(state):
        a,b=pd.Timestamp(opening['start']),pd.Timestamp(opening['end'])
        if a<current or b-a!=pd.Timedelta(minutes=15) or not accepts(opening,eid):continue
        if not any(row['kind']=='Çalışma' and pd.Timestamp(row['start'])<=a and b<=pd.Timestamp(row['end']) for row in agenda):continue
        if any(row['kind']=='Koçluk' and a<pd.Timestamp(row['end']) and pd.Timestamp(row['start'])<b for row in agenda):continue
        if any(str(item.get('employee_id'))==eid and item.get('status')!='İptal' and a<pd.Timestamp(item['end']) and pd.Timestamp(item['start'])<b for item in busy):continue
        month_used=sum((pd.Timestamp(item['end'])-pd.Timestamp(item['start'])).total_seconds()/60 for item in busy if str(item.get('employee_id'))==eid and item.get('kind')=='Koçluk' and item.get('status')!='İptal' and item.get('start','')[:7]==str(a)[:7])
        if month_used+15>int(rule.get('coaching_monthly_minutes',60)):continue
        week=a.normalize()-pd.Timedelta(days=a.weekday())
        if not rule.get('coaching_multiple_per_week',False) and any(str(item.get('employee_id'))==eid and item.get('kind')=='Koçluk' and item.get('status')!='İptal' and week<=pd.Timestamp(item['start'])<week+pd.Timedelta(days=7) for item in busy):continue
        upcoming.append(opening)
    return sorted(upcoming,key=lambda item:item['start'])


def submit(state,opening_id):
    profile=state.get('profile') or {};eid=str(profile.get('employee_id',''))
    if profile.get('position')!='agent' or not eid:raise ValueError('Koçluk talebini yalnızca kendi hesabınla iletebilirsin.')
    opening=next((row for row in eligible_slots(state,eid) if row.get('id')==opening_id),None)
    if not opening:raise ValueError('Bu koçluk saati artık uygun değil; listeyi yenileyin.')
    path=state['workspace_db_path'];init(path);person=_person(state,eid);ident='CRQ-'+uuid4().hex[:12]
    payload={'id':ident,'employee_id':eid,'employee_name':person.get('full_name',eid),'team_lead':person.get('team_lead'),
             'opening_id':opening_id,'start':opening['start'],'end':opening['end'],'created_at':now()}
    with connect(path) as db:
        duplicate=db.execute("SELECT payload FROM coaching_requests WHERE status='Bekliyor'").fetchall()
        if any(str(loads(row[0]).get('employee_id'))==eid and loads(row[0]).get('opening_id')==opening_id for row in duplicate):
            raise ValueError('Bu saat için zaten bekleyen bir talebin var.')
        db.execute('INSERT INTO coaching_requests VALUES(?,?,?)',(ident,'Bekliyor',dumps(payload)))
    return ident


def pending(state,team_only=True):
    path=state.get('workspace_db_path')
    if not path:return []
    init(path)
    with connect(path) as db:
        items=[dict(loads(row['payload']),status=row['status']) for row in db.execute("SELECT * FROM coaching_requests WHERE status='Bekliyor' ORDER BY rowid")]
    profile=state.get('profile') or {}
    if not team_only:return items
    if profile.get('position')=='agent':return [item for item in items if str(item['employee_id'])==str(profile.get('employee_id'))]
    from ortak.personel import get_people,visible_people
    visible={str(person['employee_id']) for person in visible_people(profile,get_people(state))}
    return [item for item in items if str(item['employee_id']) in visible]


def decide(state,ident,approve=True,reason=''):
    profile=state.get('profile') or {}
    if profile.get('position') not in {'tl','manager','assistant_manager','wfm','planning_manager','moderator'}:
        raise ValueError('Koçluk talebini yalnızca yönetim rolleri değerlendirebilir.')
    path=state['workspace_db_path'];init(path)
    with connect(path) as db:
        row=db.execute('SELECT * FROM coaching_requests WHERE id=?',(ident,)).fetchone()
        if not row or row['status']!='Bekliyor':raise ValueError('Talep artık beklemiyor.')
        item=loads(row['payload'])
        from ortak.personel import get_people,visible_people
        if str(item['employee_id']) not in {str(p['employee_id']) for p in visible_people(profile,get_people(state))}:
            raise ValueError('Bu personel yetki kapsamınızda değil.')
        if not approve:
            if not reason.strip():raise ValueError('Ret gerekçesi gerekli.')
            item.update(decided_at=now(),decided_by=profile.get('username'),reason=reason)
            db.execute('UPDATE coaching_requests SET status=?,payload=? WHERE id=?',('Reddedildi',dumps(item),ident));return False
    # add_coaching opens its own transaction and validates agenda, employee shift,
    # opening capacity and weekly/monthly group rules at the final decision time.
    from ortak.ajanda_servisi import add_coaching
    add_coaching(state,item['employee_id'],pd.Timestamp(item['start']),15,opening_id=item['opening_id'])
    with connect(path) as db:
        item.update(decided_at=now(),decided_by=profile.get('username'))
        db.execute('UPDATE coaching_requests SET status=?,payload=? WHERE id=?',('Onaylandı',dumps(item),ident))
    return True

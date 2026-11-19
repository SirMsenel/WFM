"""Planlamada kapasitesi ayrılan, liderin personele atayacağı koçluk aralıkları."""
import pandas as pd
from ortak.calisma_alani_deposu import connect,loads,init_db

def init(path):
    init_db(path)
    with connect(path) as db:db.execute("CREATE TABLE IF NOT EXISTS coaching_openings(id TEXT PRIMARY KEY,publication_id TEXT NOT NULL,employee_id TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL)")

def read(state,db=None):
    path=state.get('workspace_db_path')
    if not path:return []
    def query(c):
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='coaching_openings'").fetchone():return []
        return [dict(loads(r['payload']),id=r['id'],publication_id=r['publication_id']) for r in c.execute("SELECT * FROM coaching_openings WHERE status='Açık'")]
    if db is not None:return query(db)
    init(path)
    with connect(path) as c:return query(c)

def accepts(opening,eid):
    return str(eid) in set(map(str,opening.get('eligible_employee_ids',[]))) if opening.get('pool') else str(opening['employee_id'])==str(eid)


def eligible(state,eid):
    from ortak.ajanda_servisi import rows
    from ortak.personel import get_people,visible_people
    from ortak.mola_servisi import records
    eid=str(eid);person=next((p for p in visible_people(state['profile'],get_people(state)) if str(p['employee_id'])==eid),None)
    if person is None:return []
    work=rows(state)
    from ortak.statu_iptalleri import events
    with connect(state['workspace_db_path']) as db:cancellations=events(state,db)
    now=pd.Timestamp.now(tz='Europe/Istanbul').tz_localize(None);planned=records(state);meetings=[w for w in work if w['kind']=='Koçluk'];result=[]
    target=int(state.get('status_rules',{}).get('groups',{}).get(person.get('work_type'),{}).get('coaching_monthly_minutes',60))
    for r in read(state):
        a,b=pd.Timestamp(r['start']),pd.Timestamp(r['end'])
        if not accepts(r,eid) or a<now:continue
        if state['profile'].get('position')=='tl' and b-a!=pd.Timedelta(minutes=15):continue
        if any(str(x.get('employee_id'))==eid and x.get('source')!='coaching_openings' and a<pd.Timestamp(x['end']) and pd.Timestamp(x['start'])<b for x in cancellations):continue
        if not any(w['kind']=='Çalışma' and pd.Timestamp(w['start'])<=a and b<=pd.Timestamp(w['end']) for w in work):continue
        if any((str(w['employee_id'])==eid or w.get('owner')==state['profile']['username']) and a<pd.Timestamp(w['end']) and pd.Timestamp(w['start'])<b for w in meetings):continue
        if any(str(w['employee_id'])==eid and w.get('status')!='İptal' and a<pd.Timestamp(w['end']) and pd.Timestamp(w['start'])<b for w in planned):continue
        used=sum((pd.Timestamp(w['end'])-pd.Timestamp(w['start'])).total_seconds()/60 for w in planned if w.get('status')!='İptal' and str(w['employee_id'])==eid and w['kind']=='Koçluk' and w['start'][:7]==str(a)[:7])
        rule=state.get('status_rules',{}).get('groups',{}).get(person.get('work_type'),{});week=a.normalize()-pd.Timedelta(days=a.weekday())
        if not rule.get('coaching_multiple_per_week',False) and any(str(w['employee_id'])==eid and w['kind']=='Koçluk' and week<=pd.Timestamp(w['start'])<week+pd.Timedelta(days=7) for w in planned):continue
        if used+(b-a).total_seconds()/60<=target:result.append(r)
    return result

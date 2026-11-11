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

def eligible(state,eid):
    from ortak.ajanda_servisi import rows
    work=rows(state);now=pd.Timestamp.now(tz='Europe/Istanbul').tz_localize(None)
    return [r for r in read(state) if str(r['employee_id'])==str(eid) and pd.Timestamp(r['start'])>=now and any(w['kind']=='Çalışma' and pd.Timestamp(w['start'])<=pd.Timestamp(r['start']) and pd.Timestamp(r['end'])<=pd.Timestamp(w['end']) for w in work)]

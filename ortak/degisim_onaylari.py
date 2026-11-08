"""Değişim Onayları — hücre düzenlemesi önce önerilir, yalnızca Planlama uygular."""
from uuid import uuid4
from copy import deepcopy
from ortak.calisma_alani_deposu import connect,dumps,loads
from ortak.roller_ve_yetkiler import init_governance,append_audit,require
from ortak.vardiya_degisimleri import validate_changes,apply_changes
from ortak.talep_servisi import now


def init_changes(path):
    init_governance(path)
    with connect(path) as db:db.execute('CREATE TABLE IF NOT EXISTS shift_change_requests(id TEXT PRIMARY KEY,version INTEGER NOT NULL,payload TEXT NOT NULL)')


def change_requests(state):
    init_changes(state['workspace_db_path'])
    with connect(state['workspace_db_path']) as db:return [{**loads(r['payload']),'version':r['version']} for r in db.execute('SELECT * FROM shift_change_requests ORDER BY rowid DESC')]


def submit_change(state,changes,kind,reason):
    require(state,'vardiya_degistir');path=state['workspace_db_path'];init_changes(path)
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE');stored=db.execute("SELECT payload FROM work_state WHERE key='published_shift_plan'").fetchone();current=loads(stored[0]) if stored else state.get('published_shift_plan',[])
        before,after=validate_changes(state,changes,kind,reason,current)
        item={'id':'EDIT-'+uuid4().hex[:12],'kind':kind,'reason':reason.strip(),'before':deepcopy(before),'changes':deepcopy(changes),'requester':deepcopy(state['profile']),'created_at':now(),'status':'Planlama onayı'}
        db.execute('INSERT INTO shift_change_requests VALUES(?,?,?)',(item['id'],1,dumps(item)));append_audit(db,'Vardiya değişim önerisi',state['profile'],item)
    return dict(item,version=1)


def decide_change(state,item,approve,note=''):
    if state['profile'].get('position')!='wfm':raise ValueError('Son onayı yalnızca Planlama verir.')
    path=state['workspace_db_path'];init_changes(path)
    if approve:
        apply_changes(state,item['changes'],item['kind'],item['reason'],proposal_update=(item,item['version']))
        return
    if not note.strip():raise ValueError('Ret gerekçesi gerekli.')
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT * FROM shift_change_requests WHERE id=?',(item['id'],)).fetchone()
        if not row or row['version']!=item['version']:raise ValueError('Talep başka bir oturumda değişti.')
        actual=loads(row['payload'])
        if actual['status']!='Planlama onayı':raise ValueError('Talep sonuçlanmış.')
        updated={**actual,'status':'Reddedildi','decision_note':note.strip(),'decided_by':state['profile'].get('username'),'decided_at':now()}
        db.execute('UPDATE shift_change_requests SET version=version+1,payload=? WHERE id=?',(dumps(updated),item['id']));append_audit(db,'Vardiya değişim kararı',state['profile'],updated)

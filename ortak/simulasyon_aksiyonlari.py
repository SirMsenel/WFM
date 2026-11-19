"""Simülasyondan doğan aksiyonların yönetim onay akışı."""
from datetime import datetime
from zoneinfo import ZoneInfo

from ortak.calisma_alani_deposu import connect,dumps,loads,init_db

APPROVAL_ROLES={'wfm','planning_manager','manager','assistant_manager','moderator'}


def init(path):
    init_db(path)
    with connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS simulation_actions(id INTEGER PRIMARY KEY,payload TEXT NOT NULL)')


def list_actions(state):
    path=state.get('workspace_db_path')
    if not path:return []
    init(path)
    with connect(path) as db:return [dict(loads(row['payload']),id=row['id']) for row in db.execute('SELECT id,payload FROM simulation_actions ORDER BY id DESC')]


def submit(state,month,kind,reason,scenario):
    profile=state.get('profile') or {}
    if profile.get('position') not in APPROVAL_ROLES or not str(reason).strip():raise ValueError('Aksiyon talebi için yetkili kullanıcı ve gerekçe gerekli.')
    payload={'month':str(month),'kind':str(kind),'reason':str(reason).strip(),'actor':profile.get('username'),'actor_name':profile.get('full_name',profile.get('username')),
             'status':'Onay bekliyor','created_at':datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(),'scenario':scenario}
    init(state['workspace_db_path'])
    with connect(state['workspace_db_path']) as db:
        ident=db.execute('INSERT INTO simulation_actions(payload) VALUES(?)',(dumps(payload),)).lastrowid
    return ident


def decide(state,ident,approve,note=''):
    profile=state.get('profile') or {}
    if profile.get('position') not in APPROVAL_ROLES:raise ValueError('Bu aksiyonu yönetim veya planlama onaylayabilir.')
    if not approve and not str(note).strip():raise ValueError('Ret gerekçesi gerekli.')
    path=state['workspace_db_path'];init(path)
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT payload FROM simulation_actions WHERE id=?',(ident,)).fetchone()
        if not row:raise ValueError('Aksiyon kaydı bulunamadı.')
        item=loads(row['payload'])
        if item.get('status')!='Onay bekliyor':raise ValueError('Aksiyon daha önce sonuçlandırılmış.')
        if item.get('actor')==profile.get('username') and profile.get('position')!='moderator':raise ValueError('Talebi oluşturan kullanıcı kendi aksiyonunu onaylayamaz.')
        item.update(status='Onaylandı' if approve else 'Reddedildi',decision_note=str(note).strip(),decided_by=profile.get('username'),decided_by_name=profile.get('full_name'),decided_at=datetime.now(ZoneInfo('Europe/Istanbul')).isoformat())
        db.execute('UPDATE simulation_actions SET payload=? WHERE id=?',(dumps(item),ident))
    return item['status']

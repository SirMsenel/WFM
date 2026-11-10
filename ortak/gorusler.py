"""Uygulama görüşleri: anonim şikâyetlerde gönderici alıcı ekranında saklanmaz."""
import hashlib,hmac,secrets
from uuid import uuid4
from ortak.calisma_alani_deposu import connect,dumps,loads,init_db


def init(path):
    init_db(path)
    with connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS feedback(id TEXT PRIMARY KEY,owner TEXT NOT NULL,payload TEXT NOT NULL)')
        db.execute("INSERT OR IGNORE INTO metadata VALUES('feedback_key',?)",(secrets.token_hex(32),))


def owner(db,username):return hmac.new(db.execute("SELECT value FROM metadata WHERE key='feedback_key'").fetchone()[0].encode(),username.encode(),hashlib.sha256).hexdigest()


def submit(state,kind,message,anonymous=False):
    if kind not in {'Bilgi','Öneri','Talep','Şikâyet'} or not message.strip():raise ValueError('Tür ve içerik gerekli.')
    from ortak.talep_servisi import now
    path=state['workspace_db_path'];init(path);profile=state['profile'];anonymous=bool(anonymous and kind=='Şikâyet');ident='FB-'+uuid4().hex[:12]
    payload={'type':kind,'message':message.strip(),'sender':None if anonymous else profile.get('full_name',profile['username']),'anonymous':anonymous,'status':'Yeni','created_at':now(),'reply':''}
    with connect(path) as db:db.execute('INSERT INTO feedback VALUES(?,?,?)',(ident,owner(db,profile['username']),dumps(payload)))
    return ident


def records(state):
    path=state['workspace_db_path'];init(path);admin=state['profile'].get('position') in {'wfm','planning_manager','moderator'}
    with connect(path) as db:
        own=owner(db,state['profile']['username']);return [dict(loads(r['payload']),id=r['id']) for r in db.execute('SELECT * FROM feedback') if admin or r['owner']==own]

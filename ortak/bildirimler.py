"""Kullanıcının yetki kapsamındaki uygulama bildirimleri ve okundu kaydı."""
import hashlib
from ortak.calisma_alani_deposu import connect,loads,init_db


def init(path):
    init_db(path)
    with connect(path) as db:db.execute('CREATE TABLE IF NOT EXISTS notification_reads(username TEXT NOT NULL,id TEXT NOT NULL,PRIMARY KEY(username,id))')


def items(state):
    profile=state.get('profile') or {};username=profile.get('username');path=state.get('workspace_db_path')
    if not username or not path:return []
    init(path);role=profile.get('position');eid=str(profile.get('employee_id'));output=[]
    def add(ident,title,content,when,category):output.append({'id':ident,'Başlık':title,'İçerik':content,'Tarih':when,'Konu':category})
    with connect(path) as db:
        read={r[0] for r in db.execute('SELECT id FROM notification_reads WHERE username=?',(username,))}
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'requests' in tables:
            from ortak.talep_servisi import visible
            for row in db.execute('SELECT payload FROM requests'):
                req=loads(row[0])
                if not visible(req,profile):continue
                event=(req.get('events') or [{}])[-1];add('REQ-'+req['id']+'-'+str(req.get('version',1)),req.get('type','Talep')+' · '+req.get('status',''),(req.get('created_by_name') or req.get('created_by',''))+' · '+str(event.get('action') or req.get('note') or ''),event.get('at') or req.get('created_at',''),'Talep')
        if role in {'wfm','planning_manager','moderator'} and 'plan_approvals' in tables:
            for row in db.execute('SELECT status,payload FROM plan_approvals ORDER BY rowid DESC LIMIT 80'):
                p=loads(row['payload']);count=len(p.get('votes',[]));manager=bool(p.get('manager'));period=p['result']['period'];add('APR-'+p['id']+'-'+str(count)+'-'+str(manager)+'-'+row['status'],'Plan yayını · '+row['status'],f"{period['start']} – {period['end']} · Planlama onayı {count}/2 · Yönetici {'onayladı' if manager else 'bekleniyor' if p['rate']>5 else 'gerekmiyor'}",p.get('created_at',''),'Yayın onayı')
        if 'publication_batches' in tables:
            for row in db.execute("SELECT payload,created_at FROM publication_batches WHERE status='active' ORDER BY rowid DESC LIMIT 40"):
                p=loads(row['payload']);own=any(str(r['employee_id'])==eid for r in p.get('rows',[]))
                if not own and role not in {'wfm','planning_manager','manager','assistant_manager','moderator','tl'}:continue
                add('PUB-'+p['id'],'Vardiya yayınlandı',f"{p['start']} – {p['end']} · Vardiyalar Tüm Vardiyalar ekranında; kişisel yemek, mola ve koçluk saatlerin İzleme ve Takip ekranlarında.",row['created_at'],'Vardiya')
        if 'status_swap_requests' in tables:
            for row in db.execute('SELECT * FROM status_swap_requests'):
                r=loads(row['payload'])
                if username in {r['owner'],r['peer']} or (role=='tl' and profile.get('full_name')==r.get('team_lead')) or role in {'wfm','planning_manager'}:add('SS-'+r['id']+'-'+str(row['version']),'Yemek / mola değişimi · '+row['status'],r['reason'],r.get('updated_at',r['created_at']),'Statü değişimi')
        if 'manager_agenda' in tables:
            for row in db.execute("SELECT * FROM manager_agenda WHERE kind='Koçluk' AND (employee_id=? OR owner=?)",(eid,username)):
                add('CO-'+row['id'],'Koçluk görüşmesi planlandı',row['start']+' – '+row['end'],row['start'],'Koçluk')
        if 'shift_change_batches' in tables:
            for row in db.execute('SELECT payload FROM shift_change_batches ORDER BY rowid DESC LIMIT 100'):
                r=loads(row[0])
                if any(str(x['employee_id'])==eid for x in r['after']):add('CHANGE-'+str(r.get('id') or r['date']),'Vardiyan güncellendi · '+r['type'],r['reason'],r['date'],'Vardiya değişimi')
    # Anonymous complaints retain owner-scoped tracking without leaking sender names.
    from ortak.gorusler import records
    for item in records(state):
        if item.get('reply'):add('FB-'+item['id']+'-'+hashlib.sha256(item['reply'].encode()).hexdigest()[:10],'Görüşüne yanıt var',item['reply'],item.get('updated_at',item['created_at']),'Uygulama')
    for p in output:p['Okundu']=p['id'] in read
    return sorted(output,key=lambda p:str(p['Tarih']),reverse=True)[:200]


def mark_read(state,ident):
    allowed={r['id'] for r in items(state)}
    if ident not in allowed:raise ValueError('Bu bildirim hesabına ait değil.')
    with connect(state['workspace_db_path']) as db:db.execute('INSERT OR IGNORE INTO notification_reads VALUES(?,?)',(state['profile']['username'],ident))


def mark_many_read(state,identifiers):
    allowed={r['id'] for r in items(state)};selected=list(identifiers)
    if any(i not in allowed for i in selected):raise ValueError('Hesabına ait bildirimleri seçin.')
    with connect(state['workspace_db_path']) as db:db.executemany('INSERT OR IGNORE INTO notification_reads VALUES(?,?)',[(state['profile']['username'],i) for i in selected])

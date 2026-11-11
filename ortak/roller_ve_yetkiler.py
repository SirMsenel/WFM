# Ortak / Roller Ve Yetkiler — bu ekranın / servisin uygulama kodu.
"""Roller ve Yetkiler — bütün değişiklik servislerinin ortak yetki kaynağı."""
from ortak.calisma_alani_deposu import connect,init_db,dumps,loads

ROLE_LABELS={'assistant_manager':'Yönetici Yardımcısı','agent':'Müşteri Temsilcisi','tl':'Takım Lideri','manager':'Yönetici','wfm':'Planlama','moderator':'Müdür','planning_manager':'Planlama Yöneticisi'}
DEFAULTS={'assistant_manager':{'personel_incele','vardiya_degistir','kayit_merkezi'},'agent':{'talep_ilet'},'tl':{'talep_ilet','personel_talebi','vardiya_degistir','rapor_gir'},
 'manager':{'personel_incele','vardiya_degistir','kayit_merkezi'},'wfm':{'personel_onayla','vardiya_degistir','kayit_merkezi','yetki_yonet'},
 'planning_manager':{'kayit_merkezi','personel_incele'},'moderator':{'personel_incele','vardiya_degistir','kayit_merkezi'}}
CAPTIONS={'talep_ilet':'Talep iletme','personel_talebi':'Personel ekleme/çıkarma önerme','personel_incele':'Personel talebi yönetici onayı',
 'personel_onayla':'Personel talebi planlama onayı','vardiya_degistir':'Yayınlanmış vardiya düzenleme','rapor_gir':'Rapor girişi (yalnızca Takım Lideri)',
 'kayit_merkezi':'Veri ve Kayıt Merkezi','yetki_yonet':'Yetkilendirme (yalnızca Planlama)'}


def init_governance(path):
    init_db(path)
    with connect(path) as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS audit_events(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,category TEXT NOT NULL,actor TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS role_permissions(role TEXT PRIMARY KEY,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS personnel_workflows(id TEXT PRIMARY KEY,version INTEGER NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS shift_change_batches(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,payload TEXT NOT NULL);''')


def permissions(state,role=None):
    role=role or (state.get('profile') or {}).get('position');result=set(DEFAULTS.get(role,set()));path=state.get('workspace_db_path')
    if path:
        init_governance(path)
        with connect(path) as db:
            row=db.execute('SELECT payload FROM role_permissions WHERE role=?',(role,)).fetchone()
            if row:result=set(loads(row[0]))
    if role!='tl':result.discard('rapor_gir')
    if role!='wfm':result.discard('yetki_yonet')
    if role=='wfm':result.add('yetki_yonet')
    return result


def require(state,capability):
    if capability=='kayit_merkezi' and (state.get('profile') or {}).get('position') not in {'wfm','manager','assistant_manager','moderator','planning_manager'}:raise ValueError('Kayıt Merkezi yalnızca Planlama, Yönetici ve Müdür içindir.')
    if capability not in permissions(state):raise ValueError('Bu işlem için yetkiniz yok: '+CAPTIONS.get(capability,capability))


def append_audit(db,category,profile,payload):
    from ortak.talep_servisi import now
    actor=profile.get('_actor_username') or profile.get('username') or profile.get('full_name') or 'sistem'
    if profile.get('_actor_username'):payload={**payload,'kullanilan_hesap':profile.get('username')}
    db.execute('INSERT INTO audit_events(created_at,category,actor,payload) VALUES(?,?,?,?)',(now(),category,actor,dumps(payload)))


def save_permissions(state,role,selected,reason):
    require(state,'yetki_yonet')
    if role not in ROLE_LABELS or not reason.strip():raise ValueError('Rol ve değişiklik gerekçesi gerekli.')
    selected=set(selected)
    if not selected<=set(CAPTIONS):raise ValueError('Bilinmeyen yetki seçilemez.')
    if role!='tl' and 'rapor_gir' in selected:raise ValueError('Rapor girişini yalnızca Takım Lideri yapabilir.')
    if role!='wfm' and 'yetki_yonet' in selected:raise ValueError('Yetkilendirmeyi yalnızca Planlama yönetebilir.')
    if role=='wfm':selected.add('yetki_yonet')
    path=state['workspace_db_path'];init_governance(path)
    with connect(path) as db:
        old=db.execute('SELECT payload FROM role_permissions WHERE role=?',(role,)).fetchone()
        before=loads(old[0]) if old else sorted(DEFAULTS[role])
        db.execute('INSERT INTO role_permissions VALUES(?,?) ON CONFLICT(role) DO UPDATE SET payload=excluded.payload',(role,dumps(sorted(selected))))
        append_audit(db,'Yetkilendirme',state['profile'],{'rol':role,'eski':before,'yeni':sorted(selected),'gerekce':reason})

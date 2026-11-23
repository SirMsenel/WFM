"""İki bağımsız planlamacı ve %5 üstü açıkta Planlama Yöneticisi onayı."""
from uuid import uuid4
import hashlib
from copy import deepcopy
from ortak.calisma_alani_deposu import connect,dumps,loads,STATE_KEYS
from ortak.roller_ve_yetkiler import init_governance,append_audit
from ortak.talep_servisi import now
from modules.vardiya_plani.planlama_verileri import fingerprint


CRITICAL_KEYS=('employees_cache','shift_rules','status_rules','slot_shrinkage','staffing_parameters','sp_staffing_result_df',
               'fixed_shift_records','shift_overrides','trk_requests','plan_overrides','group_hour_targets','acad_schedules','acad_exam_calendar')


def approval_languages(item):
    saved=item.get('languages')
    if saved:return set(saved)
    return {p.get('language','tr') for p in item.get('result',{}).get('staff',[])}


def directory_revision(state):
    """İmzada da kontrolde de veritabanındaki aynı ham revizyonu kullan."""
    path=state.get('workspace_db_path')
    if path:
        with connect(path) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='metadata'").fetchone():
                row=db.execute("SELECT value FROM metadata WHERE key='directory_revision'").fetchone()
                return row[0] if row else None
    value=state.get('_directory_revision')
    return str(value).split('|',1)[0] if value is not None else None


def source_signature(state):
    """Başka dil taslaklarını değil, planın güvenliğini etkileyen ortak kaynakları izle."""
    data={key:state.get(key) for key in CRITICAL_KEYS}
    for key in ('employees_cache','fixed_shift_records','shift_overrides','trk_requests','plan_overrides','group_hour_targets'):
        data[key]=data.get(key) or []
    for key in ('shift_rules','status_rules','staffing_parameters','acad_schedules','acad_exam_calendar'):
        data[key]=data.get(key) or {}
    data['directory_revision']=directory_revision(state)
    return hashlib.sha256(dumps(data).encode()).hexdigest()


def init(path):
    init_governance(path)
    with connect(path) as db:db.execute('CREATE TABLE IF NOT EXISTS plan_approvals(id TEXT PRIMARY KEY,status TEXT NOT NULL,payload TEXT NOT NULL)')


def proposals(state):
    init(state['workspace_db_path'])
    with connect(state['workspace_db_path']) as db:return [dict(loads(r['payload']),status=r['status']) for r in db.execute('SELECT * FROM plan_approvals ORDER BY rowid DESC')]


def submit(state,result,planning_languages=None):
    from ortak.statu_haklari import assert_complete
    assert_complete(state,result)
    if (state.get('profile') or {}).get('position')!='wfm':raise ValueError('Yayına Planlama gönderir.')
    scoped=dict(state)
    if planning_languages is not None:scoped['planning_languages']=planning_languages
    languages={key for key,value in (scoped.get('planning_languages') or {}).items() if value}
    if not languages:languages={p.get('language','tr') for p in result.get('staff',[])}
    scoped_fingerprint=fingerprint(scoped)
    if planning_languages is None and state.get('planning_result_fingerprint')!=scoped_fingerprint:raise ValueError('Taslak değişti; yeniden kontrol edin.')
    from ortak.planlama_gorunumu import blocking_issues
    if blocking_issues(result) and not state.get('planning_accept_hard'):raise ValueError('Kesin kural ihlalleri çözülmeli veya planlama onayıyla devam seçeneği işaretlenmeli.')
    for existing in proposals(state):
        old=existing['result'];new=result
        if existing['status']=='Bekliyor' and old['period']['start']<=new['period']['end'] and new['period']['start']<=old['period']['end'] and approval_languages(existing) & languages:raise ValueError('Bu dönem ve dil için onay bekleyen plan var: '+existing['id']+'. Önce sonuçlandırın veya reddedin.')
    path=state['workspace_db_path'];init(path);coverage=result['coverage'];coverage=coverage[coverage.get('Sayaca Dahil',True)] if 'Sayaca Dahil' in coverage else coverage
    total=float(coverage['İhtiyaç'].sum());gap=float(coverage['Eksik'].sum());rate=100*gap/total if total else 0.
    result={k:deepcopy(result[k]) for k in ('plan','coverage','staff','period','issues','rules','breaks') if k in result}
    from ortak.statu_kapasite_raporu import entitlement_snapshot
    result['status_rights']=entitlement_snapshot(state,result['plan'],result['staff'])
    from modules.vardiya_plani.planlama_verileri import SOURCE_KEYS
    context_keys=set(SOURCE_KEYS)|{'planning_accept_soft','planning_accept_hard'}
    context={k:deepcopy(scoped[k]) for k in context_keys if k in scoped}
    item={'id':'APR-'+uuid4().hex[:12],'fingerprint':scoped_fingerprint,'source_signature':source_signature(state),'languages':sorted(languages),'result':result,'context':context,'rate':rate,'votes':[],'manager':None,'created_by':state['profile']['username'],'created_at':now()}
    baseline=dict(state.get('workspace_baseline',{}))
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        for row in db.execute("SELECT payload FROM plan_approvals WHERE status='Bekliyor'"):
            pending=loads(row[0]);old=pending['result'];new=item['result']
            if old['period']['start']<=new['period']['end'] and new['period']['start']<=old['period']['end']:
                if approval_languages(pending) & languages:raise ValueError('Bu dönem ve dil için onay bekleyen plan var: '+pending['id']+'. Önce sonuçlandırın veya reddedin.')
        # Persist proposal sources only after reserving its period, in the same transaction.
        for key in STATE_KEYS:
            if key not in state:continue
            payload=dumps(state[key]);digest=hashlib.sha256(payload.encode()).hexdigest()
            if baseline.get(key)!=digest:
                db.execute('INSERT INTO work_state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload',(key,payload));baseline[key]=digest
        db.execute('INSERT INTO plan_approvals VALUES(?,?,?)',(item['id'],'Bekliyor',dumps(item)));append_audit(db,'Plan onaya gönderildi',state['profile'],{'id':item['id'],'eksik_yuzdesi':rate})
    state['workspace_baseline']=baseline
    return item['id']


def ready(item):return len({v['actor'] for v in item['votes']})>=2 and (item['rate']<=5 or item.get('manager') is not None)


def current_context(state,item,db):
    check=dict(state)
    for r in db.execute('SELECT key,payload FROM work_state'):
        if r['key'] in STATE_KEYS:check[r['key']]=loads(r['payload'])
    check['trk_requests']=[loads(r[0]) for r in db.execute('SELECT payload FROM requests')];check.update(item['context']);check['planning_result_fingerprint']=item['fingerprint'];return check


def is_current(state,item):
    with connect(state['workspace_db_path']) as db:
        current=dict(state)
        for r in db.execute('SELECT key,payload FROM work_state'):
            if r['key'] in STATE_KEYS:current[r['key']]=loads(r['payload'])
        current['trk_requests']=[loads(r[0]) for r in db.execute('SELECT payload FROM requests')]
        revision=db.execute("SELECT value FROM metadata WHERE key='directory_revision'").fetchone() if db.execute("SELECT 1 FROM sqlite_master WHERE name='metadata'").fetchone() else None
        current['_directory_revision']=revision[0] if revision else None
        if 'source_signature' not in item:return fingerprint(current_context(state,item,db))==item['fingerprint']
    return source_signature(current)==item['source_signature']


def vote(state,ident,approve=True,reason=''):
    profile=state.get('profile') or {};role=profile.get('position');actor=profile.get('_actor_username') or profile.get('username')
    if role not in {'wfm','planning_manager'}:raise ValueError('Planlamacı veya Planlama Yöneticisi gerekli.')
    path=state['workspace_db_path'];init(path)
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT * FROM plan_approvals WHERE id=?',(ident,)).fetchone()
        if not row or row['status']!='Bekliyor':raise ValueError('Onay bekleyen plan bulunamadı.')
        item=loads(row['payload'])
        if not approve:
            if not reason.strip():raise ValueError('Ret gerekçesi gerekli.')
            db.execute("UPDATE plan_approvals SET status='Reddedildi' WHERE id=?",(ident,));append_audit(db,'Plan yayını reddedildi',profile,{'id':ident,'reason':reason});return False
        current=dict(state)
        for source in db.execute('SELECT key,payload FROM work_state'):
            if source['key'] in STATE_KEYS:current[source['key']]=loads(source['payload'])
        current['trk_requests']=[loads(source[0]) for source in db.execute('SELECT payload FROM requests')]
        revision=db.execute("SELECT value FROM metadata WHERE key='directory_revision'").fetchone() if db.execute("SELECT 1 FROM sqlite_master WHERE name='metadata'").fetchone() else None
        current['_directory_revision']=revision[0] if revision else None
        current_ok=source_signature(current)==item['source_signature'] if 'source_signature' in item else fingerprint(current_context(state,item,db))==item['fingerprint']
        if not current_ok:raise ValueError('Taslak güncel değil. Kaynaklar değişti; bu taslağı reddedip güncel planı yeniden oluşturun.')
        if actor in {v['actor'] for v in item['votes']} or (item.get('manager') or {}).get('actor')==actor:raise ValueError('Aynı gerçek kullanıcı ikinci onayı veremez; hesap görünümü değiştirmek bağımsız onay sayılmaz.')
        entry={'actor':actor,'as':profile['username'],'name':profile.get('full_name') or profile['username'],'role':role,'at':now()}
        if role=='wfm':item['votes'].append(entry)
        else:item['manager']=entry
        db.execute('UPDATE plan_approvals SET payload=? WHERE id=?',(dumps(item),ident));append_audit(db,'Plan yayın onayı',profile,{'id':ident,**entry})
    if ready(item):
        check=dict(state)
        with connect(path) as db:
            for r in db.execute('SELECT key,payload FROM work_state'):
                if r['key'] in STATE_KEYS:check[r['key']]=loads(r['payload'])
            check['trk_requests']=[loads(r[0]) for r in db.execute('SELECT payload FROM requests')]
        check.update(item['context']);check['planning_result_fingerprint']=item['fingerprint']
        from ortak.yayin_servisi import publish_plan
        publish_plan(check,item['result'],approval_ticket=ident)
        for key in ('published_shift_plan','last_publication','planning_result_fingerprint','workspace_baseline','trk_requests'): 
            if key in check:state[key]=check[key]
        return True
    return False

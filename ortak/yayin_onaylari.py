"""İki bağımsız planlamacı ve %5 üstü açıkta Planlama Yöneticisi onayı."""
from uuid import uuid4
from copy import deepcopy
from ortak.calisma_alani_deposu import connect,dumps,loads,STATE_KEYS
from ortak.roller_ve_yetkiler import init_governance,append_audit
from ortak.talep_servisi import now
from modules.vardiya_plani.planlama_verileri import fingerprint


def init(path):
    init_governance(path)
    with connect(path) as db:db.execute('CREATE TABLE IF NOT EXISTS plan_approvals(id TEXT PRIMARY KEY,status TEXT NOT NULL,payload TEXT NOT NULL)')


def proposals(state):
    init(state['workspace_db_path'])
    with connect(state['workspace_db_path']) as db:return [dict(loads(r['payload']),status=r['status']) for r in db.execute('SELECT * FROM plan_approvals ORDER BY rowid DESC')]


def submit(state,result):
    if (state.get('profile') or {}).get('position')!='wfm':raise ValueError('Yayına Planlama gönderir.')
    if state.get('planning_result_fingerprint')!=fingerprint(state):raise ValueError('Taslak değişti; yeniden kontrol edin.')
    from ortak.planlama_gorunumu import blocking_issues
    if blocking_issues(result):raise ValueError('Hard ihlaller çözülmeli.')
    from ortak.calisma_alani_deposu import save_keys
    save_keys(state)
    path=state['workspace_db_path'];init(path);coverage=result['coverage'];coverage=coverage[coverage.get('Sayaca Dahil',True)] if 'Sayaca Dahil' in coverage else coverage
    total=float(coverage['İhtiyaç'].sum());gap=float(coverage['Eksik'].sum());rate=100*gap/total if total else 0.
    for p in proposals(state):
        if p['status']=='Bekliyor' and p['fingerprint']==fingerprint(state):return p['id']
    result={k:deepcopy(result[k]) for k in ('plan','coverage','staff','period','issues','rules','breaks') if k in result}
    context={k:deepcopy(state[k]) for k in ('plan_ctx','plan_ctx_confirmed','planning_languages','planning_exam_hours','planning_exclude_early_hours','planning_bypass','planning_accept_soft','employees_cache') if k in state}
    item={'id':'APR-'+uuid4().hex[:12],'fingerprint':fingerprint(state),'result':result,'context':context,'rate':rate,'votes':[],'manager':None,'created_by':state['profile']['username'],'created_at':now()}
    with connect(path) as db:db.execute('INSERT INTO plan_approvals VALUES(?,?,?)',(item['id'],'Bekliyor',dumps(item)));append_audit(db,'Plan onaya gönderildi',state['profile'],{'id':item['id'],'eksik_yuzdesi':rate})
    return item['id']


def ready(item):return len({v['actor'] for v in item['votes']})>=2 and (item['rate']<=5 or item.get('manager') is not None)


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
        if actor in {v['actor'] for v in item['votes']} or (item.get('manager') or {}).get('actor')==actor:raise ValueError('Aynı gerçek kullanıcı ikinci onayı veremez; hesap görünümü değiştirmek bağımsız onay sayılmaz.')
        entry={'actor':actor,'as':profile['username'],'at':now()}
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

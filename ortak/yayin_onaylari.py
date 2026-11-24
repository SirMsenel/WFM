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


def source_signature(state,languages=None):
    """Başka dil taslaklarını değil, planın güvenliğini etkileyen ortak kaynakları izle."""
    languages=set(languages or ())
    foreign_only=bool(languages) and 'tr' not in languages
    if foreign_only:
        employees=[row for row in (state.get('employees_cache') or []) if (row.get('language') or 'tr') in languages]
        ids={str(row.get('employee_id')) for row in employees};users={str(row.get('username')) for row in employees if row.get('username')}
        def relevant(row):
            return str(row.get('employee_id',row.get('employee',row.get('created_by','')))) in ids|users
        data={'employees_cache':employees,'shift_rules':state.get('shift_rules'),'status_rules':state.get('status_rules'),
              'fixed_shift_records':[row for row in (state.get('fixed_shift_records') or []) if relevant(row)],
              'shift_overrides':[row for row in (state.get('shift_overrides') or []) if relevant(row)],
              'trk_requests':[row for row in (state.get('trk_requests') or []) if relevant(row)],
              'plan_overrides':[row for row in (state.get('plan_overrides') or []) if relevant(row)],
              'group_hour_targets':state.get('group_hour_targets'),
              'acad_schedules':{key:value for key,value in (state.get('acad_schedules') or {}).items() if str(key) in ids|users},
              'acad_exam_calendar':{key:value for key,value in (state.get('acad_exam_calendar') or {}).items() if str(key) in ids|users}}
    else:data={key:state.get(key) for key in CRITICAL_KEYS}
    for key in ('employees_cache','fixed_shift_records','shift_overrides','trk_requests','plan_overrides','group_hour_targets'):
        data[key]=data.get(key) or []
    for key in ('shift_rules','status_rules','staffing_parameters','acad_schedules','acad_exam_calendar'):
        data[key]=data.get(key) or {}
    # DataFrame çalışma alanına JSON olarak yazılıp geri okunduğunda pandas
    # dtype metadatası değişebilir; değerler aynıysa onayı eskitmemelidir.
    if not foreign_only:
        frame=data.get('sp_staffing_result_df')
        if hasattr(frame,'to_json'):
            normalized=frame.copy()
            if 'Tarih' in normalized:normalized['Tarih']=__import__('pandas').to_datetime(normalized['Tarih'])
            data['sp_staffing_result_df']=normalized.to_json(date_format='iso',orient='split')
    if not foreign_only:data['directory_revision']=directory_revision(state)
    return hashlib.sha256(dumps(data).encode()).hexdigest()


def approval_signature(state, languages, reviewed=None):
    """Match only the sources used by this language's plan, in stable order."""
    scoped = dict(state)
    people = [p for p in state.get('employees_cache', []) if (p.get('language') or 'tr') in languages]
    identities = {str(p.get(field)) for p in people for field in ('employee_id', 'username') if p.get(field)}
    scoped['employees_cache'] = sorted(people, key=lambda p: str(p['employee_id']))
    for key in ('fixed_shift_records', 'shift_overrides', 'trk_requests', 'plan_overrides'):
        def belongs(row):
            owner = row.get('request') or row
            return any(str(owner.get(f, '')) in identities for f in ('employee_id','created_by','employee')) or any(
                str(target.get('employee_id')) in identities for target in owner.get('targets', []))
        scoped[key] = sorted((row for row in state.get(key, []) if belongs(row)), key=dumps)
    for key in ('acad_schedules', 'acad_exam_calendar'):
        scoped[key] = {k:v for k,v in state.get(key, {}).items() if str(k) in identities}
    if 'tr' in languages:
        from ortak.plan_ihtiyaci import demand
        staffing = demand(dict(state, planning_demand_language=None))
        if staffing is not None:
            scoped['sp_staffing_result_df'] = staffing.sort_values(['Tarih','Slot']).reset_index(drop=True)
    signature = source_signature(scoped, languages)
    if 'tr' in languages:
        return signature
    sources = []
    for lang in sorted(languages):
        need = (state.get('language_demands') or {}).get(lang)
        if need is not None:
            import pandas as pd
            need = need.assign(Tarih=pd.to_datetime(need['Tarih'])).sort_values(['Tarih','Slot'])
            need = need.reset_index(drop=True).to_json(orient='split',date_format='iso')
        plan = (state.get('foreign_language_plans') or {}).get(lang) or reviewed or {}
        sources.append((lang, need, plan.get('plan') or []))
    return hashlib.sha256(dumps([signature,sources]).encode()).hexdigest()


def approval_is_current(state, item, db):
    languages = approval_languages(item)
    if not state.get('employees_cache'):
        from ortak.personel import planner_people
        planner_people(state)
    current = dict(state)
    for row in db.execute('SELECT key,payload FROM work_state'):
        if row['key'] in STATE_KEYS:
            current[row['key']] = loads(row['payload'])
    current['trk_requests'] = [loads(row[0]) for row in db.execute('SELECT payload FROM requests ORDER BY id')]
    if item.get('signature_version') == 2:
        return approval_signature(current, languages, item['result']) == item['source_signature']
    if 'source_signature' in item:
        legacy_languages = item.get('source_signature_languages')
        if source_signature(current, legacy_languages) == item['source_signature']:
            return True
        # For pending older tickets verify the archived sources against the
        # original signature before comparing their language-specific subset.
        original = {**current, **item.get('context', {})}
        return (source_signature(original, legacy_languages) == item['source_signature']
                and approval_signature(original, languages) == approval_signature(current, languages))
    return fingerprint(current_context(state,item,db)) == item['fingerprint']


def init(path):
    init_governance(path)
    with connect(path) as db:db.execute('CREATE TABLE IF NOT EXISTS plan_approvals(id TEXT PRIMARY KEY,status TEXT NOT NULL,payload TEXT NOT NULL)')


def proposals(state):
    init(state['workspace_db_path'])
    with connect(state['workspace_db_path']) as db:return [dict(loads(r['payload']),status=r['status']) for r in db.execute('SELECT * FROM plan_approvals ORDER BY rowid DESC')]


def submit(state,result,planning_languages=None):
    if (state.get('profile') or {}).get('position')!='wfm':raise ValueError('Yayına Planlama gönderir.')
    scoped=dict(state)
    if planning_languages is not None:scoped['planning_languages']=planning_languages
    languages={key for key,value in (scoped.get('planning_languages') or {}).items() if value}
    if not languages:languages={p.get('language','tr') for p in result.get('staff',[])}
    from ortak.yayin_servisi import publication_scope
    approval_result=publication_scope(result,scoped.get('planning_languages'))
    from ortak.statu_haklari import assert_complete
    assert_complete(state,approval_result)
    scoped_fingerprint=fingerprint(scoped)
    if planning_languages is None and state.get('planning_result_fingerprint')!=scoped_fingerprint:raise ValueError('Taslak değişti; yeniden kontrol edin.')
    from ortak.planlama_gorunumu import blocking_issues
    if blocking_issues(approval_result) and not state.get('planning_accept_hard'):raise ValueError('Kesin kural ihlalleri çözülmeli veya planlama onayıyla devam seçeneği işaretlenmeli.')
    for existing in proposals(state):
        old=existing['result'];new=result
        if existing['status']=='Bekliyor' and old['period']['start']<=new['period']['end'] and new['period']['start']<=old['period']['end'] and approval_languages(existing) & languages:raise ValueError('Bu dönem ve dil için onay bekleyen plan var: '+existing['id']+'. Önce sonuçlandırın veya reddedin.')
    path=state['workspace_db_path'];init(path);coverage=approval_result['coverage'];coverage=coverage[coverage.get('Sayaca Dahil',True)] if 'Sayaca Dahil' in coverage else coverage
    total=float(coverage['İhtiyaç'].sum());gap=float(coverage['Eksik'].sum());rate=100*gap/total if total else 0.
    result={k:deepcopy(approval_result[k]) for k in ('plan','coverage','staff','period','issues','rules','breaks') if k in approval_result}
    from ortak.statu_kapasite_raporu import entitlement_snapshot
    result['status_rights']=entitlement_snapshot(state,result['plan'],result['staff'])
    from modules.vardiya_plani.planlama_verileri import SOURCE_KEYS
    # fingerprint(), talep seçicisi üzerinden bu tabloyu da okur; onay anındaki
    # kopya saklanmazsa son yayın adımı sonradan değişen Türkçe hesabı görür.
    context_keys=set(SOURCE_KEYS)|{'sp_staffing_result_df','planning_accept_soft','planning_accept_hard'}
    context={k:deepcopy(scoped[k]) for k in context_keys if k in scoped}
    item={'id':'APR-'+uuid4().hex[:12],'fingerprint':scoped_fingerprint,'signature_version':2,'source_signature':approval_signature(state,languages,result),'source_signature_languages':sorted(languages),'languages':sorted(languages),'result':result,'context':context,'rate':rate,'votes':[],'manager':None,'created_by':state['profile']['username'],'created_at':now()}
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
        return approval_is_current(state,item,db)


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
        if not approval_is_current(state,item,db):
            raise ValueError('Taslak güncel değil. Kaynaklar değişti; bu taslağı reddedip güncel planı yeniden oluşturun.')
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
        for key in ('plan_ctx','planning_languages','planning_accept_hard','planning_accept_soft'):
            if key in item['context']:
                check[key] = item['context'][key]
        check['planning_result_fingerprint'] = item['fingerprint']
        from ortak.yayin_servisi import publish_plan
        publish_plan(check,item['result'],approval_ticket=ident)
        for key in ('published_shift_plan','last_publication','workspace_baseline','trk_requests'):
            if key in check:state[key]=check[key]
        return True
    return False

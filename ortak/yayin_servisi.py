# Ortak / Yayin Servisi — bu ekranın / servisin uygulama kodu.
from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import uuid4
from ortak.calisma_alani_deposu import save_keys,connect,init_db,dumps,loads
from ortak.planlama_gorunumu import blocking_issues
from modules.vardiya_plani.planlama_verileri import fingerprint


def init_publications(path):
    init_db(path)
    from ortak.sabit_demo import init_history
    init_history(path)
    with connect(path) as db:db.execute('CREATE TABLE IF NOT EXISTS publication_batches(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL)')


def publish_plan(state,result,approval_ticket=None):
    gated=state.get("shift_rules",{}).get("publication_approvals",{}).get("enabled",False)
    if gated and not approval_ticket:raise ValueError("Önce iki Planlama onayı; eksik %5 üzerindeyse Planlama Yöneticisi onayı gerekli.")
    from ortak.donem_kilitleri import assert_can_plan
    if state.get("workspace_db_path"):
        from ortak.talep_servisi import refresh
        refresh(state)
    if state.get('planning_result_fingerprint')!=fingerprint(state):raise ValueError('Taslak güncel değil. Yeniden oluşturun.')
    if blocking_issues(result):raise ValueError('Kayıt veya çalışma kuralı ihlallerini düzeltin; eksik ihtiyacın kabulü bu ihlalleri kaldırmaz.')
    if any(r.get('severity')=='warning' and r.get('override_required',True) for r in result.get('issues',[])) and not state.get('planning_accept_soft'):raise ValueError('Esnek kural aşımlarını inceleyip onaylayın.')
    path=state.get('workspace_db_path');previous=state.get('published_shift_plan',[])
    start,end=result['period']['start'],result['period']['end'];included={str(e['employee_id']) for e in result['staff']}
    language={str(e['employee_id']):e.get('language') or 'tr' for e in result['staff']}
    batch_id='PUB-'+uuid4().hex[:12]
    rows=[dict(r,language=language[str(r['employee_id'])],publication_id=batch_id) for r in result['plan']]
    payload={'id':batch_id,'start':start,'end':end,'rows':rows,'languages':sorted(set(language.values())),'actor':(state.get('profile') or {}).get('username')}
    if path:
        init_publications(path)
        from ortak.kocluk_alanlari import init as init_openings
        init_openings(path)
        with connect(path) as db:
            db.execute('BEGIN IMMEDIATE')
            if gated:
                from ortak.yayin_onaylari import ready
                approval=db.execute('SELECT * FROM plan_approvals WHERE id=?',(approval_ticket,)).fetchone()
                if not approval or approval['status']!='Bekliyor':raise ValueError('Yayın onayı güncel değil.')
                item=loads(approval['payload'])
                if not ready(item) or item['fingerprint']!=state['planning_result_fingerprint'] or dumps(item['result']['plan'])!=dumps(result['plan']):raise ValueError('Onaylar bu taslağa ait değil.')
            stored=db.execute("SELECT payload FROM work_state WHERE key='published_shift_plan'").fetchone()
            current=loads(stored[0]) if stored else previous
            latest_requests=[loads(r[0]) for r in db.execute('SELECT payload FROM requests')]
            check=dict(state,published_shift_plan=current,trk_requests=latest_requests or state.get('trk_requests',[]))
            if fingerprint(check)!=state.get('planning_result_fingerprint'):raise ValueError('Yayın veya talepler başka bir oturumda değişti. Güncel bilgilerle yeniden oluşturun.')
            assert_can_plan(check,result['staff'])
            published=[r for r in current if not start<=str(r.get('date'))<=end or str(r['employee_id']) not in included]+rows
            db.execute('INSERT INTO publication_batches VALUES(?,?,?,?)',(payload['id'],datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(),'active',dumps(payload)))
            db.execute("INSERT INTO work_state VALUES('published_shift_plan',?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload",(dumps(published),))
            if gated:db.execute("UPDATE plan_approvals SET status='Yayınlandı' WHERE id=?",(approval_ticket,))
            from ortak.talep_simulasyonu import finalize
            finalize(db,rows,start,end,(state.get('profile') or {}).get('username'))
            if result.get('breaks'):
                db.execute('CREATE TABLE IF NOT EXISTS planned_breaks(id TEXT PRIMARY KEY,publication_id TEXT,payload TEXT)')
                for i,r in enumerate(result['breaks']):
                    if r['kind']=='Koçluk Alanı':db.execute('INSERT INTO coaching_openings VALUES(?,?,?,?,?)',(batch_id+'-'+str(i),batch_id,str(r['employee_id']),'Açık',dumps(r)))
                    else:db.execute('INSERT INTO planned_breaks VALUES(?,?,?)',(batch_id+'-'+str(i),batch_id,dumps(r)))
        from ortak.talep_servisi import refresh
        refresh(state)
        state['published_shift_plan']=published
    else:
        assert_can_plan(state,result['staff'])
        state['published_shift_plan']=[r for r in previous if not start<=str(r.get('date'))<=end or str(r['employee_id']) not in included]+rows
        state['publication_batches']=state.get('publication_batches',[])+[dict(payload,status='active')]
    save_keys(state)
    state['planning_result_fingerprint']=fingerprint(state)
    state['last_publication']={'id':payload['id'],'start':start,'end':end,'count':len(rows),'at':datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(),'fingerprint':state['planning_result_fingerprint']}


def publications(state):
    path=state.get('workspace_db_path')
    if path:
        init_publications(path)
        from ortak.kocluk_alanlari import init as init_openings
        init_openings(path)
        with connect(path) as db:result=[dict(loads(r['payload']),status=r['status'],created_at=r['created_at']) for r in db.execute('SELECT * FROM publication_batches ORDER BY created_at DESC')]
    else:result=list(state.get('publication_batches',[]))
    for batch in result:
        if batch['status']=='active':
            current=[r for r in state.get('published_shift_plan',[]) if r.get('publication_id')==batch['id']]
            if current:batch['rows']=current
    covered={(str(r['employee_id']),str(r['date'])) for b in result if b['status']=='active' for r in b['rows']}
    legacy={}
    lookup={str(e['employee_id']):e.get('language') or 'tr' for e in state.get('employees_cache',[])}
    import pandas as pd
    for r in state.get('published_shift_plan',[]):
        if (str(r['employee_id']),str(r['date'])) in covered:continue
        day=pd.Timestamp(r['date']);week=str((day-pd.Timedelta(days=day.weekday())).date());lang=r.get('language') or lookup.get(str(r['employee_id']),'tr')
        legacy.setdefault((week,lang),[]).append(r)
    for (week,lang),rows in legacy.items():result.append({'id':'LEGACY-'+week+'-'+lang,'start':min(r['date'] for r in rows),'end':max(r['date'] for r in rows),'rows':rows,'languages':[lang],'status':'active'})
    return result


def publication_today():return datetime.now(ZoneInfo('Europe/Istanbul')).date()


def withdraw(state,batch,reopen=False):
    if str(batch['start'])<publication_today().isoformat():raise ValueError('Geçmiş günleri içeren yayın geri alınamaz. Yalnızca bugünden itibaren başlayan dönemler geri alınabilir.')
    from copy import deepcopy
    keys={(str(r['employee_id']),str(r['date'])) for r in batch['rows']}
    def change(current):
        actual={(str(r['employee_id']),str(r['date'])):r for r in current}
        for r in batch['rows']:
            old=actual.get((str(r['employee_id']),str(r['date'])))
            if old is None or any(old.get(k)!=r.get(k) for k in ('shift_code','start','end','publication_id')):raise ValueError('Yayın başka bir işlemle değişti. Listeyi yenileyin.')
        return [r for r in current if (str(r['employee_id']),str(r['date'])) not in keys]
    path=state.get('workspace_db_path')
    if path:
        init_publications(path)
        from ortak.kocluk_alanlari import init as init_openings
        init_openings(path)
        with connect(path) as db:
            db.execute('BEGIN IMMEDIATE');stored=db.execute("SELECT payload FROM work_state WHERE key='published_shift_plan'").fetchone()
            published=change(loads(stored[0]) if stored else state.get('published_shift_plan',[]))
            if batch['id'].startswith('LEGACY-'):db.execute('INSERT INTO publication_batches VALUES(?,?,?,?)',(batch['id']+'-'+uuid4().hex[:6],datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(),'withdrawn',dumps(batch)))
            else:db.execute("UPDATE publication_batches SET status='withdrawn' WHERE id=? AND status='active'",(batch['id'],))
            db.execute("INSERT INTO work_state VALUES('published_shift_plan',?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload",(dumps(published),))
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='planned_breaks'").fetchone():db.execute('DELETE FROM planned_breaks WHERE publication_id=?',(batch['id'],))
            opening_ids={r[0] for r in db.execute('SELECT id FROM coaching_openings WHERE publication_id=?',(batch['id'],))}
            if opening_ids and db.execute("SELECT 1 FROM sqlite_master WHERE name='planned_breaks'").fetchone():
                for item in db.execute('SELECT id,payload FROM planned_breaks').fetchall():
                    if loads(item['payload']).get('opening_id') in opening_ids:
                        db.execute('DELETE FROM planned_breaks WHERE id=?',(item['id'],))
                        if db.execute("SELECT 1 FROM sqlite_master WHERE name='manager_agenda'").fetchone():db.execute("DELETE FROM manager_agenda WHERE id=? AND kind='Koçluk'",(item['id'],))
            db.execute('DELETE FROM coaching_openings WHERE publication_id=?',(batch['id'],))
        state['published_shift_plan']=published
    else:
        state['published_shift_plan']=change(state.get('published_shift_plan',[]))
        for b in state.get('publication_batches',[]):
            if b['id']==batch['id']:b['status']='withdrawn'
    draft=[r for r in state.get('draft_shift_plan',[]) if (str(r['employee_id']),str(r['date'])) not in keys]
    if reopen:
        draft += [dict(deepcopy(r),source='manual_single') for r in batch['rows'] if r.get('source') not in {'fixed_external','approved_request','published_fixed'}]
    state['draft_shift_plan']=draft;state.pop('planning_result',None);state.pop('last_publication',None)
    from datetime import date
    state['plan_ctx']={'start':date.fromisoformat(batch['start']),'end':date.fromisoformat(batch['end'])};state['plan_ctx_confirmed']=True
    save_keys(state)

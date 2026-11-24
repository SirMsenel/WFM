# Ortak / Donem Kilitleri — bu ekranın / servisin uygulama kodu.
import hashlib,json
import pandas as pd
from ortak.talep_servisi import is_terminal,refresh
from ortak.personel import LANG_LABELS


def planning_problem(state,context=None,employees=None):
    ctx=context or state.get('plan_ctx') or {}
    if not ctx.get('start') or not ctx.get('end'):return None
    start,end=str(pd.Timestamp(ctx['start']).date()),str(pd.Timestamp(ctx['end']).date())
    people=employees if employees is not None else state.get('employees_cache',[])
    included=state.get('planning_languages',{'tr':True,'en':True,'ar':True})
    people=[e for e in people if included.get(e.get('language') or 'tr',True)]
    languages={e.get('language') or 'tr' for e in people}
    lookup={str(e['employee_id']):e.get('language') or 'tr' for e in state.get('employees_cache',[])}
    existing=[]
    for r in state.get('published_shift_plan',[]):
        language=r.get('language') or lookup.get(str(r['employee_id']),'tr')
        if start<=str(r.get('date'))<=end and language in languages:
            existing.append({'Tarih':r['date'],'Dil':LANG_LABELS.get(language,language),'Personel':r.get('full_name',r['employee_id'])})
    if existing:return {'kind':'published','message':'Bu tarih ve dil kapsamının vardiyası zaten yayınlanmış. Yeni plan reddedildi. Önce Yayın Yönetimi ekranında yayını geri alın.','rows':existing}
    users={str(e.get('username')) for e in people};ids={str(e['employee_id']) for e in people}
    from ortak.planlama import school_term
    terms={school_term(d) for d in pd.date_range(start,end)}
    requests=[]
    for r in state.get('trk_requests',[]):
        if is_terminal(r) or r.get('queue')=='SIMULATION':continue
        if str(r.get('employee_id')) not in ids and str(r.get('created_by')) not in users and not any(str(t.get('employee_id')) in ids for t in r.get('targets',[])):continue
        a,b=r.get('start_date'),r.get('end_date') or r.get('start_date')
        relevant=bool(a and b and str(a)<=end and start<=str(b))
        if not a and r.get('type')=='Ders Programı':relevant=any(t in str(r.get('generated_ref','')) for t in terms)
        if relevant:requests.append({'Kayıt':r['id'],'Personel':r.get('created_by_name',r.get('created_by')),'Talep':r.get('type'),'Başlangıç':a or 'Dönemlik','Bitiş':b or 'Dönemlik','Durum':r.get('status'),'Onay beklenen':(', '.join(t for t in r.get('assigned_tls',[]) if t not in r.get('tl_approvals',[])) if r.get('queue') in {'TL','TL_SWAP'} else 'Planlama')})
    bypass=state.get('planning_bypass',{}).get(start+'|'+end)
    acknowledged = set((bypass or {}).get('requests', []))
    if bypass and str(bypass.get('reason','')).strip():
        requests = [row for row in requests if row['Kayıt'] not in acknowledged]
    if requests:return {'kind':'requests','message':'Bu dönemde bekleyen talepler var. Planlama bunları değerlendirebilir veya gerekçeyle es geçebilir.','rows':requests}
    return None


def refresh_guard(state):
    path=state.get('workspace_db_path')
    if not path:return
    from ortak.calisma_alani_deposu import connect,loads
    refresh(state)
    with connect(path) as db:
        row=db.execute("SELECT payload FROM work_state WHERE key='planning_bypass'").fetchone()
        if row:state['planning_bypass']=loads(row[0])


def assert_transaction_can_plan(db,state,context,employees,languages):
    from ortak.calisma_alani_deposu import loads
    scope=dict(state,plan_ctx=context,planning_languages=languages)
    for key in ('planning_bypass','published_shift_plan'):
        row=db.execute('SELECT payload FROM work_state WHERE key=?',(key,)).fetchone()
        if row:scope[key]=loads(row[0])
    scope['trk_requests']=[loads(r[0]) for r in db.execute('SELECT payload FROM requests')]
    problem=planning_problem(scope,employees=employees)
    if problem:raise ValueError(problem['message'])


def assert_can_plan(state,employees=None):
    refresh_guard(state)
    problem=planning_problem(state,employees=employees)
    if problem:raise ValueError(problem['message'])


def record_bypass(state,context,problem,reason):
    from ortak.calisma_alani_deposu import connect,dumps,loads
    profile=state.get('profile') or {}
    if profile.get('position') not in {'wfm','planning_manager'} or not reason.strip():
        raise ValueError('Planlama yetkisi ve es geçme gerekçesi gerekli.')
    key='|'.join(str(pd.Timestamp(context[k]).date()) for k in ('start','end'))
    ids={row['Kayıt'] for row in problem['rows']}
    def merge(decisions):
        decisions=dict(decisions)
        previous=decisions.get(key) or {}
        event={'requests':sorted(ids),'reason':reason.strip(),'actor':profile['username']}
        decisions[key]={**event,'requests':sorted(ids.union(previous.get('requests',[]))),
                        'events':previous.get('events',[])+[event]}
        return decisions
    if state.get('workspace_db_path'):
        with connect(state['workspace_db_path']) as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT payload FROM work_state WHERE key='planning_bypass'").fetchone()
            decisions=merge(loads(row[0]) if row else state.get('planning_bypass') or {})
            payload=dumps(decisions)
            db.execute("INSERT INTO work_state VALUES('planning_bypass',?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload",(payload,))
        state['workspace_baseline']={**state.get('workspace_baseline',{}),'planning_bypass':hashlib.sha256(payload.encode()).hexdigest()}
    else:decisions=merge(state.get('planning_bypass') or {})
    state['planning_bypass']=decisions


def render_guard(state,languages=None,context=None,employees=None,*,requests_only=False):
    import streamlit as st
    refresh_guard(state)
    context=context or state.get('plan_ctx') or {}
    scoped=dict(state,planning_languages=languages) if languages is not None else state
    problem=planning_problem(scoped,context,employees)
    if not problem or requests_only and problem['kind']=='published':return True
    st.warning(problem['message']);st.dataframe(problem['rows'],hide_index=True,use_container_width=True)
    if problem['kind']=='requests' and (state.get('profile') or {}).get('position') in {'wfm','planning_manager'}:
        reason=st.text_input('Bekleyen talepleri es geçme gerekçesi',key='guard_bypass_reason')
        if st.button('Talepleri Şimdilik Es Geç ve Planla',disabled=not reason.strip(),key='guard_bypass'):
            record_bypass(state,context,problem,reason);st.rerun()
    destination='Yayın Yönetimi' if problem['kind']=='published' else 'Talepler'
    def open_page():
        from ortak.gezinme import navigate
        navigate(state,'🗓️ Vardiya Planı');state['nav_roster']=destination
    if st.button(destination+' Ekranını Aç',key='guard_open_'+problem['kind'],on_click=open_page):st.rerun()
    token=hashlib.sha1(json.dumps([state.get('plan_ctx'),problem],default=str,ensure_ascii=False).encode()).hexdigest()
    if state.get('planning_guard_seen')!=token:
        state['planning_guard_seen']=token
        @st.dialog('Vardiya planlaması durduruldu')
        def warning():
            st.warning(problem['message']);st.dataframe(problem['rows'][:15],hide_index=True,use_container_width=True)
            if problem['kind']=='requests' and state.get('profile',{}).get('position') in {'wfm','planning_manager'}:
                reason=st.text_input('Es geçme gerekçesi',key='guard_modal_reason')
                if st.button('Talepleri Es Geç ve Devam Et',key='guard_modal_bypass'):
                    if not reason.strip():st.warning('Es geçme gerekçesini doldurun.')
                    else:
                        record_bypass(state,context,problem,reason);st.rerun()
            if st.button('Anladım',key='guard_ack'):st.rerun()
        warning()
    return False

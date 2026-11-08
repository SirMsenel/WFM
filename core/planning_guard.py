import hashlib,json
import pandas as pd
from core.request_service import is_terminal,refresh
from core.personnel import LANG_LABELS


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
    from core.planning import school_term
    terms={school_term(d) for d in pd.date_range(start,end)}
    requests=[]
    for r in state.get('trk_requests',[]):
        if is_terminal(r):continue
        if str(r.get('employee_id')) not in ids and str(r.get('created_by')) not in users and not any(str(t.get('employee_id')) in ids for t in r.get('targets',[])):continue
        a,b=r.get('start_date'),r.get('end_date') or r.get('start_date')
        relevant=bool(a and b and str(a)<=end and start<=str(b))
        if not a and r.get('type')=='Ders Programı':relevant=any(t in str(r.get('generated_ref','')) for t in terms)
        if relevant:requests.append({'Kayıt':r['id'],'Personel':r.get('created_by_name',r.get('created_by')),'Talep':r.get('type'),'Başlangıç':a or 'Dönemlik','Bitiş':b or 'Dönemlik','Durum':r.get('status')})
    if requests:return {'kind':'requests','message':'Seçili döneme ait sonuçlanmamış talepler var. Talepler karara bağlanmadan vardiya atamasına veya otomatik planlamaya başlanamaz.','rows':requests}
    return None


def assert_can_plan(state,employees=None):
    if state.get("workspace_db_path"):refresh(state)
    problem=planning_problem(state,employees=employees)
    if problem:raise ValueError(problem['message'])


def render_guard(state):
    import streamlit as st
    if state.get("workspace_db_path"):refresh(state)
    problem=planning_problem(state)
    if not problem:return True
    st.warning(problem['message']);st.dataframe(problem['rows'],hide_index=True,use_container_width=True)
    destination='Yayın Yönetimi' if problem['kind']=='published' else 'Talepler'
    def open_page():
        from core.navigation import navigate
        navigate(state,'🗓️ Vardiya Planı');state['nav_roster']=destination
    if st.button(destination+' Ekranını Aç',key='guard_open_'+problem['kind'],on_click=open_page):st.rerun()
    token=hashlib.sha1(json.dumps([state.get('plan_ctx'),problem],default=str,ensure_ascii=False).encode()).hexdigest()
    if state.get('planning_guard_seen')!=token:
        state['planning_guard_seen']=token
        @st.dialog('Vardiya planlaması durduruldu')
        def warning():
            st.warning(problem['message']);st.dataframe(problem['rows'][:15],hide_index=True,use_container_width=True)
            if st.button('Anladım',key='guard_ack'):st.rerun()
        warning()
    return False

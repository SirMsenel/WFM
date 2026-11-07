from itertools import permutations
import pandas as pd
import streamlit as st

from .engine import generate_plan
from .planning_data import collect_inputs,fingerprint
from core.personnel import planner_people,WORK_LABELS
from core.planning import preview_plan,school_term
from core.planning_ui import period_banner,coverage_summary,render_shortages,render_issues
from core.workspace_store import save_keys

GROUP_LABELS=WORK_LABELS


def render_group_priority():
    rules=(st.session_state.get('shift_rules') or {}).get('work_type',{})
    if not rules:
        st.info('Önce mesai kurallarını tanımlayın.');return
    groups=list(rules);options=list(permutations(groups))
    saved=tuple(st.session_state.get('plan_group_priority') or groups)
    if saved not in options:saved=options[0]
    selected=st.selectbox('Otomatik yerleştirme önceliği',options,index=options.index(saved),
                          format_func=lambda order:' → '.join(GROUP_LABELS.get(g,g) for g in order),key='planning_priority_compact')
    st.session_state['plan_group_priority']=list(selected)
    st.caption('Kesin kayıtlar ve elle girişler korunur; kalan ihtiyaç bu sırayla tamamlanır.')
    rows=[]
    for group in selected:
        rule=rules[group]
        rows.append({'Grup':GROUP_LABELS.get(group,group),'Vardiya':f"{rule.get('shift_total_hours',rule.get('shift_total_hours_max'))} saat"+(" üst sınır" if 'shift_total_hours_max' in rule else ''),
                     'Haftalık gün':str(rule.get('max_days_per_week',rule.get('max_days_per_week_default','—'))),
                     'Dinlenme':f"{rule['min_rest_hours']} saat" if 'min_rest_hours' in rule else '—',
                     'Gece':'Uygun' if rule.get('night_allowed') else 'Uygun değil'})
    st.dataframe(rows,hide_index=True,use_container_width=True)


def render():
    state=st.session_state
    st.subheader('Oluştur, Kontrol Et ve Yayınla')
    if (state.get('profile') or {}).get('position') not in {'wfm','manager','moderator'}:
        st.info('Plan oluşturma ve yayınlama yönetim rolleri içindir.');return
    context=period_banner(state)
    if not context:return
    people=planner_people(state)
    render_group_priority()
    st.caption(f"{len(people)} personel otomatik alındı · Ders dönemi tarihe göre seçilir. Sınav günleri önceliklidir; diğer günlerde ilgili Bahar/Güz programı kullanılır.")
    with st.expander('Okul takvimi ve planlama koşulları'):
        st.write('Ocak: önceki yılın Güz dönemi. Şubat–Ağustos: Bahar. Eylül–Aralık: Güz. Sınav bitiş saati olmadığı için sınav günü tamamen kapatılır.')
        st.write('İhtiyaç dolmuş bir yarım saate otomatik ek personel atanmaz. Sabit vardiya süresi veya uygunluk nedeniyle kalan açıklar aşağıda gösterilir. Mola yerleşimi bu sürümde ayrıca modellenmez.')
    ready=bool(state.get('plan_ctx_confirmed') and people and state.get('plan_group_priority')
               and isinstance(state.get('sp_staffing_result_df'),pd.DataFrame) and not state['sp_staffing_result_df'].empty)
    if not ready:st.info('Dönemi onaylayın ve personel ihtiyacını hesaplayın.')
    if st.button('Otomatik Vardiya Taslağı Oluştur',disabled=not ready,key='planning_generate',type='primary'):
        try:
            with st.spinner('İhtiyaç ve uygunluklara göre yerleştiriliyor…'):
                staff,fixed,history,unavailable,source_issues=collect_inputs(state)
                result=generate_plan(staff,state['sp_staffing_result_df'],state['shift_rules'],state['plan_group_priority'],
                                     context['start'],context['end'],fixed=fixed,history=history,unavailable=unavailable,
                                     strict_capacity=True)
                result['issues']=source_issues+result['issues'];result['staff']=staff
                start,end=str(context['start']),str(context['end'])
                outside=[r for r in state.get('draft_shift_plan',[]) if not start<=str(r.get('date'))<=end]
                state['draft_shift_plan']=outside+result['plan']
                result['period']={'start':start,'end':end}
                state['planning_result']=result;state['planning_allow_gaps']=False
                state['planning_result_fingerprint']=fingerprint(state)
                save_keys(state)
            st.success('Taslak hazır. Takvimi Vardiya Saatleri ekranından da inceleyebilirsin.')
        except (ValueError,TypeError,KeyError) as exc:
            st.error(f'Plan oluşturulamadı: {exc}')
    result=state.get('planning_result')
    if result is None:
        if ready:
            try:
                current=preview_plan(state)
                coverage_summary(current,'Başlamadan Önce · Yerleştirilmiş Kayıtların Etkisi')
                with st.expander('Gece, izin ve mevcut kayıt kontrolleri'):render_issues(current)
            except ValueError as exc:st.info(str(exc))
        return
    stale=state.get('planning_result_fingerprint')!=fingerprint(state)
    if stale:st.warning('Kayıtlar veya kurallar değişti. Güncel sonucu yayınlamak için yeniden oluşturun.')
    coverage_summary(result,'Planın İhtiyacı Karşılama Durumu')
    render_shortages(result,'auto_gaps')
    with st.expander('Tüm atamalar ve 30 dakikalık karşılaştırma'):
        st.dataframe(pd.DataFrame(result['plan']),hide_index=True,use_container_width=True)
        st.dataframe(result['coverage'],hide_index=True,use_container_width=True)
    render_issues(result)
    roster=pd.DataFrame(result['plan'])
    st.download_button('Vardiya CSV İndir',roster.to_csv(index=False).encode('utf-8-sig'),'vardiya_taslagi.csv','text/csv')
    allow=False
    if result['coverage'].Eksik.sum():
        allow=st.checkbox('Gösterilen eksikleri inceleyerek bu haliyle yayınla',key='planning_allow_gaps')
    blocked=stale or bool(result['issues']) or (bool(result['coverage'].Eksik.sum()) and not allow)
    if st.button('Kontrol Edilen Planı Yayınla',disabled=blocked,key='planning_publish',type='primary'):
        start,end=result['period']['start'],result['period']['end']
        state['published_shift_plan']=[r for r in state.get('published_shift_plan',[]) if not start<=str(r.get('date'))<=end]+[dict(r) for r in result['plan']]
        state['planning_result_fingerprint']=fingerprint(state)
        save_keys(state)
        st.success('Plan yayınlandı ve veritabanına kaydedildi.')

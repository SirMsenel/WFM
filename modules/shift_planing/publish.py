from itertools import permutations
import pandas as pd
import streamlit as st

from .engine import generate_plan
from .planning_data import collect_inputs,fingerprint
from core.personnel import planner_people,WORK_LABELS
from core.planning import preview_plan,school_term
from core.planning_ui import period_banner,coverage_summary,render_shortages,render_issues,blocking_issues
from core.workspace_store import save_keys

GROUP_LABELS=WORK_LABELS


def render_group_priority():
    rules=(st.session_state.get('shift_rules') or {}).get('work_type',{})
    if not rules:
        st.info('Önce mesai kurallarını tanımlayın.');return
    groups=list(rules)
    selected=[g for g in st.session_state.get('plan_group_priority',groups) if g in groups]
    with st.expander('Grup sırasını seç · tıkladığın sırayla yerleştirilir'):
        if st.button('Sırayı Yeniden Seç',key='priority_reset'):
            st.session_state['plan_group_priority']=[];st.rerun()
        cols=st.columns(len(groups))
        for col,group in zip(cols,groups):
            if col.button(GROUP_LABELS.get(group,group),disabled=group in selected,key='priority_add_'+group):
                st.session_state['plan_group_priority']=selected+[group];st.rerun()
    st.markdown(' → '.join(f"**{i+1}. {GROUP_LABELS.get(g,g)}**" for i,g in enumerate(selected)) or 'Sıra boş; yukarıdan gruplara sırayla tıklayın.')
    if len(selected)<len(groups):st.info('Plan oluşturmadan önce tüm grupları sıraya ekleyin.')
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
    language=state.get('planning_languages',{'en':True,'ar':True})
    en,ar=st.columns(2)
    english=en.toggle('İngilizce personeller dahil',value=language.get('en',True),key='planning_include_en')
    arabic=ar.toggle('Arapça personeller dahil',value=language.get('ar',True),key='planning_include_ar')
    state['planning_languages']={'en':english,'ar':arabic}
    save_keys(state)
    st.caption('Kapalı dilin personelleri bu taslağa ve ihtiyaç karşılama hesabına katılmaz. Önceden yayınlanan vardiyaları korunur. İhtiyaç tahmini ortak havuzdur; dilin ayrı talebi burada tahmin edilmez.')
    st.caption(f"{len(people)} personel otomatik alındı · Ders dönemi tarihe göre seçilir. Sınav günleri önceliklidir; diğer günlerde ilgili Bahar/Güz programı kullanılır.")
    with st.expander('Okul takvimi ve planlama koşulları'):
        st.write('Ocak: önceki yılın Güz dönemi. Şubat–Ağustos: Bahar. Eylül–Aralık: Güz. Sınav bitiş saati olmadığı için sınav günü tamamen kapatılır.')
        st.write('İhtiyaç dolmuş bir yarım saate otomatik ek personel atanmaz. Sabit vardiya süresi veya uygunluk nedeniyle kalan açıklar aşağıda gösterilir. Mola yerleşimi bu sürümde ayrıca modellenmez.')
    ready=bool(state.get('plan_ctx_confirmed') and people and state.get('plan_group_priority')
               and len(state['plan_group_priority'])==len(state['shift_rules']['work_type'])
               and isinstance(state.get('sp_staffing_result_df'),pd.DataFrame) and not state['sp_staffing_result_df'].empty)
    if not ready:st.info('Dönemi onaylayın ve personel ihtiyacını hesaplayın.')
    if st.button('Otomatik Vardiya Taslağı Oluştur',disabled=not ready,key='planning_generate',type='primary'):
        try:
            with st.spinner('İhtiyaç ve uygunluklara göre yerleştiriliyor…'):
                staff,fixed,history,unavailable,source_issues=collect_inputs(state)
                result=generate_plan(staff,state['sp_staffing_result_df'],state['shift_rules'],state['plan_group_priority'],
                                     context['start'],context['end'],fixed=fixed,history=history,unavailable=unavailable,
                                     strict_capacity=True,hour_targets=state.get('group_hour_targets',[]),languages=state.get('planning_languages'))
                result['issues']=source_issues+result['issues'];result['staff']=staff
                start,end=str(context['start']),str(context['end'])
                included={str(e['employee_id']) for e in staff}
                outside=[r for r in state.get('draft_shift_plan',[]) if not start<=str(r.get('date'))<=end or str(r['employee_id']) not in included]
                state['draft_shift_plan']=outside+result['plan']
                result['period']={'start':start,'end':end}
                state['planning_result']=result;state['planning_allow_gaps']=False;state['planning_accept_warnings']=False
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
    hard=blocking_issues(result)
    warning_count=len(result.get('issues',[]))-len(hard)
    accept_warnings=st.checkbox('Gece kişi sayısı uyarılarını inceledim',key='planning_accept_warnings') if warning_count else True
    reasons=[]
    if stale:reasons.append('Kayıtlar değişti: Otomatik Vardiya Taslağı Oluştur düğmesine tekrar basın.')
    if hard:reasons.append(f'{len(hard)} kayıt/kural ihlali var: aşağıdaki açıklamalara göre düzeltin ve yeniden oluşturun.')
    if result['coverage'].Eksik.sum() and not allow:reasons.append('Kalan eksikleri kabul etmek için eksiklerle yayınlama kutusunu işaretleyin.')
    if not accept_warnings:reasons.append('Gece kişi sayısı uyarılarını incelediğinizi işaretleyin.')
    blocked=bool(reasons)
    if reasons:
        st.info('Yayınlamak için kalan adımlar:\n\n'+'\n\n'.join(reasons))
    if st.button('Kontrol Edilen Planı Yayınla',disabled=blocked,key='planning_publish',type='primary'):
        start,end=result['period']['start'],result['period']['end']
        included={str(e['employee_id']) for e in result['staff']}
        state['published_shift_plan']=[r for r in state.get('published_shift_plan',[]) if not start<=str(r.get('date'))<=end or str(r['employee_id']) not in included]+[dict(r) for r in result['plan']]
        state['planning_result_fingerprint']=fingerprint(state)
        save_keys(state)
        st.success('Plan yayınlandı ve veritabanına kaydedildi.')

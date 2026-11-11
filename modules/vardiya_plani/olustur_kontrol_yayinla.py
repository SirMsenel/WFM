# Vardiya Plani / Olustur Kontrol Yayinla — bu ekranın / servisin uygulama kodu.
from itertools import permutations
import pandas as pd
import streamlit as st

from modules.vardiya_plani.vardiya_motoru import generate_plan
from modules.vardiya_plani.planlama_verileri import collect_inputs,fingerprint
from ortak.personel import planner_people,WORK_LABELS
from ortak.planlama import preview_plan,school_term
from ortak.planlama_gorunumu import period_banner,coverage_summary,render_shortages,render_issues,blocking_issues,coverage_controls
from ortak.calisma_alani_deposu import save_keys

GROUP_LABELS=WORK_LABELS


def render_group_priority():
    rules=(st.session_state.get('shift_rules') or {}).get('work_type',{})
    if not rules:
        st.info('Önce mesai kurallarını tanımlayın.');return
    groups=list(rules)
    st.session_state.setdefault('plan_group_priority',groups)
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
    for col,row in zip(st.columns(max(1,len(rows))),rows):
        from html import escape
        content=''.join('<div style="font-size:12px;margin-top:8px">'+escape(k)+': <b>'+escape(str(v))+'</b></div>' for k,v in row.items() if k!='Grup')
        col.markdown('<div style="border:1px solid #d6e5ed;border-top:4px solid #4b94a2;background:#f5fafc;border-radius:16px;padding:16px;min-height:175px"><b>'+escape(row['Grup'])+'</b>'+content+'</div>',unsafe_allow_html=True)



def render():
    state=st.session_state
    st.subheader('Oluştur, Kontrol Et ve Yayınla')
    if (state.get('profile') or {}).get('position') not in {'wfm','manager','assistant_manager','moderator','planning_manager'}:
        st.info('Plan oluşturma ve yayınlama yönetim rolleri içindir.');return
    context=period_banner(state)
    if not context:return
    coverage_controls(state)
    people=planner_people(state)
    if state.get('publication_notice'):st.success(state.pop('publication_notice'))
    render_group_priority()
    language=state.get('planning_languages',{'en':True,'ar':True})
    tr,en,ar=st.columns(3)
    turkish=tr.toggle('Türkçe personeller dahil',value=language.get('tr',True),key='planning_include_tr')
    english=en.toggle('İngilizce personeller dahil',value=language.get('en',True),key='planning_include_en')
    arabic=ar.toggle('Arapça personeller dahil',value=language.get('ar',True),key='planning_include_ar')
    state['planning_languages']={'tr':turkish,'en':english,'ar':arabic}
    save_keys(state)
    st.caption('Kapalı dilin personelleri bu taslağa ve ihtiyaç karşılama hesabına katılmaz. Önceden yayınlanan vardiyaları korunur. İhtiyaç tahmini ortak havuzdur; dilin ayrı talebi burada tahmin edilmez.')
    st.caption(f"{len(people)} personel otomatik alındı · Ders dönemi tarihe göre seçilir. Sınav günleri önceliklidir; diğer günlerde ilgili Bahar/Güz programı kullanılır.")
    from ortak.donem_kilitleri import render_guard
    if not render_guard(state):return
    exam=st.toggle('Sınav gününde saat bilgisi varsa diğer uygun saatlere vardiya yaz',value=state.get('planning_exam_hours',False),key='planning_exam_hours_toggle')
    state['planning_exam_hours']=exam;save_keys(state)
    st.caption('Sınav başlangıç ve bitişi varsa yalnızca o saatler kapanır. Bitiş bilinmiyorsa gün tamamen kapalı kalır.')
    ready=bool(state.get('plan_ctx_confirmed') and people and state.get('plan_group_priority')
               and len(state['plan_group_priority'])==len(state['shift_rules']['work_type'])
               and isinstance(state.get('sp_staffing_result_df'),pd.DataFrame) and not __import__('ortak.plan_ihtiyaci',fromlist=['demand']).demand(state).empty)
    if not ready:st.info('Dönemi onaylayın ve personel ihtiyacını hesaplayın.')
    if st.button('Otomatik Vardiya Taslağı Oluştur',disabled=not ready,key='planning_generate',type='primary'):
        try:
            with st.spinner('İhtiyaç ve uygunluklara göre yerleştiriliyor…'):
                from ortak.donem_kilitleri import assert_can_plan
                assert_can_plan(state)
                staff,fixed,history,unavailable,source_issues=collect_inputs(state)
                result=generate_plan(staff,__import__('ortak.plan_ihtiyaci',fromlist=['demand']).demand(state),state['shift_rules'],state['plan_group_priority'],
                                     context['start'],context['end'],fixed=fixed,history=history,unavailable=unavailable,
                                     strict_capacity=True,hour_targets=state.get('group_hour_targets',[]),languages=state.get('planning_languages'),exclude_early_hours=state.get('planning_exclude_early_hours',False))
                from ortak.statuler import meal_plan
                meals,coverage,meal_issues=meal_plan(state,result['plan'],result['coverage'],staff)
                result['breaks']=meals;result['coverage']=coverage
                result['issues']=source_issues+result['issues']+meal_issues;result['staff']=staff
                start,end=str(context['start']),str(context['end'])
                included={str(e['employee_id']) for e in staff}
                outside=[r for r in state.get('draft_shift_plan',[]) if not start<=str(r.get('date'))<=end or str(r['employee_id']) not in included]
                state['draft_shift_plan']=outside+result['plan']
                result['period']={'start':start,'end':end}
                state['planning_result']=result;state['planning_allow_gaps']=False;state['planning_accept_warnings']=False;state['planning_accept_soft']=False;state['planning_soft_consent']=False
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
    render_issues(result)
    if result.get('issues'):
        from ortak.cakisma_temizleme import propose_cleanup
        propose_cleanup(state,[(r.get('employee_id'),r.get('date')) for r in result['issues']],'publish')
    roster=pd.DataFrame(result['plan'])
    st.download_button('Vardiya CSV İndir',roster.to_csv(index=False).encode('utf-8-sig'),'vardiya_taslagi.csv','text/csv')
    hard=blocking_issues(result)
    warnings=len(result.get('issues',[]))-len(hard)
    has_gaps=bool(result['coverage'].Eksik.sum())
    soft=any(r.get('severity')=='warning' and r.get('override_required',True) for r in result.get('issues',[]))
    if soft:state['planning_accept_soft']=st.checkbox('Esnek kural aşımlarını inceledim ve onaylıyorum',value=False,key='planning_soft_consent')
    reasons=[]
    if soft and not state.get('planning_accept_soft'):reasons.append('Esnek kural aşımları için onay verin.')
    if stale:reasons.append('Kayıtlar değişti: Otomatik Vardiya Taslağı Oluştur düğmesine tekrar basın.')
    if hard:reasons.append(f'{len(hard)} kayıt/kural ihlali var. Yukarıdaki tabloda Mevcut vardiya ve Olması gereken sütunlarını karşılaştırarak düzeltin, sonra yeniden oluşturun.')
    if reasons:st.info('Yayınlamak için kalan adımlar:\n\n'+'\n\n'.join(reasons))
    if has_gaps or warnings:st.caption('Plan, kalan ihtiyaç ve uyarılarla birlikte yayın onayına gönderilir. İki ayrı planlamacının onayı gerekir; eksik %5 üzerindeyse Planlama Yöneticisi de onaylar.')
    label='Taslağı Yayın Onayına Gönder' if state.get('shift_rules',{}).get('publication_approvals',{}).get('enabled') else ('Eksikleri Kabul Et ve Planı Yayınla' if has_gaps or warnings else 'Kontrol Edilen Planı Yayınla')
    if st.button(label,disabled=bool(reasons),key='planning_publish',type='primary'):
        try:
            from ortak.yayin_servisi import publish_plan
            if state.get('shift_rules',{}).get('publication_approvals',{}).get('enabled'):
                from ortak.yayin_onaylari import submit
                ident=submit(state,result);st.success('Taslak onaya gönderildi: '+ident+' · Yayın Onayları ekranında iki bağımsız Planlama onayı bekleniyor.');return
            publish_plan(state,result)
            st.success('Vardiya tablosu yayınlandı ve veritabanına kaydedildi. Personeller Benim Vardiyam ekranından görebilir.')
        except (ValueError,OSError) as exc:st.error(str(exc))
    receipt=state.get('last_publication')
    if receipt and receipt['start']==result['period']['start'] and receipt['end']==result['period']['end'] and not stale and receipt.get('fingerprint')==state.get('planning_result_fingerprint'):
        from ortak.planlama import calendar_grid
        st.markdown('### Yayınlanan Vardiya Tablosu')
        st.caption(f"{receipt['start']} – {receipt['end']} · {receipt['count']} personel/gün kaydı")
        ids={str(e['employee_id']) for e in result['staff']}
        published=[r for r in state.get('published_shift_plan',[]) if str(r['employee_id']) in ids and receipt['start']<=str(r['date'])<=receipt['end']]
        grid=calendar_grid({**result,'source_rows':published,'exam_keys':set()},result['period'])
        from ortak.vardiya_gorunumu import cell_style
        st.dataframe(grid.style.map(cell_style,subset=[c for c in grid if c not in {'Personel','Sicil no','Kullanıcı adı'}]),hide_index=True,use_container_width=True,height=500)

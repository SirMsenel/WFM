# Vardiya Plani / Olustur Kontrol Yayinla — bu ekranın / servisin uygulama kodu.
from itertools import permutations
import pandas as pd
import streamlit as st

from modules.vardiya_plani.vardiya_motoru import generate_plan
from modules.vardiya_plani.planlama_verileri import collect_inputs,fingerprint
from ortak.personel import planner_people,WORK_LABELS
from ortak.planlama import preview_plan,school_term
from ortak.planlama_gorunumu import period_banner,coverage_summary,render_shortages,render_issues,blocking_issues,coverage_controls,roster_summary
from ortak.calisma_alani_deposu import save_keys

GROUP_LABELS=WORK_LABELS


def status_scope(plan,staff,fixed):
    """Türkçe statülerine, yabancı dilde zaten planlanan kişileri katma."""
    foreign_ids={str(row['employee_id']) for row in fixed if row.get('source')=='foreign_language_plan'}
    return ([row for row in plan if str(row.get('employee_id')) not in foreign_ids],
            [person for person in staff if str(person.get('employee_id')) not in foreign_ids])


def foreign_plan_period_summary(state,context,lang):
    """Dönemdeki bağımsız dil planını ve ana plana taşınan net etkisini özetle."""
    start,end=str(context['start']),str(context['end'])
    result=(state.get('foreign_language_plans') or {}).get(lang) or {}
    period=result.get('period') or {}
    planned=str(period.get('start'))==start and str(period.get('end'))==end
    selected={str(eid) for eid in (state.get('foreign_language_transferred_ids') or {}).get(lang,[])}
    rows=[row for row in state.get('draft_shift_plan',[])
          if row.get('source')=='foreign_language_plan' and row.get('language')==lang
          and str(row.get('employee_id')) in selected and start<=str(row.get('date'))<=end]
    from modules.vardiya_plani.vardiya_motoru import bounds
    active=[row for row in rows if bounds(row)]
    hours=sum((bounds(row)[1]-bounds(row)[0]).total_seconds()/3600 for row in active)
    return {'planned':planned,'planned_people':len(result.get('staff',[])) if planned else 0,
            'impact_people':len({str(row['employee_id']) for row in active}),
            'impact_shifts':len(active),'impact_hours':hours}


def render_foreign_plan_status(state,context):
    columns=st.columns(2,gap='small')
    for column,(lang,label,color) in zip(columns,[('en','İngilizce','#3c7ca6'),('ar','Arapça','#8a62a8')]):
        item=foreign_plan_period_summary(state,context,lang)
        badge='Planlandı' if item['planned'] else 'Planlanmadı'
        badge_bg='#e4f5ec' if item['planned'] else '#f2f3f5'
        badge_color='#26704d' if item['planned'] else '#6d7680'
        with column:
            st.markdown(f'''<div style="min-height:122px;padding:14px 16px;border-radius:16px;background:linear-gradient(135deg,#fff,#f7f9fb);border:1px solid #dfe7eb;box-shadow:0 4px 14px rgba(42,66,78,.06)">
            <div style="display:flex;align-items:center;justify-content:space-between;gap:8px"><b style="color:{color}">{label} Dil Planı</b><span style="padding:4px 9px;border-radius:999px;background:{badge_bg};color:{badge_color};font-size:12px;font-weight:700">{badge}</span></div>
            <div style="margin-top:11px;color:#536873;font-size:13px">Plan kapsamı <b>{item['planned_people']} kişi</b></div>
            <div style="margin-top:5px;color:#263f4a;font-size:13px">Türkçe ihtiyaç etkisi <b>{item['impact_people']} kişi · {item['impact_shifts']} vardiya · {item['impact_hours']:g} saat</b></div>
            </div>''',unsafe_allow_html=True)


def render_group_priority():
    rules=(st.session_state.get('shift_rules') or {}).get('work_type',{})
    if not rules:
        st.info('Önce mesai kurallarını tanımlayın.');return
    groups=list(rules)
    st.session_state.setdefault('plan_group_priority',groups)
    selected=[g for g in st.session_state.get('plan_group_priority',groups) if g in groups]
    st.markdown('''<style>.st-key-placement-priority button{min-height:38px!important;border-radius:12px!important}.st-key-placement-priority [data-testid="stHorizontalBlock"]{gap:.45rem!important}</style>''',unsafe_allow_html=True)
    with st.container(key='placement-priority'):
        title,content=st.columns([1.05,3.95],vertical_alignment='center',gap='small')
        title.markdown('<div style="padding:9px 12px;border-radius:13px;background:linear-gradient(120deg,#e8f5f5,#f4eef9);border:1px solid #d7e7e8"><b style="font-size:13px;color:#315e68">Yerleştirme Önceliği</b><br><small style="color:#6a7f87">Kartlara sırayla dokun</small></div>',unsafe_allow_html=True)
        ordered=selected+[g for g in groups if g not in selected]
        with content:
            for col,group in zip(st.columns(len(ordered),gap='small'),ordered):
                rank=str(selected.index(group)+1) if group in selected else '○'
                if col.button(rank+' · '+GROUP_LABELS.get(group,group),key='priority_add_'+group,type='primary' if group in selected else 'secondary',use_container_width=True,help='Seçimi kaldırmak veya sıranın sonuna eklemek için tıkla'):
                    st.session_state['plan_group_priority']=([g for g in selected if g!=group] if group in selected else selected+[group]);st.rerun()
    if len(selected)<len(groups):st.info('Plan oluşturmadan önce tüm grupları sıraya ekleyin.')



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
    with st.expander('Otomatik vardiya motoru nasıl yerleştirir?'):
        st.markdown('''Motor, önce kesin kayıtları (onaylı izin/talep, gece, ders-sınav ve elle girilmiş vardiya) korur. Ardından seçtiğin grup sırasına göre her personel için yarım saatlik ihtiyaç açığını en çok azaltan vardiyayı dener. Her denemede dil, çalışma grubu, işe giriş/ayrılış tarihi, 11 saat dinlenme, en fazla ardışık gün, haftalık OFF, ders/sınav, gece, Cuma kuralı, vardiya süresi ve dönem hedefleri kontrol edilir. Son aşamada yemek ve mola hakları otomatik dağıtılır; açıklar ile kural ihlalleri yayın öncesinde ayrıca gösterilir.''')
        st.caption('Bu yaklaşım kural-temelli ve deterministiktir: aynı veri ve kuralla aynı sonucu üretir. Küresel matematiksel optimum garantisi yerine, uygulanabilir en yüksek yerel ihtiyaç kazanımını hedefler.')
    # Ana motor Türkçe planı oluşturur. Yabancı dil kapasitesi yalnızca bağımsız
    # dil planında kişi bazında ana plana aktarılan sabit vardiyalardan gelir.
    language_scope={'tr':True,'en':False,'ar':False}
    if state.get('planning_languages')!=language_scope:
        state['planning_languages']=language_scope;save_keys(state)
    render_foreign_plan_status(state,context)
    from ortak.donem_kilitleri import render_guard
    if not render_guard(state):return
    exam=st.toggle('Sınav gününde saat bilgisi varsa diğer uygun saatlere vardiya yaz',value=state.get('planning_exam_hours',False),key='planning_exam_hours_toggle')
    state['planning_exam_hours']=exam;save_keys(state)
    state['planning_allow_hour_target_override']=st.checkbox('Dönem çalışma süresi hedefi aşılsa da uygun personeli yerleştirmeye devam et',value=state.get('planning_allow_hour_target_override',False),key='planning_hour_target_override')
    if state['planning_allow_hour_target_override']:st.warning('Bu taslakta hedef çalışma süresi aşılabilir. Yayın öncesinde aşan personeller kural kontrolünde ayrıca gösterilir.')
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
                                     strict_capacity=True,hour_targets=() if state.get('planning_allow_hour_target_override') else state.get('group_hour_targets',[]),languages=state.get('planning_languages'),exclude_early_hours=state.get('planning_exclude_early_hours',False),
                                     auto_night=state.get('shift_rules',{}).get('night',{}).get('auto_fill',True),
                                     auto_excluded_ids={str(eid) for ids in ((state.get('foreign_language_reserved_ids') or state.get('foreign_language_transferred_ids') or {})).values() for eid in ids})
                from ortak.statuler import meal_plan
                # Yabancı dil vardiyaları burada yalnızca Türkçe ihtiyacından
                # düşülecek yarım saatlik kapasitedir. Kendi yemek/molaları
                # bağımsız dil planında kalır ve Türkçe statü planına girmez.
                status_plan,status_staff=status_scope(result['plan'],staff,fixed)
                meals,coverage,meal_issues=meal_plan(state,status_plan,result['coverage'],status_staff)
                result['breaks']=meals;result['coverage']=coverage
                result['issues']=source_issues+result['issues']+meal_issues;result['staff']=staff
                locked={(str(r['employee_id']),str(r['date'])):(r.get('shift_code'),r.get('start'),r.get('end')) for r in fixed if r.get('source')=='foreign_language_plan'}
                actual={(str(r['employee_id']),str(r['date'])):(r.get('shift_code'),r.get('start'),r.get('end')) for r in result['plan']}
                changed=[key for key,value in locked.items() if actual.get(key)!=value]
                if changed:raise ValueError('Ana motor, aktarılan yabancı dil vardiyasını koruyamadı. Dil planı değiştirilmeden işlem durduruldu.')
                start,end=str(context['start']),str(context['end'])
                included={str(e['employee_id']) for e in staff}
                outside=[r for r in state.get('draft_shift_plan',[]) if not start<=str(r.get('date'))<=end or str(r['employee_id']) not in included]
                state['draft_shift_plan']=outside+result['plan']
                result['period']={'start':start,'end':end}
                state['planning_result']=result;state['planning_allow_gaps']=False;state['planning_accept_warnings']=False;state['planning_accept_soft']=False;state['planning_accept_hard']=False;state['planning_soft_consent']=False
                state['planning_result_fingerprint']=fingerprint(state)
                save_keys(state)
            st.success('Taslak hazır. Aşağıdaki raporu inceleyebilir; düzeltme ve yayın işlemleri için Taslak Aksiyonları ekranına geçebilirsin.')
        except (ValueError,TypeError,KeyError) as exc:
            st.error(f'Plan oluşturulamadı: {exc}')
    if st.button('Otomatik Taslağı Sıfırla',key='planning_reset'):
        start,end=str(context['start']),str(context['end']);included={str(p['employee_id']) for p in people}
        state['draft_shift_plan']=[r for r in state.get('draft_shift_plan',[]) if not (r.get('source')=='auto' and start<=str(r.get('date'))<=end and str(r['employee_id']) in included)]
        for key in ('planning_result','planning_result_fingerprint','_status_plan_cache'):state.pop(key,None)
        save_keys(state);st.rerun()
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
    roster_summary(result,'Otomatik Taslak · Grup Kapasitesi ve Atamalar')
    coverage_summary(result,'Planın İhtiyacı Karşılama Durumu')
    render_shortages(result,'auto_gaps',actions=False)
    render_issues(result)
    if result.get('issues'):
        from ortak.cakisma_temizleme import propose_cleanup
        propose_cleanup(state,[(r.get('employee_id'),r.get('date')) for r in result['issues']],'publish')
    roster=pd.DataFrame(result['plan'])
    st.download_button('Vardiya CSV İndir',roster.to_csv(index=False).encode('utf-8-sig'),'vardiya_taslagi.csv','text/csv')
    st.divider()
    st.markdown('### Düzeltme ve Yayın Aşaması')
    st.caption('Sistem önerileri, personel/saat değişiklikleri ve yayın onayı Taslak Aksiyonları ekranında birlikte yönetilir.')
    if st.button('Taslak Aksiyonlarına Geç',key='planning_open_draft_actions',type='primary',use_container_width=True):
        from ortak.gezinme import select_section
        select_section(state,'nav_roster','Taslak Aksiyonları');st.rerun()
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

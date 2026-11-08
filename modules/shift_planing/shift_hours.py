"""Selected-period roster workbench: source records, manual placement and coverage."""
from datetime import time
import pandas as pd
import streamlit as st

from core.planning import preview_plan,calendar_grid,SHIFT_LABELS,LEAVE_LABELS
from core.planning_ui import period_banner,coverage_summary,render_shortages,render_issues,coverage_controls
from core.shift_edits import edit_shifts,undo_edit
from core.personnel import planner_people,WORK_LABELS
from core.navigation import sections


SOURCE_LABELS={'fixed_external':'Kesin kayıt','approved_request':'Onaylı talep','published_fixed':'Mevcut plan',
               'manual':'Elle giriş','manual_single':'Elle giriş','manual_template':'Elle giriş','auto':'Otomatik'}


def _cell_style(value):
    from core.shift_display import cell_style
    return cell_style(value)


def _manual_form(state,result,context):
    from core.manual_assignments import prepare_manual
    people={str(e['employee_id']):e for e in result['staff']}
    with st.expander('Elle Vardiya veya İzin Ekle',expanded=True):
        mode=st.radio('Kimlere yazılacak?',['Personel seç','Grup seç'],horizontal=True,key='manual_pick_mode')
        if mode=='Grup seç':
            groups=st.multiselect('Çalışma grupları',list(WORK_LABELS),format_func=WORK_LABELS.get,key='manual_groups')
            picked=[eid for eid,e in people.items() if e['work_type'] in groups]
            st.caption(f'{len(picked)} personel seçildi. Dolu günler korunur; yalnızca kurallara uygun boş günler yerleştirilir.')
        else:
            picked=st.multiselect('Yerleştirilecek personeller',list(people),format_func=lambda eid:f"{people[eid].get('full_name',eid)} · {WORK_LABELS.get(people[eid].get('work_type'),'')}",key='manual_people_v2')
        kind=st.selectbox('Kayıt türü',['WORK','OFF',*LEAVE_LABELS,'GECE','MESAI'],format_func=lambda k:SHIFT_LABELS[k],key='manual_kind_v2')
        working=kind in {'WORK','GECE','MESAI'}
        custom=st.checkbox('Bitiş saatini kendim belirleyeceğim',value=kind=='MESAI',key='manual_custom_end_v2') if working else False
        start,end=pd.Timestamp(context['start']).date(),pd.Timestamp(context['end']).date()
        dates=st.date_input('Uygulanacak gün aralığı',value=(start,end),min_value=start,max_value=end,key=f'manual_dates_{start}_{end}')
        begin,finish=None,None
        if working:
            a,b=st.columns(2)
            begin=a.time_input('Başlangıç saati',value=time.fromisoformat(state['shift_rules']['general']['night_window_start']) if kind=='GECE' else time(8),key=f'manual_begin_{kind}')
            if custom:finish=b.time_input('Bitiş saati',value=time(18),key=f'manual_finish_{kind}')
            else:b.caption('Gece saatleri mesai kurallarından; diğer bitiş saatleri personelin grup süresinden hesaplanır.')
        note=st.text_input('Not',key='manual_note_v2')
        additions=[];warnings=[]
        if picked and len(dates)==2:
            try:additions,warnings=prepare_manual(state,picked,dates[0],dates[1],kind,begin,finish,note)
            except (ValueError,TypeError,KeyError) as exc:st.error(str(exc))
        if warnings:
            st.warning(f'{len(warnings)} gün/kural kontrolü nedeniyle bazı girişler yazılmayacak. Mevcut vardiyalar değiştirilmez.')
            st.dataframe(warnings,hide_index=True,use_container_width=True)
            from core.conflict_cleanup import propose_cleanup
            propose_cleanup(state,[(r['Personel No'],r['Tarih']) for r in warnings],'manual')
        if additions:st.caption(f'{len(additions)} boş ve uygun güne yerleştirme yapılacak.')
        if st.button('Seçili Günlere Yerleştir',disabled=not additions,type='primary',key='manual_place'):
            edit_shifts(state,additions)
            state['shift_notice']=f'{len(additions)} kayıt yerleştirildi. Dolu veya kurala aykırı günler korunarak atlandı.'
            st.rerun()


def _record_table(rows):
    return pd.DataFrame([{'Personel':r.get('full_name',r['employee_id']),'Tarih':r['date'],
                          'Kayıt':SHIFT_LABELS.get(r.get('shift_code'),r.get('shift_code')),
                          'Saat':f"{r['start']}–{r['end']}" if r.get('start') and r.get('end') else 'Tüm gün',
                          'Kaynak':SOURCE_LABELS.get(r.get('source'),r.get('source')),'Not':r.get('note','')} for r in rows])


def _edit_controls(state,result):
    a,b=st.columns([1,3])
    if a.button('Son Elle İşlemi Geri Al',disabled=not state.get('shift_edit_history'),key='shift_undo'):
        try:
            undo_edit(state);state['shift_notice']='Son elle işlem geri alındı.';st.rerun()
        except ValueError as exc:st.error(str(exc))
    b.caption('Kesin gece/izin ve onaylı talep kayıtları kaynaklarından değiştirilir. Elle girişler aşağıdan seçilerek silinebilir.')
    with st.expander('Elle Girişleri Seç ve Sil'):
        rows=[r for r in result['source_rows'] if r.get('source') in {'manual','manual_single','manual_template'}]
        if not rows:
            st.caption('Seçili dönemde elle girilmiş kayıt yok.');return
        table=_record_table(rows)
        event=st.dataframe(table,hide_index=True,use_container_width=True,on_select='rerun',selection_mode='multi-row',key='manual_delete_rows')
        indices=[i for i in event.selection.rows if i<len(rows)]
        if st.button('Seçilen Elle Girişleri Sil',disabled=not indices,key='shift_delete'):
            try:
                edit_shifts(state,deletions=[(rows[i]['employee_id'],rows[i]['date']) for i in indices])
                state['shift_notice']=f'{len(indices)} elle giriş silindi.';st.rerun()
            except ValueError as exc:st.error(str(exc))


def render():
    state=st.session_state
    st.subheader('Vardiya Saatleri ve Yerleştirmeler')
    context=period_banner(state)
    if not context:return
    coverage_controls(state)
    state['planning_exam_hours']=st.toggle('Sınav saatleri dışında vardiya yazılabilsin',value=state.get('planning_exam_hours',False),key='manual_exam_hours_toggle')
    from core.workspace_store import save_keys
    save_keys(state)
    planner_people(state)
    try:result=preview_plan(state,include_auto=True)
    except (ValueError,KeyError) as exc:
        st.info(str(exc));return
    if state.get('shift_notice'):st.success(state.pop('shift_notice'))
    from core.planning_guard import render_guard
    coverage_summary(result)
    if not render_guard(state):return
    _manual_form(state,result,context)
    _edit_controls(state,result)
    def show_calendar():
        st.markdown('### Seçili Dönem Takvimi')
        query=st.text_input('Takvimde personel ara',key='shift_calendar_search')
        grid=calendar_grid(result,context)
        if query:grid=grid[grid.Personel.str.contains(query,case=False,regex=False)]
        dates=[c for c in grid if c!='Personel']
        st.dataframe(grid.style.map(_cell_style,subset=dates),hide_index=True,use_container_width=True,height=570)
        st.caption('Yeşil: çalışma · Mor: gece · Pembe: izin/rapor · Sarı: sınav · —: henüz yerleştirilmedi')
    def show_night():
        rows=[r for r in result['source_rows'] if r.get('shift_code')=='GECE']
        st.markdown('### Gece Vardiyasına Yerleştirilmiş Personel')
        if rows:
            ids={r['employee_id'] for r in rows}
            grid=calendar_grid({**result,'staff':[e for e in result['staff'] if str(e['employee_id']) in ids],'source_rows':rows},context)
            st.dataframe(grid.style.map(_cell_style,subset=[c for c in grid if c!='Personel']),hide_index=True,use_container_width=True,height=500)
        else:st.warning('Bu dönem için gece vardiyası kaydı yok.')
        night_issues=[r for r in result['issues'] if 'Gece' in r.get('Sorun','') or 'gece' in r.get('Sorun','')]
        if night_issues:render_issues({**result,'issues':night_issues})
        elif state['shift_rules'].get('night',{}).get('enabled'):st.success('Tanımlı gece kontrolleri sağlanıyor.')
    sections('nav_shift_workbench',{'Takvim':show_calendar,'Gece Kontrolü':show_night,'Kalan İhtiyaç':lambda:render_shortages(result,'manual_gaps')})
    # Show actual errors immediately, even when another subview is selected.
    if result['issues']:
        with st.expander("Kayıtlardaki uyuşmazlıklar ve düzeltme adımları",expanded=True):render_issues(result)
        from core.conflict_cleanup import propose_cleanup
        propose_cleanup(state,[(r.get('employee_id'),r.get('date')) for r in result['issues']],'issues')

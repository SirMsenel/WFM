"""Selected-period roster workbench: source records, manual placement and coverage."""
from datetime import time
import pandas as pd
import streamlit as st

from core.planning import preview_plan,calendar_grid,SHIFT_LABELS,LEAVE_LABELS
from core.planning_ui import period_banner,coverage_summary,render_shortages,render_issues
from core.shift_edits import edit_shifts,undo_edit
from core.personnel import planner_people,WORK_LABELS
from core.navigation import sections


SOURCE_LABELS={'fixed_external':'Kesin kayıt','approved_request':'Onaylı talep','published_fixed':'Mevcut plan',
               'manual':'Elle giriş','manual_single':'Elle giriş','manual_template':'Elle giriş','auto':'Otomatik'}


def _cell_style(value):
    text=str(value)
    if '⚠' in text:return 'background-color:#fee2e2;color:#991b1b;font-weight:600'
    if 'Sınav' in text:return 'background-color:#fef3c7;color:#92400e'
    if 'Gece' in text:return 'background-color:#e0e7ff;color:#3730a3'
    if any(word in text for word in ['izin','Rapor']):return 'background-color:#fce7f3;color:#9d174d'
    if text=='OFF':return 'background-color:#f1f5f9;color:#64748b'
    if '–' in text:return 'background-color:#dff5ed;color:#065f46'
    return 'color:#b0bac5'


def _manual_form(state,result,context):
    people={str(e['employee_id']):e for e in result['staff']}
    with st.expander('Elle Vardiya veya İzin Ekle',expanded=True):
        picked=st.multiselect('Yerleştirilecek personeller',list(people),
                              format_func=lambda eid:f"{people[eid].get('full_name',eid)} · {WORK_LABELS.get(people[eid].get('work_type'),'')}",key='manual_people_v2')
        kind=st.selectbox('Kayıt türü',['WORK','OFF',*LEAVE_LABELS,'GECE','MESAI'],format_func=lambda k:SHIFT_LABELS[k],key='manual_kind_v2')
        working=kind in {'WORK','GECE','MESAI'}
        custom=st.checkbox('Bitiş saatini kendim belirleyeceğim',value=kind=='MESAI',key='manual_custom_end_v2') if working else False
        with st.form('manual_assignment_v2'):
            start,end=pd.Timestamp(context['start']).date(),pd.Timestamp(context['end']).date()
            dates=st.date_input('Uygulanacak gün aralığı',value=(start,end),min_value=start,max_value=end,key=f'manual_dates_{start}_{end}')
            begin,finish=None,None
            if working:
                a,b=st.columns(2)
                begin=a.time_input('Başlangıç saati',value=time(0) if kind=='GECE' else time(8),key=f'manual_begin_{kind}')
                if custom:
                    finish=b.time_input('Bitiş saati',value=time(18),key=f'manual_finish_{kind}')
                else:
                    b.caption('Bitiş saati her personelin grup süresinden hesaplanır. Dış kaynak 10 saat, Full Time 9 saat; Akademi kendi üst sınırına göre.')
            note=st.text_input('Not',key='manual_note_v2')
            save=st.form_submit_button('Seçili Günlere Yerleştir',disabled=not picked,type='primary')
        if save:
            if len(dates)!=2:
                st.error('Başlangıç ve bitiş gününü seçin.');return
            protected={(r['employee_id'],r['date']) for r in result['source_rows'] if r.get('source') in {'fixed_external','approved_request','published_fixed'}}
            additions=[];skipped=0
            for eid in picked:
                rule=state['shift_rules']['work_type'][people[eid]['work_type']]
                for day in pd.date_range(dates[0],dates[1]):
                    key=(eid,str(day.date()))
                    if key in protected or (working and key in result['exam_keys']):
                        skipped+=1;continue
                    a,b=None,None
                    if working:
                        a=begin.strftime('%H:%M')
                        if custom:
                            b=finish.strftime('%H:%M')
                        else:
                            hours=rule.get('shift_total_hours',rule.get('shift_total_hours_max',7))
                            minute=begin.hour*60+begin.minute+int(float(hours)*60)
                            b=f'{(minute//60)%24:02d}:{minute%60:02d}'
                    additions.append({'employee_id':eid,'date':str(day.date()),'group':people[eid]['work_type'],'shift_code':kind,
                                      'start':a,'end':b,'source':'manual_single','note':note})
            if not additions:
                st.warning('Seçili günlerdeki kesin kayıt veya sınavlar nedeniyle yeni atama yapılamadı.');return
            try:
                edit_shifts(state,additions)
                state['shift_notice']=f'{len(additions)} kayıt yerleştirildi. {skipped} kesin kayıt/sınav günü korundu.'
                st.rerun()
            except (ValueError,TypeError) as exc:
                st.error(str(exc))


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
    planner_people(state)
    try:result=preview_plan(state,include_auto=True)
    except (ValueError,KeyError) as exc:
        st.info(str(exc));return
    if state.get('shift_notice'):st.success(state.pop('shift_notice'))
    coverage_summary(result)
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
    def show_sources():
        rows=[r for r in result['source_rows'] if r.get('source')!='auto']
        st.markdown('### Otomatik Gelen ve Elle Girilen Kayıtlar')
        if rows:st.dataframe(_record_table(rows),hide_index=True,use_container_width=True)
        else:st.info('Seçili dönemde kaynak kayıt yok.')
        if result['exam_keys']:
            names={str(e['employee_id']):e.get('full_name') for e in result['staff']}
            st.markdown('#### Sınav Nedeniyle Kapalı Günler')
            st.dataframe([{'Personel':names.get(eid,eid),'Tarih':day,'Kayıt':'Sınav'} for eid,day in sorted(result['exam_keys'])],hide_index=True,use_container_width=True)
        render_issues(result)
    def show_night():
        rows=[r for r in result['source_rows'] if r.get('shift_code')=='GECE']
        st.markdown('### Gece Vardiyasına Yerleştirilmiş Personel')
        if rows:st.dataframe(_record_table(rows),hide_index=True,use_container_width=True)
        else:st.warning('Bu dönem için gece vardiyası kaydı yok.')
        night_issues=[r for r in result['issues'] if 'Gece' in r.get('Sorun','') or 'gece' in r.get('Sorun','')]
        if night_issues:st.error('Gece yerleştirmelerinde eksik veya uyuşmazlık var.');st.dataframe(night_issues,hide_index=True,use_container_width=True)
        elif state['shift_rules'].get('night',{}).get('enabled'):st.success('Tanımlı gece kontrolleri sağlanıyor.')
    sections('nav_shift_workbench',{'Takvim':show_calendar,'Kayıtlar ve İzinler':show_sources,'Gece Kontrolü':show_night,'Kalan İhtiyaç':lambda:render_shortages(result,'manual_gaps')})
    # Show actual errors immediately, even when another subview is selected.
    if result['issues']:
        with st.expander(f"Dikkat gerektiren {len(result['issues'])} kontrol",expanded=True):render_issues(result)

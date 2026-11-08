"""Gece ve Yıllık İzin — onaylı talepleri de içeren ortak vardiya takvimi."""
import calendar,uuid
from datetime import date
import streamlit as st
from ortak.personel import get_people
from ortak.kesin_kayit_deposu import fixed_calendar_rows
from ortak.takvim_gorunumu import render_calendar
from ortak.calisma_alani_deposu import save_keys
from modules.vardiya_plani.vardiya_motoru import bounds


def render_fixed_records(code,year,month):
    state=st.session_state;start=date(year,month,1);end=date(year,month,calendar.monthrange(year,month)[1])
    rows=[r for r in fixed_calendar_rows(state,start,end) if r['shift_code']==code]
    from ortak.personel_deposu import list_people
    people=[p for p in (list_people(state,True) if state.get('all_include_inactive') else get_people(state)) if str(p['employee_id']) in {r['employee_id'] for r in rows}]
    if rows:render_calendar(rows,people,start,end,key='fixed_calendar_'+code)
    else:st.info('Seçili ayda kayıt yok.')
    if code=='GECE':
        from ortak.gece_kontrolleri import night_gaps
        try:
            missing=night_gaps(state)
            if missing:
                st.warning(f'Seçili plan döneminde {len(missing)} tarih/dil için gece eksiği var.')
                with st.expander('Gece eksiklerini göster'):st.dataframe(missing,hide_index=True,use_container_width=True)
            elif state.get('shift_rules',{}).get('night',{}).get('enabled'):st.success('Seçili plan dönemi için gece kontrolleri tamam.')
        except (ValueError,KeyError):pass
    if (state.get('profile') or {}).get('position') not in {'wfm','manager','moderator'}:return
    with st.expander('Kesin Kayıt Ekle / Kaldır'):
        all_people={str(p['employee_id']):p for p in get_people(state) if p.get('position')=='agent'}
        selected=st.multiselect('Personeller',list(all_people),format_func=lambda i:all_people[i]['full_name'],key='fixed_people_'+code)
        a,b=st.columns(2);first=a.date_input('Başlangıç',value=start,key='fixed_start_'+code);last=b.date_input('Bitiş',value=start,key='fixed_end_'+code)
        begin,finish=None,None
        if code=='GECE':
            general=state.get('shift_rules',{}).get('general',{});begin=a.text_input('Gece başlangıç',value=general.get('night_window_start','00:00'),key='fixed_ns');finish=b.text_input('Gece bitiş',value=general.get('night_window_end','08:00'),key='fixed_ne')
        note=st.text_input('Kayıt açıklaması',key='fixed_note_'+code)
        if st.button('Kesin Kaydı Kaydet',key='fixed_save_'+code):
            try:
                if not selected or last<first or (last-first).days>366:raise ValueError('Personel ve geçerli tarih aralığı seçin.')
                if code=='GECE':bounds({'date':str(first),'shift_code':code,'start':begin,'end':finish})
                state['fixed_shift_records']=state.get('fixed_shift_records',[])+[{'id':uuid.uuid4().hex,'employee_id':i,'full_name':all_people[i]['full_name'],'start_date':str(first),'end_date':str(last),'shift_code':code,'start':begin,'end':finish,'note':note} for i in selected]
                save_keys(state);st.rerun()
            except ValueError as exc:st.error(str(exc))
        existing={r['id']:r for r in state.get('fixed_shift_records',[]) if r.get('shift_code')==code}
        if existing:
            ident=st.selectbox('Kaldırılacak kesin kayıt',list(existing),format_func=lambda i:f"{existing[i].get('full_name','Personel')} · {existing[i]['start_date']} – {existing[i]['end_date']}",key='fixed_delete_pick_'+code)
            if st.button('Kesin Kaydı Kaldır',key='fixed_delete_'+code):
                state['fixed_shift_records']=[r for r in state['fixed_shift_records'] if r['id']!=ident];save_keys(state);st.rerun()

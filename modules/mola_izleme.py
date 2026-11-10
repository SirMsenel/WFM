"""İzleme — kişisel vardiya, planlı statüler ve kapasiteye göre mola talebi."""
from datetime import datetime,date,time
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from ortak.mola_servisi import records,availability,request,cancel
from ortak.personel_karti import pick_person,render_person
from ortak.sabit_demo import history_rows
from ortak.takvim_gorunumu import render_calendar


def render():
    s=st.session_state;st.title('📊 İzleme');profile=s['profile'];person=pick_person(s,profile,'break_monitor')
    if not person:return
    render_person(person);today=datetime.now(ZoneInfo('Europe/Istanbul')).date()
    day=st.date_input('İzlenecek gün',value=today,key='break_day');eid=str(person['employee_id']);rows=[r for r in history_rows(s,day,day) if str(r['employee_id'])==eid]
    render_calendar(rows,[person],day,day,height=150,key='personal_break_calendar')
    reserved=[r for r in records(s) if str(r['employee_id'])==eid and pd.Timestamp(r['start']).date()==day]
    if reserved:
        st.markdown('#### Planlı Statülerim')
        for r in reserved:
            color='#6c71bc' if r['kind']=='Yemek' else '#238b86'
            st.markdown(f'<div style="border-left:5px solid {color};padding:12px;margin:7px 0;background:#f1f7fa;border-radius:10px"><b>{r["kind"]}</b> · {pd.Timestamp(r["start"]):%H:%M}–{pd.Timestamp(r["end"]):%H:%M} · {r["status"]}</div>',unsafe_allow_html=True)
    st.markdown('#### Mola uygunluğu · 30 dakikalık dilimler')
    options=[];duration=int(s.get('status_rules',{}).get('groups',{}).get(person['work_type'],{}).get('break_minutes',15))
    for slot in range(48):
        t=pd.Timestamp(day)+pd.Timedelta(minutes=slot*30)
        try:spare=availability(s,eid,t,duration);value=max(0,int(spare))
        except ValueError:value=0
        options.append({'Saat':t.strftime('%H:%M'),'Uygun mola sayısı':value})
    st.bar_chart(pd.DataFrame(options).set_index('Saat'),color='#279b91')
    if profile.get('position')!='agent':st.info('Mola talebi personelin kendi hesabından yapılır.');return
    a,b=st.columns(2);clock=a.time_input('Mola başlangıcı',value=time(12),step=900,key='break_start');b.metric('Tek mola üst sınırı',str(duration)+' dk')
    if st.button('Mola Talep Et',key='request_break'):
        try:request(s,datetime.combine(day,clock),duration);st.success('Kapasite uygun; mola ayrıldı.');st.rerun()
        except ValueError as e:st.warning(str(e))
    choices={r['id']:r for r in reserved if r['status']=='Onaylı'}
    if choices:
        ident=st.selectbox('İptal edilecek mola',list(choices),key='break_cancel_pick')
        if st.button('Mola Talebini İptal Et'):
            try:cancel(s,ident);st.rerun()
            except ValueError as e:st.error(str(e))

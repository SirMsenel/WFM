"""İzleme — kişisel vardiya, planlı statüler ve kapasiteye göre mola talebi."""
from datetime import datetime,date,time
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from ortak.mola_servisi import records
from ortak.personel_karti import pick_person,render_person
from ortak.sabit_demo import history_rows
from ortak.takvim_gorunumu import render_calendar


def render_today():
    s=st.session_state;profile=s['profile'];person=pick_person(s,profile,'break_monitor')
    if not person:return
    render_person(person);today=datetime.now(ZoneInfo('Europe/Istanbul')).date()
    from ortak.cagri_tahmin_servisi import DAY_NAMES
    st.markdown(f'<div style="padding:20px;background:linear-gradient(120deg,#e0f4f4,#ede9fb);border-radius:18px;color:#295365"><small>BUGÜN · {today:%d.%m.%Y} · {DAY_NAMES[today.weekday()]}</small><h3 style="margin:6px 0">Vardiyam ve Planlanan Statülerim</h3><span>Takvimde çalışma saatlerin, altında bugün sana ayrılan yemek, mola ve görüşme saatlerin yer alır.</span></div>',unsafe_allow_html=True)
    st.divider();day=today;eid=str(person['employee_id']);rows=[r for r in history_rows(s,day,day) if str(r['employee_id'])==eid]
    render_calendar(rows,[person],day,day,height=150,key='personal_break_calendar')
    reserved=[r for r in records(s) if str(r['employee_id'])==eid and pd.Timestamp(r['start']).date()==day]
    if reserved:
        from ortak.statu_kartlari import render_status_cards
        render_status_cards([r for r in reserved if r['status']!='İptal'])
    if profile.get('position')=='agent':
        from modules.statu_degisimi import render_personal,render_requests
        render_personal(s,day)
        with st.expander('Statü değişim taleplerim'):render_requests(s)
    st.caption('Yemek ve mola saatlerin sistem tarafından vardiya hakkının tamamına göre otomatik planlanır. Değişiklik gerekirse karşılıklı statü değişimi kullanılır.')


def render_insights():
    from ortak.modern_kartlar import metric_cards
    from ortak.calisma_sureleri import personnel_hours
    s=st.session_state;person=pick_person(s,s['profile'],'personal_insights')
    if not person:return
    render_person(person);today=datetime.now(ZoneInfo('Europe/Istanbul')).date();dates=st.date_input('İncelenecek dönem',(today.replace(day=1),today),key='insights_dates')
    if len(dates)!=2:return
    eid=str(person['employee_id']);roster=[r for r in history_rows(s,*dates) if str(r['employee_id'])==eid];hours=personnel_hours(s,[person],*dates,published_only=True)
    assigned=[r for r in records(s) if str(r['employee_id'])==eid and r.get('status')!='İptal' and str(dates[0])<=r['start'][:10]<=str(dates[1])]
    metric_cards([('Yayınlanmış çalışma',f'{hours["Toplam saat"].sum():.2f} sa'),('Çalışılan gün',len({r['date'] for r in roster if r.get('start')})),('OFF günü',sum(r['shift_code']=='OFF' for r in roster))])
    st.divider();st.markdown('### Statü ve Koçluk Özeti')
    values=[]
    for kind in ['Yemek','Mola','Koçluk']:
        chosen=[r for r in assigned if r['kind']==kind];minutes=sum((pd.Timestamp(r['end'])-pd.Timestamp(r['start'])).total_seconds()/60 for r in chosen);values.append((kind,f'{len(chosen)} kayıt · {minutes:.2f} dk'))
    metric_cards(values)
    st.info('Bu bilgiler yayınlanmış plan kayıtlarıdır. Performans skoru ve gerçekleşen bireysel performans kaynağı henüz bağlı değil.')


def render():
    from ortak.gezinme import sections
    sections('nav_monitor_views',{'Bugünkü Planım':render_today,'Personel Bilgileri':render_insights})

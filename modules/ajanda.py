"""Yönetim çalışma takvimi ve ekip koçluk planlama."""
from datetime import datetime,time
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from ortak.ajanda_servisi import rows,add_work,add_coaching,MANAGEMENT
from ortak.personel import get_people,visible_people
from ortak.modern_kartlar import metric_cards


def render():
    s=st.session_state;p=s['profile'];st.title('📆 Ajanda')
    if p.get('position') not in MANAGEMENT:st.info('Bu takvim yönetim rolleri içindir.');return
    today=datetime.now(ZoneInfo('Europe/Istanbul')).date();a,b=st.columns([1,2]);day=a.date_input('Takvim günü',today,key='agenda_day');view=b.toggle('Yetkimdeki yönetim takvimlerini göster',False,key='agenda_all') if p['position']!='tl' else False
    current=[r for r in rows(s,view) if r['start'][:10]==str(day)];work=[r for r in current if r['kind']=='Çalışma'];meetings=[r for r in current if r['kind']=='Koçluk'];metric_cards([('Çalışma aralığı',len(work)),('Koçluk görüşmesi',len(meetings)),('Görüşme süresi',f"{sum((pd.Timestamp(r['end'])-pd.Timestamp(r['start'])).total_seconds()/60 for r in meetings):.0f} dk")])
    cols=st.columns(2)
    with cols[0].container(border=True):
        st.markdown('#### Kendi çalışma saatlerim');a,b=st.columns(2);start=a.time_input('Çalışma başlangıcı',time(8),key='agenda_work_start');end=b.time_input('Çalışma bitişi',time(17),key='agenda_work_end')
        if st.button('Çalışmayı Ajandama Ekle',key='agenda_save_work'):
            try:
                if start is None or end is None:raise ValueError('İki saati de doldurun.')
                a=pd.Timestamp(datetime.combine(day,start));b=pd.Timestamp(datetime.combine(day,end));b=b+pd.Timedelta(days=1) if b<a else b;add_work(s,a,b);st.rerun()
            except ValueError as e:st.warning(str(e))
    with cols[1].container(border=True):
        st.markdown('#### Ekibime koçluk ata');people={str(x['employee_id']):x for x in visible_people(p,get_people(s))}
        if people:
            eid=st.selectbox('Görüşülecek personel',list(people),format_func=lambda i:people[i]['full_name'],key='agenda_coach_person');a,b=st.columns(2);clock=a.time_input('Görüşme saati',time(14),key='agenda_coach_clock');duration=b.number_input('Görüşme süresi (dk)',5,60,15,5,key='agenda_coach_duration')
            if st.button('Uygunluğu Kontrol Et ve Ata',key='agenda_assign_coach'):
                try:
                    if clock is None:raise ValueError('Görüşme saatini doldurun.')
                    add_coaching(s,eid,datetime.combine(day,clock),duration);st.success('Görüşme atandı; personelin takvimine ve bildirimlerine eklendi.');st.rerun()
                except ValueError as e:st.warning(str(e))
        else:st.info('Atanabilir personel yok.')
    st.markdown('#### Günlük Ajanda')
    if not current:st.info('Bu gün için ajanda kaydı yok.')
    for r in current:
        color='#168d96' if r['kind']=='Çalışma' else '#8064ac'
        st.markdown(f'<div style="border-left:5px solid {color};background:{color}0b;border-radius:14px;padding:17px;margin:8px 0"><b>{r["kind"]}</b> · {pd.Timestamp(r["start"]):%H:%M}–{pd.Timestamp(r["end"]):%H:%M}</div>',unsafe_allow_html=True);st.caption(r.get('name',r['owner']))

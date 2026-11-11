"""Haftalık lider çalışma takvimi ve ayrılmış koçluk alanlarına atama."""
from datetime import datetime
from zoneinfo import ZoneInfo
from html import escape
import pandas as pd
import streamlit as st
from ortak.ajanda_servisi import rows,save_week,add_coaching,MANAGEMENT
from ortak.personel import get_people,visible_people
from ortak.cagri_tahmin_servisi import DAY_NAMES


def render():
    s=st.session_state;p=s['profile'];st.title('📆 Ajanda')
    if p.get('position') not in MANAGEMENT:st.info('Bu takvim yönetim rolleri içindir.');return
    today=datetime.now(ZoneInfo('Europe/Istanbul')).date();chosen=st.date_input('Planlanacak hafta',today,key='agenda_week');week=pd.Timestamp(chosen)-pd.Timedelta(days=chosen.weekday());end=week+pd.Timedelta(days=6)
    own=rows(s);work=[r for r in own if r['kind']=='Çalışma'];entries=[]
    for day in pd.date_range(week,end):
        old=next((r for r in work if pd.Timestamp(r['start']).date()==day.date()),None)
        entries.append({'Tarih':day.date(),'Gün':DAY_NAMES[day.weekday()],'Çalışıyor':bool(old),'Başlangıç':pd.Timestamp(old['start']).strftime('%H:%M') if old else '08:00','Bitiş':pd.Timestamp(old['end']).strftime('%H:%M') if old else '17:00'})
    with st.container(border=True):
        st.markdown('#### Haftalık Çalışma Saatlerim')
        edited=st.data_editor(pd.DataFrame(entries),hide_index=True,disabled=['Tarih','Gün'],key='agenda_week_editor_'+str(week.date()),column_config={'Başlangıç':st.column_config.TextColumn(help='SS:DD, örnek 08:00',required=True),'Bitiş':st.column_config.TextColumn(help='SS:DD, örnek 17:00',required=True)})
        if st.button('Haftayı Kaydet',key='agenda_save_work',type='primary'):
            try:save_week(s,week,edited.to_dict('records'));st.rerun()
            except (ValueError,TypeError) as e:st.warning('Hafta kaydedilemedi: '+str(e))
    st.divider();st.markdown('### Personelin Uygun Koçluk Aralıkları')
    people={str(x['employee_id']):x for x in visible_people(p,get_people(s))}
    if people:
        eid=st.selectbox('Görüşülecek personel',list(people),format_func=lambda i:people[i]['full_name'],key='agenda_coach_person')
        from ortak.kocluk_alanlari import eligible
        openings=[r for r in eligible(s,eid) if week.date()<=pd.Timestamp(r['start']).date()<=end.date()]
        if not openings:st.info('Bu hafta kendi çalışma takviminle eşleşen, planlamada ayrılmış uygun koçluk alanı yok. Vardiyanın yayınlanmış ve haftalık çalışma saatlerinin girilmiş olması gerekir.')
        for offset in range(0,len(openings),3):
            for col,r in zip(st.columns(3),openings[offset:offset+3]):
                with col.container(border=True):
                    a,b=pd.Timestamp(r['start']),pd.Timestamp(r['end']);st.markdown(f'**{a:%d.%m.%Y} · {DAY_NAMES[a.weekday()]}**');st.markdown(f'### {a:%H:%M} – {b:%H:%M}');st.caption('Hat kapasitesi ayrıldı · '+people[eid]['full_name'])
                    if st.button('Bu Aralığa Koçluk Ata',key='agenda_assign_'+r['id'],use_container_width=True):
                        try:add_coaching(s,eid,a,int((b-a).total_seconds()/60),opening_id=r['id']);st.success('Görüşme atandı.');st.rerun()
                        except ValueError as e:st.warning(str(e))
    st.divider();st.markdown('### Haftalık Ajandam')
    columns=st.columns(7)
    for col,day in zip(columns,pd.date_range(week,end)):
        with col:
            st.markdown(f'**{day:%d.%m}**');st.caption(DAY_NAMES[day.weekday()])
            items=[r for r in rows(s) if pd.Timestamp(r['start']).date()==day.date()]
            if not items:st.caption('OFF / kayıt yok')
            for r in items:
                color='#168d96' if r['kind']=='Çalışma' else '#8064ac';a,b=pd.Timestamp(r['start']),pd.Timestamp(r['end'])
                st.markdown(f'<div style="padding:12px 8px;background:{color}15;border-top:4px solid {color};border-radius:10px;margin:8px 0;color:{color}"><b>{escape(r["kind"])}</b><div>{a:%H:%M}–{b:%H:%M}</div><small>{escape(r.get("name",""))}</small></div>',unsafe_allow_html=True)

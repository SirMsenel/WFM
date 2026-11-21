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
    render_person(person)
    from ortak.demo_zamani import today as active_today
    from ortak.cagri_tahmin_servisi import DAY_NAMES
    today=active_today(s);day=st.date_input('İzlenecek gün',value=today,key='monitor_status_day',format='DD.MM.YYYY');prefix='BUGÜN' if day==today else 'SEÇİLİ GÜN'
    st.markdown(f'<div style="padding:17px 20px;background:linear-gradient(120deg,#e0f4f4,#ede9fb);border-radius:18px;color:#295365"><b>{prefix}</b><span style="margin-left:12px;font-size:20px;font-weight:800">{day:%d.%m.%Y} · {DAY_NAMES[day.weekday()]}</span></div>',unsafe_allow_html=True)
    eid=str(person['employee_id']);rows=[r for r in history_rows(s,day,day) if str(r['employee_id'])==eid]
    render_calendar(rows,[person],day,day,height=150,key='personal_break_calendar')
    reserved=[r for r in records(s) if str(r['employee_id'])==eid and pd.Timestamp(r['start']).date()==day and r['status']!='İptal']
    from ortak.kocluk_talepleri import eligible_slots,submit,requests as coaching_requests
    from modules.statu_degisimi import render_personal,render_requests
    left,right=st.columns(2,vertical_alignment='top')
    with left:
        st.markdown('### Planlanan Statüler')
        from ortak.statu_kartlari import render_status_panel
        render_status_panel(reserved)
    with right:
        st.markdown('### Talepler ve Durumları')
        coaching=[r for r in coaching_requests(s) if str(r['employee_id'])==eid]
        colors={'Bekliyor':'#c18e44','Onaylandı':'#2f8b69','Reddedildi':'#bd6262'}
        for row in coaching[:8]:
            a,b=pd.Timestamp(row['start']),pd.Timestamp(row['end']);color=colors.get(row['status'],'#66869c')
            st.markdown(f'<div style="padding:9px 12px;margin:6px 0;border-left:4px solid {color};background:{color}12;border-radius:10px;display:grid;grid-template-columns:1fr auto;gap:5px"><b style="color:{color}">Koçluk · {row["status"]}</b><small>{a:%d.%m}</small><span style="font-size:12px">{a:%H:%M}–{b:%H:%M}</span><small>{row.get("reason","")}</small></div>',unsafe_allow_html=True)
        render_requests(s)
    if profile.get('position')=='agent':
        st.divider();request_left,request_right=st.columns([1,1.6],vertical_alignment='top')
        with request_left:
            st.markdown('### Yemek / Mola Değişimi')
            render_personal(s,day)
        with request_right:
            st.markdown('### Takım Liderinden Koçluk Talep Et')
            openings=eligible_slots(s,eid,day)
            if not openings:
                st.info('Bu gün için vardiyan, takım liderinin ajandası, açık kapasite ve haftalık/aylık koçluk hakkınla eşleşen saat yok. Haftalık hakkın dolduysa yeni saatler pasif kalır.')
            else:
                for offset in range(0,min(8,len(openings)),4):
                    for col,opening in zip(st.columns(4),openings[offset:offset+4]):
                        a,b=pd.Timestamp(opening['start']),pd.Timestamp(opening['end']);selected=s.get('agent_coaching_request_slot')==opening['id']
                        with col.container(border=True):
                            st.markdown(f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:5px"><div style="background:#edf7f8;border-radius:8px;padding:6px;text-align:center"><small>Başlangıç</small><br><b>{a:%H:%M}</b></div><div style="background:#f2eef9;border-radius:8px;padding:6px;text-align:center"><small>Bitiş</small><br><b>{b:%H:%M}</b></div></div><div style="margin-top:6px;text-align:center;font-size:12px">{(b-a).total_seconds()/60:.0f} dakika</div>',unsafe_allow_html=True)
                            if st.button('✓ Seçildi' if selected else 'Seç',type='primary' if selected else 'secondary',key='agent_coaching_pick_'+opening['id'],use_container_width=True):s['agent_coaching_request_slot']=opening['id'];st.rerun()
                choice=s.get('agent_coaching_request_slot')
                if st.button('Takım Lideri Onayına Gönder',key='agent_coaching_request',disabled=choice not in {row['id'] for row in openings},type='primary'):
                    try:submit(s,choice);s.pop('agent_coaching_request_slot',None);st.success('Talep takım liderinin Ajanda onayına ve Taleplerim alanına gönderildi.');st.rerun()
                    except ValueError as exc:st.warning(str(exc))
    st.caption('Yemek ve mola saatleri otomatik planlanır; koçluk talebi takım lideri onayından sonra iki ajandaya da işlenir.')


def render_insights():
    from ortak.modern_kartlar import metric_cards
    from ortak.calisma_sureleri import personnel_hours
    s=st.session_state;person=pick_person(s,s['profile'],'personal_insights')
    if not person:return
    render_person(person)
    from ortak.demo_zamani import today as active_today
    today=active_today(s);dates=st.date_input('İncelenecek dönem',(today.replace(day=1),today),key='insights_dates')
    if len(dates)!=2:return
    eid=str(person['employee_id']);roster=[r for r in history_rows(s,*dates) if str(r['employee_id'])==eid];hours=personnel_hours(s,[person],*dates,published_only=True)
    assigned=[r for r in records(s) if str(r['employee_id'])==eid and r.get('status')!='İptal' and str(dates[0])<=r['start'][:10]<=str(dates[1])]
    metric_cards([('Yayınlanmış çalışma',f'{hours["Toplam saat"].sum():.2f} sa'),('Çalışılan gün',len({r['date'] for r in roster if r.get('start')})),('OFF günü',sum(r['shift_code']=='OFF' for r in roster))])
    st.markdown('### Koçlukta Kullanılacak Personel Bilgileri')
    metric_cards([('Şikayet sayısı','Veri kaynağı bekleniyor'),('NPS / anket puanı','Veri kaynağı bekleniyor'),('Destek puanı','Veri kaynağı bekleniyor')])
    st.caption('Bu üç kart CRM, anket ve kalite kaynakları bağlandığında gerçek değerlerle dolar; sentetik puan üretilmez.')
    st.divider();st.markdown('### Statü ve Koçluk Özeti')
    values=[]
    for kind in ['Yemek','Mola','Koçluk']:
        chosen=[r for r in assigned if r['kind']==kind];minutes=sum((pd.Timestamp(r['end'])-pd.Timestamp(r['start'])).total_seconds()/60 for r in chosen);values.append((kind,f'{len(chosen)} kayıt · {minutes:.2f} dk'))
    metric_cards(values)
    st.info('Bu bilgiler yayınlanmış plan kayıtlarıdır. Performans skoru ve gerçekleşen bireysel performans kaynağı henüz bağlı değil.')


def render():
    from ortak.gezinme import sections
    s=st.session_state
    pages={'Bugünkü Planım':render_today,'Personel Bilgileri':render_insights}
    if s['profile'].get('position') in {'tl','manager','assistant_manager','wfm','planning_manager','moderator'}:
        def team_plan():
            from ortak.personel import get_people,visible_people
            people=visible_people(s['profile'],get_people(s))
            from ortak.demo_zamani import today as active_today
            today=active_today(s);dates=st.date_input('Ekip vardiya dönemi',(today,today+pd.Timedelta(days=6)),key='monitor_team_dates')
            if len(dates)!=2:return
            from ortak.sabit_demo import history_rows
            rows=history_rows(s,*dates);ids={str(p['employee_id']) for p in people};render_calendar([row for row in rows if str(row['employee_id']) in ids],people,*dates,key='monitor_team_calendar',height=460)
        pages['Ekip Planı']=team_plan
    sections('nav_monitor_views',pages)

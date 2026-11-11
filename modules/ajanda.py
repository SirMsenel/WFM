"""Haftalık shift ajandası ve ortak koçluk kontenjanına atama."""
from datetime import datetime,time
from zoneinfo import ZoneInfo
from collections import defaultdict
import pandas as pd
import streamlit as st
from ortak.ajanda_servisi import rows,save_week,add_coaching,MANAGEMENT
from ortak.personel import get_people,visible_people
from ortak.cagri_tahmin_servisi import DAY_NAMES
from ortak.takvim_gorunumu import modern_grid,render_calendar
from ortak.ajanda_gorunumu import weekly_grid,opportunity_grid
from ortak.modern_kartlar import metric_cards


def render():
    s=st.session_state;p=s['profile'];st.title('📆 Ajanda')
    if p.get('position') not in MANAGEMENT:st.info('Bu takvim yönetim rolleri içindir.');return
    today=datetime.now(ZoneInfo('Europe/Istanbul')).date();chosen=st.date_input('Ajanda haftası',today,key='agenda_week',format='DD.MM.YYYY');week=pd.Timestamp(chosen)-pd.Timedelta(days=chosen.weekday());end=week+pd.Timedelta(days=6)
    own=rows(s);work=[r for r in own if r['kind']=='Çalışma'];current=[r for r in own if pd.Timestamp(r['start'])<end+pd.Timedelta(days=1) and pd.Timestamp(r['end'])>week]
    st.markdown(f'<div style="padding:18px 22px;background:linear-gradient(110deg,#e1f4f4,#eee7fc);border:1px solid #d8e5ec;border-radius:18px;color:#305568;margin-bottom:18px"><b>HAFTALIK AJANDAM</b><div style="font-size:24px;font-weight:750;margin:8px 0">{week:%d.%m.%Y} → {end:%d.%m.%Y}</div><span>Çalışma saatlerin ve ekibinle planladığın görüşmeler tek takvimde.</span></div>',unsafe_allow_html=True)
    minutes=lambda r:max(0,(min(pd.Timestamp(r['end']),end+pd.Timedelta(days=1))-max(pd.Timestamp(r['start']),week)).total_seconds()/60)
    metric_cards([('Haftalık çalışma',f"{sum(minutes(r) for r in current if r['kind']=='Çalışma')/60:.2f} saat"),('Planlı koçluk',sum(r['kind']=='Koçluk' for r in current)),('Görüşmelere ayrılan süre',f"{sum(minutes(r) for r in current if r['kind']=='Koçluk'):.0f} dk")])
    st.markdown('### Çalışma ve Görüşme Takvimim');modern_grid(weekly_grid(current,week,p.get('full_name',p['username'])),'agenda_weekly_shifts')
    with st.expander('Haftalık Çalışma Saatlerimi Düzenle'):
        with st.form('agenda_work_form_'+str(week.date())):
            entries=[]
            for column,day in zip(st.columns(7),pd.date_range(week,end)):
                with column:
                    st.markdown(f'**{day:%d.%m}**');st.caption(DAY_NAMES[day.weekday()]);old=next((r for r in work if pd.Timestamp(r['start']).date()==day.date()),None)
                    active=st.checkbox('Çalışma',bool(old),key='agenda_on_'+str(day.date()))
                    a=st.time_input('Giriş',pd.Timestamp(old['start']).time() if old else time(8),step=900,key='agenda_start_'+str(day.date()))
                    b=st.time_input('Çıkış',pd.Timestamp(old['end']).time() if old else time(17),step=900,key='agenda_end_'+str(day.date()))
                    entries.append({'Tarih':day.date(),'Çalışıyor':active,'Başlangıç':a.strftime('%H:%M') if a else None,'Bitiş':b.strftime('%H:%M') if b else None})
            if st.form_submit_button('Haftayı Kaydet',type='primary'):
                try:
                    if any(x['Çalışıyor'] and (not x['Başlangıç'] or not x['Bitiş']) for x in entries):raise ValueError('Çalışma günlerinde giriş ve çıkış saatlerini doldurun.')
                    save_week(s,week,entries);st.rerun()
                except (ValueError,TypeError) as e:st.warning('Hafta kaydedilemedi: '+str(e))
    st.divider();st.markdown('### Ekibim İçin Koçluk Planla')
    people={str(x['employee_id']):x for x in visible_people(p,get_people(s))}
    if not people:st.info('Yetki kapsamında personel yok.');return
    eid=st.selectbox('Görüşülecek personel',list(people),format_func=lambda i:people[i]['full_name'],key='agenda_coach_person');person=people[eid]
    rule=s.get('status_rules',{}).get('groups',{}).get(person['work_type'],{})
    st.caption('Aynı hafta birden fazla görüşme: '+('İzinli' if rule.get('coaching_multiple_per_week',False) else 'Kapalı · en fazla bir görüşme')+' · Aylık üst süre: '+str(rule.get('coaching_monthly_minutes',60))+' dk')
    from ortak.sabit_demo import history_rows
    personal=[r for r in history_rows(s,week-pd.Timedelta(days=1),end) if str(r['employee_id'])==eid]
    st.markdown('#### Personelin Vardiyası');render_calendar(personal,[person],week,end,key='agenda_person_shifts')
    from ortak.kocluk_alanlari import eligible
    openings=[r for r in eligible(s,eid) if week.date()<=pd.Timestamp(r['start']).date()<=end.date()]
    st.markdown('#### Vardiyanla Eşleşen Açık Koçluk Kontenjanları')
    if not openings:
        st.info('Bu hafta için uygun kontenjan yok. Haftalık çalışma kaydı, personelin vardiyası, diğer statüler ve haftalık/aylık koçluk sınırları birlikte kontrol edilir.');return
    modern_grid(opportunity_grid(openings,week,person['full_name']),'agenda_opening_shifts')
    groups=defaultdict(list)
    for r in openings:groups[(r['start'],r['end'])].append(r)
    dates=sorted({pd.Timestamp(a).date() for a,b in groups});chosen_day=st.segmented_control('Koçluk günü',dates,default=dates[0],format_func=lambda d:f'{d:%d.%m} {DAY_NAMES[d.weekday()]}',key='agenda_coach_day') or dates[0]
    windows=sorted(k for k in groups if pd.Timestamp(k[0]).date()==chosen_day)
    if not windows:return
    choice=st.selectbox('Uygun saat aralığı',windows,format_func=lambda t:f"{pd.Timestamp(t[0]):%H:%M}–{pd.Timestamp(t[1]):%H:%M} · {sum(int(r.get('remaining_capacity',1)) for r in groups[t])} kişilik kontenjan",key='agenda_coach_window');item=groups[choice][0];a,b=pd.Timestamp(item['start']),pd.Timestamp(item['end'])
    metric_cards([('Seçilen görüşme',f'{a:%H:%M}–{b:%H:%M}'),('Kalan kontenjan',sum(int(r.get('remaining_capacity',1)) for r in groups[choice])),('Görüşme süresi',f'{(b-a).total_seconds()/60:.0f} dk')])
    if st.button('Seçilen Kontenjana Koçluk Ata',key='agenda_assign_coach',type='primary'):
        try:add_coaching(s,eid,a,int((b-a).total_seconds()/60),opening_id=item['id']);st.success('Görüşme takvimlere ve bildirimlere eklendi.');st.rerun()
        except ValueError as e:st.warning(str(e))

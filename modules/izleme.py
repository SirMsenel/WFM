"""İzleme — kişisel / ekip kapsamındaki izin günleri ve gerekçeli değişim sayıları."""
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter
import pandas as pd
import streamlit as st
from ortak.personel import get_people,visible_people
from ortak.calisma_alani_deposu import connect,loads
from ortak.roller_ve_yetkiler import init_governance
from ortak.kesin_kayit_deposu import fixed_calendar_rows


def metrics(state,people,start,end):
    ids={str(p['employee_id']) for p in people};events=[];counts=Counter()
    path=state.get('workspace_db_path')
    if path:
        init_governance(path)
        with connect(path) as db:raw=db.execute('SELECT payload FROM shift_change_batches ORDER BY rowid DESC').fetchall()
        for record in raw:
            item=loads(record[0]);seen=set()
            for row in item['after']:
                eid=str(row['employee_id'])
                if eid not in ids or not str(start)<=row['date']<=str(end):continue
                marker=(eid,item['type']) if item['type']=='Vardiya değişimi' else (eid,row['date'],item['type'])
                if marker in seen:continue
                seen.add(marker);counts[item['type']]+=1
                events.append({'Personel':next(p['full_name'] for p in people if str(p['employee_id'])==eid),'Vardiya tarihi':row['date'],'İşlem':item['type'],'İşlemi yapan':item['actor'],'Gerekçe':item['reason'],'Kayıt zamanı':item['date']})
    calendar=fixed_calendar_rows(state,start,end)
    counts['Rapor günü']=sum(r['employee_id'] in ids and r['shift_code']=='RAPOR' for r in calendar)
    counts['Yıllık izin günü']=sum(r['employee_id'] in ids and r['shift_code']=='YILLIK_IZIN' for r in calendar)
    return counts,events


def render():
    state=st.session_state;profile=state.get('profile') or {};st.title('📊 İzleme')
    people=visible_people(profile,get_people(state));byid={str(p['employee_id']):p for p in people}
    if not byid:st.info('İzlenecek personel yok.');return
    today=datetime.now(ZoneInfo('Europe/Istanbul')).date();a,b,c=st.columns([2,1,1])
    if profile.get('position')=='agent':selected=str(profile['employee_id']);a.markdown('**'+profile.get('full_name','Kendi kayıtlarım')+'**')
    else:selected=a.selectbox('Personel / ekip',['all']+list(byid),format_func=lambda i:'Görünür ekibin tamamı' if i=='all' else byid[i]['full_name'],key='monitor_person')
    start=b.date_input('Başlangıç',value=today.replace(day=1),key='monitor_start');end=c.date_input('Bitiş',value=today,key='monitor_end')
    if end<start:st.warning('Bitiş tarihi başlangıçtan önce olamaz.');return
    scope=people if selected=='all' else [byid[selected]];counts,events=metrics(state,scope,start,end)
    labels=[('Erken çıkış','Erken çıkış'),('Geç giriş','Geç giriş'),('Rapor günü','Rapor günü'),('Yıllık izin günü','Yıllık izin günü'),('Vardiya değişimi','Vardiya değişimi')];colors=['#147d8b','#6471b3','#c16a6a','#ad6a9a','#7a9651']
    for col,(label,field),color in zip(st.columns(5),labels,colors):
        col.markdown(f'<div style="border:1px solid {color}33;border-top:4px solid {color};background:{color}09;border-radius:17px;padding:20px;min-height:120px;color:{color}"><b>{label}</b><div style="font-size:31px;font-weight:800;margin-top:15px">{counts[field]}</div></div>',unsafe_allow_html=True)
    st.caption('İzinler gün olarak; erken/geç girişler kişi-gün işlemi, vardiya değişimi kişi başına onaylanmış değişim işlemi olarak sayılır. Tarih filtresi vardiya gününe uygulanır.')
    if events:st.dataframe(events,hide_index=True,use_container_width=True,height=500)
    else:st.info('Seçili dönemde uygulanmış değişiklik kaydı yok.')

# Takip / Talep Ilet — bu ekranın / servisin uygulama kodu.
"""Takip — Talep İlet: dengeli vardiya/OFF değişimi ve Takım Lideri rapor girişi."""
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from ortak.talep_servisi import create_request,TYPE_LABELS
from ortak.talep_gorunumu import render_detail
from ortak.personel import get_people


def render():
    state=st.session_state;profile=state.get('profile') or {};role=profile.get('position')
    st.subheader('Yeni Personel Talebi')
    if role not in {'agent','tl'}:st.info('Müşteri Temsilcisi talepleri kendi hesabından iletir; rapor girişini yalnızca Takım Lideri yapar.');return
    types=['Rapor Bildirimi'] if role=='tl' else ['Yıllık İzin Talebi','Evlilik İzni Talebi','Mazeret İzni Talebi','Ücretsiz İzin Talebi','Doğum İzni Talebi','Gece Vardiyası Talebi','Mesai Talebi','Vardiya Değişim Talebi','Genel Talep']
    typ=st.selectbox('Ne için talep oluşturuyorsun?',types,format_func=TYPE_LABELS.get,key='new_request_type')
    today=datetime.now(ZoneInfo('Europe/Istanbul')).date();a,b=st.columns(2)
    start=a.date_input('Başlangıç tarihi',value=today,key='new_request_start');end=b.date_input('Bitiş tarihi',value=today,key='new_request_end')
    payload={'type':typ,'start_date':str(start),'end_date':str(end),'targets':[]};valid=start<=end
    people=[p for p in get_people(state) if p.get('position')=='agent']
    if role=='tl':
        choices={str(p['employee_id']):p for p in people if p.get('team_lead')==profile.get('full_name')}
        if not choices:st.info('Rapor girilecek ekip personeli yok.');return
        payload['report_employee_id']=st.selectbox('Rapor girilecek Müşteri Temsilcisi',list(choices),format_func=lambda i:f"{choices[i]['full_name']} · {choices[i].get('sicil_no',i)} · {choices[i].get('username','')}",key='report_target')
    if typ in {'Mesai Talebi','Gece Vardiyası Talebi'}:
        a,b=st.columns(2);general=state.get('shift_rules',{}).get('general',{})
        payload['overtime_start']=a.text_input('İstenen başlangıç saati',value=general.get('night_window_start','00:00') if typ=='Gece Vardiyası Talebi' else '18:00',key='request_time_start')
        payload['overtime_end']=b.text_input('İstenen bitiş saati',value=general.get('night_window_end','08:00') if typ=='Gece Vardiyası Talebi' else '20:00',key='request_time_end')
    if typ=='Vardiya Değişim Talebi':
        choices={str(p['employee_id']):p for p in people if str(p['employee_id'])!=str(profile.get('employee_id'))}
        if not choices:st.info('Değişim yapılacak Müşteri Temsilcisi yok.');return
        other=st.selectbox('Kimle değiştirmek istiyorsun?',list(choices),format_func=lambda i:f"{choices[i]['full_name']} · {choices[i].get('sicil_no',i)} · {choices[i].get('username','')}",key='swap_target')
        payload['targets']=[choices[other]]
        records={(str(r['employee_id']),r['date']):r for key in ('draft_shift_plan','published_shift_plan') for r in state.get(key,[])}
        own=str(profile['employee_id']);days=sorted({day for eid,day in records if eid==own and (other,day) in records and str(start)<=day<=str(end)})
        selected=st.multiselect('Hangi günlerin vardiyaları değişecek? (OFF alıp vereceğin iki günü birlikte seç)',days,key='swap_dates')
        payload['swap_dates']=selected;valid=valid and bool(selected)
        if selected:
            from ortak.talep_yerlestirme import resolve_swap
            try:
                proposed=resolve_swap(state,{**payload,'employee_id':own,'id':'ÖNİZLEME'})
                st.success('OFF ve saat dengesi uygun: iki kişinin OFF sayısı ve toplam çalışma saati korunuyor.')
                st.dataframe([{'Kişi':profile.get('full_name') if r['employee_id']==own else choices[other]['full_name'],'Tarih':r['date'],'Eski':str(records[(r['employee_id'],r['date'])]['shift_code'])+' '+str(records[(r['employee_id'],r['date'])].get('start') or ''),'Yeni':r['shift_code']+' '+str(r.get('start') or '')+'–'+str(r.get('end') or '')} for r in proposed],hide_index=True,use_container_width=True)
            except ValueError as exc:valid=False;st.warning(str(exc))
        st.caption('Nihai onayda güncel vardiya, ders/sınav ve dinlenme kuralları yeniden kontrol edilir.')
        st.caption('Örnek: bugün sen OFF / Mehmet çalışıyor, yarın Mehmet OFF / sen çalışıyorsan iki günü aynı talepte seç. Tek günle OFF veya saat dengesini bozarsan talep gönderilmez.')
    payload['note']=st.text_area('Açıklama / gerekçe',key='new_request_reason',placeholder='Değişiklik ne hakkında? Gerekçeni yaz.')
    if typ=='Vardiya Değişim Talebi':valid=valid and bool(payload['note'].strip())
    if st.button('Talebi Takım Liderime Gönder' if role=='agent' else 'Raporu Planlamaya İlet',disabled=not valid,key='request_send'):
        try:
            req=create_request(state,payload);state['last_created_request_id']=req['id'];st.success('Talebin kaydedildi: '+req['id'])
        except (ValueError,TypeError,KeyError) as exc:st.error(str(exc))
    last=state.get('last_created_request_id');receipt=next((r for r in state.get('trk_requests',[]) if r['id']==last),None)
    if receipt:
        st.markdown('### Son Gönderdiğin Kayıt');render_detail(receipt,'last_receipt')

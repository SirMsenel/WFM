from datetime import date
import streamlit as st
from core.request_service import create_request, TYPE_LABELS
from core.request_ui import render_detail


def render():
    state=st.session_state
    profile=state.get('profile') or {}
    st.subheader('Yeni Personel Talebi')
    if profile.get('position')!='agent':
        st.info('Bu ekran personelin kendi hesabından talep göndermesi içindir.')
        return
    st.caption('Talebin önce takım liderine, onaydan sonra planlamaya iletilir. Kayıt numarasıyla tüm adımları takip edebilirsin.')
    st.write(f"**Talep eden:** {profile.get('full_name')} · **Takım lideri:** {profile.get('team_lead') or 'Tanımlanmamış'}")
    types=['Yıllık İzin Talebi','Evlilik İzni Talebi','Mazeret İzni Talebi','Rapor Bildirimi','Ücretsiz İzin Talebi','Doğum İzni Talebi','Gece Vardiyası Talebi','Mesai Talebi','Vardiya Değişim Talebi','Genel Talep']
    typ=st.selectbox('Ne için talep oluşturuyorsun?',types,format_func=lambda x:TYPE_LABELS[x],key='new_request_type')
    employees=state.get('employees_cache',[])
    if typ=='Vardiya Değişim Talebi' and not employees:
        from modules.shift_planing.planning_data import fetch_employees
        try:
            employees=fetch_employees(state)
        except Exception as exc:
            st.error(f'Personeller alınamadı: {exc}')
    with st.form('new_personnel_request',clear_on_submit=True):
        a,b=st.columns(2)
        start=a.date_input('Başlangıç tarihi',value=date.today())
        end=b.date_input('Bitiş tarihi',value=date.today())
        payload={'type':typ,'start_date':str(start),'end_date':str(end),'targets':[]}
        if typ in {'Mesai Talebi','Gece Vardiyası Talebi'}:
            a,b=st.columns(2)
            payload['overtime_start']=a.text_input('İstenen başlangıç saati',value='00:00' if typ=='Gece Vardiyası Talebi' else '18:00')
            payload['overtime_end']=b.text_input('İstenen bitiş saati',value='07:00' if typ=='Gece Vardiyası Talebi' else '20:00')
        if typ=='Vardiya Değişim Talebi':
            choices={str(e['employee_id']):e for e in employees if str(e['employee_id'])!=str(profile.get('employee_id'))}
            if choices:
                picked=st.selectbox('Değişim yapılacak personel',list(choices),format_func=lambda eid:f"{choices[eid].get('full_name')} · {choices[eid].get('team_lead')}")
                payload['targets']=[choices[picked]]
            st.caption('Her iki personelin takım liderinin onayı tamamlanmadan planlamaya iletilmez.')
        payload['note']=st.text_area('Açıklama / gerekçe',placeholder='Talebini değerlendirecek kişiye iletmek istediğin bilgi')
        send=st.form_submit_button('Talebi Takım Liderime Gönder')
    if send:
        try:
            req=create_request(state,payload)
            state['last_created_request_id']=req['id']
            st.success(f"Talebin kaydedildi. Kayıt no: {req['id']}")
        except (ValueError,TypeError,KeyError) as exc:
            st.error(f'Talep kaydedilemedi: {exc}')
    last=state.get('last_created_request_id')
    receipt=next((r for r in state.get('trk_requests',[]) if r['id']==last and r.get('created_by')==profile.get('username')),None)
    if receipt:
        st.markdown('### Son Gönderdiğin Kayıt')
        render_detail(receipt,'last_receipt')

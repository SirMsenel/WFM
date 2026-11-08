# Personel Takip / Personel Yasam Dongusu — bu ekranın / servisin uygulama kodu.
"""Personel Takip — Personel Ekleme ve Ayrılma Onayları."""
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from ortak.personel_is_akisi import submit,proposals,decide
from ortak.personel_deposu import list_people
from ortak.roller_ve_yetkiler import permissions
from ortak.personel import WORK_LABELS,LANG_LABELS


def render():
    state=st.session_state;profile=state.get('profile') or {};caps=permissions(state)
    st.subheader('Personel Ekleme / Ayrılma')
    if 'personel_talebi' in caps:
        kind=st.radio('Personel işlemi',['Ekleme','Ayrılma'],horizontal=True,key='hr_kind')
        values={}
        if kind=='Ekleme':
            a,b=st.columns(2)
            values.update(full_name=a.text_input('Ad soyad',key='hr_name'),sicil_no=b.text_input('Sicil no',key='hr_registry'),username=a.text_input('Kullanıcı adı',key='hr_username'),
                          work_type=b.selectbox('Çalışma grubu',list(WORK_LABELS),format_func=WORK_LABELS.get,key='hr_work'),language=a.selectbox('Dil',list(LANG_LABELS),format_func=LANG_LABELS.get,key='hr_lang'),location=b.text_input('Şehir / lokasyon',key='hr_location'))
            values['company']=st.text_input('Şirket (Ulak, Teleperformance, Assistt vb.)',key='hr_company')
        else:
            team=[p for p in list_people(state) if p.get('team_lead')==profile.get('full_name') and p.get('position')=='agent']
            if not team:st.info('Aktif ekip personeli yok.');return
            byid={str(p['employee_id']):p for p in team}
            values['employee_id']=st.selectbox('Ayrılacak personel',list(byid),format_func=lambda i:f"{byid[i]['full_name']} · {byid[i]['sicil_no']} · {byid[i]['username']}",key='hr_target')
        values['effective_date']=str(st.date_input('İşe giriş / ayrılma tarihi',value=datetime.now(ZoneInfo('Europe/Istanbul')).date(),key='hr_effective'))
        reason=st.text_area('Personel işlemi gerekçesi',key='hr_reason')
        st.caption('Takım Lideri → ilgili Yönetici → Planlama. Ayrılma geçmiş vardiya ve denetim kayıtlarını silmez.')
        if st.button('Yönetici Onayına Gönder',key='hr_submit'):
            try:submit(state,kind,values,reason);st.success('Personel talebi yöneticiye iletildi.')
            except ValueError as exc:st.error(str(exc))
    items=proposals(state)
    if profile.get('position')=='tl':items=[p for p in items if p['team_lead']==profile.get('full_name')]
    elif profile.get('position')=='manager':items=[p for p in items if p['manager']==profile.get('full_name')]
    elif profile.get('position') not in {'wfm','moderator'}:items=[]
    if not items:st.info('Bu kapsamda personel talebi yok.');return
    st.dataframe([{'Kayıt':p['id'],'İşlem':p['kind'],'Personel':p['values'].get('full_name'),'Sicil':p['values'].get('sicil_no'),'Kullanıcı adı':p['values'].get('username'),'Tarih':p['values']['effective_date'],'Durum':p['stage'],'Yönetici':p['manager']} for p in items],hide_index=True,use_container_width=True)
    ident=st.selectbox('İncelenecek personel talebi',[p['id'] for p in items],key='hr_review')
    item=next(p for p in items if p['id']==ident)
    st.write('**Gerekçe:** '+item['reason'])
    if item['stage'] not in {'Yönetici onayı','Planlama onayı'}:return
    can=(item['stage']=='Yönetici onayı' and 'personel_incele' in caps) or (item['stage']=='Planlama onayı' and 'personel_onayla' in caps)
    if not can:st.info('Talep '+item['stage']+' aşamasında.');return
    note=st.text_area('Onay / ret notu',key='hr_decision_note')
    password=None
    if item['stage']=='Planlama onayı' and item['kind']=='Ekleme':
        password=st.text_input('Demo için geçici parola (isteğe bağlı, en az 8 karakter)',type='password',key='hr_password') or None
        st.caption('Boşsa yerel parola ile giriş açılmaz; kurumsal kimlik doğrulama entegrasyonu beklenir. Parola denetim kaydına yazılmaz.')
    a,b=st.columns(2)
    for col,label,approve in [(a,'Personel Talebini Onayla',True),(b,'Personel Talebini Reddet',False)]:
        if col.button(label,key='hr_decide_'+str(approve)):
            try:decide(state,item,approve,note,password);st.rerun()
            except (ValueError,Exception) as exc:st.error(str(exc))

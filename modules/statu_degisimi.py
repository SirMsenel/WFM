import pandas as pd
import streamlit as st
from ortak.statu_degisimleri import candidates,submit,requests,decide
from ortak.mola_servisi import records
from ortak.personel import get_people


def render_personal(state,day):
    p=state['profile'];eid=str(p.get('employee_id'));all_rows=records(state);own={r['id']:r for r in all_rows if str(r['employee_id'])==eid and r['kind'] in {'Yemek','Mola'} and r['start'][:10]==str(day) and r['status']=='Planlı'}
    with st.expander('Yemek / Mola Değişimi İste',expanded=False):
        if not own:st.info('Bu gün için değiştirilebilir planlı yemek/mola yok.');return
        label=lambda r:f"{r['kind']} · {pd.Timestamp(r['start']):%H:%M}–{pd.Timestamp(r['end']):%H:%M}"
        ident=st.selectbox('Değiştireceğim statü',list(own),format_func=lambda i:label(own[i]),key='swap_status_own');others=candidates(state,ident);byid={r['id']:r for r in others};people={str(x['employee_id']):x for x in get_people(state)}
        if not byid:st.info('Aynı ekip, grup ve dilde vardiyaya uygun eş süreli değişim yok.');return
        other=st.selectbox('Uygun karşı personel ve statüsü',list(byid),format_func=lambda i:people.get(str(byid[i]['employee_id']),{}).get('full_name','')+' · '+label(byid[i]),key='swap_status_peer');reason=st.text_input('Değişim gerekçesi',key='swap_status_reason')
        st.caption('Önce karşı personel, ardından takım lideri onaylar. Onaylanana kadar mevcut saatler korunur.')
        if st.button('Değişim Talebi Gönder',key='swap_status_send'):
            try:submit(state,ident,other,reason);st.success('Değişim karşı personelin onayına gönderildi.')
            except ValueError as e:st.warning(str(e))


def render_requests(state):
    items=requests(state)
    if not items:st.info('Statü değişim talebi yok.');return
    for r in items:
        with st.container(border=True):
            a,b=r['before'];st.markdown(f"**{a['kind']} değişimi · {r['status']}**");st.write(f"{a['start'][:10]} · {pd.Timestamp(a['start']):%H:%M} ↔ {pd.Timestamp(b['start']):%H:%M}");st.caption(r['reason'])
            if r['status'] in {'Karşı personel onayı','Takım Lideri onayı'}:
                x,y=st.columns(2)
                for col,label,value in [(x,'Onayla',True),(y,'Reddet',False)]:
                    if col.button(label,key='status_decide_'+r['id']+str(value)):
                        try:decide(state,r,value);st.rerun()
                        except ValueError as e:st.warning(str(e))

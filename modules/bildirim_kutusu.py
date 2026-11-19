import streamlit as st
from html import escape
from ortak.bildirimler import items,mark_read,mark_many_read


def render():
    s=st.session_state;st.subheader('🔔 Bildirim Kutusu');records=items(s);a,b=st.columns([2,1]);categories=['Tümü']+sorted({p['Konu'] for p in records});kind=a.selectbox('Konu',categories,key='notice_category');unread=b.toggle('Yalnızca okunmamış',False,key='notice_unread');chosen=[p for p in records if (kind=='Tümü' or p['Konu']==kind) and (not unread or not p['Okundu'])]
    if not chosen:st.info('Bu görünümde bildirim yok.');return
    if st.button('Görünenleri Okundu İşaretle',key='notices_all_read'):
        mark_many_read(s,[p['id'] for p in chosen])
        st.rerun()
    for p in chosen:
        color='#70859b' if p['Okundu'] else '#168d96'
        with st.container(border=True):
            st.markdown(f'<div style="display:flex;justify-content:space-between;gap:10px;color:{color}"><b>{escape(p["Başlık"])}</b><small>{escape(p["Tarih"][:16].replace("T"," "))}</small></div>',unsafe_allow_html=True);st.write(p['İçerik'])
            if not p['Okundu'] and st.button('Okundu',key='read_'+p['id']):mark_read(s,p['id']);st.rerun()

"""Her girişte o kullanıcıya ait okunmamış haberlerin kısa karşılaması."""
from html import escape
import streamlit as st
from ortak.bildirimler import items,mark_many_read


def render(state):
    if not state.pop('_notification_intro_pending',False):return
    unread=[r for r in items(state) if not r['Okundu']]
    if not unread:return
    @st.dialog('🔔 Sana Yeni Haberler Var',width='large')
    def popup():
        st.markdown('''<style>[role=dialog]:has([data-wfm-welcome]){position:fixed!important;top:50%!important;left:50%!important;transform:translate(-50%,-50%)!important;margin:0!important;width:min(760px,92vw)!important;max-height:85vh;overflow-y:auto;border-radius:22px}</style>''',unsafe_allow_html=True)
        st.markdown(f'<div data-wfm-welcome style="padding:18px;background:linear-gradient(120deg,#e0f5f4,#f1e9fc);border-radius:18px;color:#235c6b;font-size:20px;font-weight:750">{len(unread)} yeni bildirim seni bekliyor</div>',unsafe_allow_html=True)
        for r,color in zip(unread[:5],['#1b9299','#8065ac','#bd8d40','#537fa8','#b56a92']):
            st.markdown(f'<div style="margin:12px 0;padding:16px;border-left:5px solid {color};background:{color}0c;border-radius:14px"><b>{escape(r["Başlık"])}</b><div style="font-size:14px;margin-top:8px">{escape(r["İçerik"])}</div></div>',unsafe_allow_html=True)
        a,b=st.columns(2)
        def read():
            current={r['id'] for r in items(state)};mark_many_read(state,[r['id'] for r in unread if r['id'] in current])
        if a.button('Gördüm · Okundu İşaretle',key='welcome_notices_read',on_click=read):st.rerun()
        if b.button('Bildirim Kutusunu Aç',key='welcome_notices_open'):state['main_page']='⚙️ Ayarlar';state['nav_settings']='Bildirimler';st.rerun()
    popup()

import streamlit as st
from core.request_ui import render_center


def render():
    profile=st.session_state.get('profile') or {}
    st.subheader('Personel Talepleri ve İletim Geçmişi')
    if profile.get('position') not in {'tl','wfm','manager','moderator'}:
        st.info('Bu ekran takım lideri ve planlama rolleri içindir.')
        return
    st.caption('Talebin içeriğini incele, değerlendirme notunu ekle ve planlamaya ilet. Ret işleminde gerekçe zorunludur.')
    render_center('tl' if profile.get('position')=='tl' else 'all','staff_requests')

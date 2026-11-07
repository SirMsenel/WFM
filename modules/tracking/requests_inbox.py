import streamlit as st
from core.request_ui import render_center


def render():
    st.subheader('Talep Durumu ve Sonuçları')
    st.caption('Talebin şu an kimde olduğunu, gönderilen içeriği, değerlendirme notlarını ve tüm işlem adımlarını takip et.')
    render_center('all','tracking_requests')

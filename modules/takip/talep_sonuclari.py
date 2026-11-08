# Takip / Talep Sonuclari — bu ekranın / servisin uygulama kodu.
import streamlit as st
from ortak.talep_gorunumu import render_center


def render():
    st.subheader('Talep Durumu ve Sonuçları')
    st.caption('Talebin şu an kimde olduğunu, gönderilen içeriği, değerlendirme notlarını ve tüm işlem adımlarını takip et.')
    render_center('all','tracking_requests')

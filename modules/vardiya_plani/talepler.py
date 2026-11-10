# Vardiya Plani / Talepler — bu ekranın / servisin uygulama kodu.
import streamlit as st
from ortak.talep_gorunumu import render_center


def render():
    st.subheader('Planlama Talep Merkezi')
    st.caption('Talepleri üstlenebilir, taslakta simüle edebilir veya gerekçeyle iptal edebilirsin. Bekleyen talepleri gerekçe yazarak atlayıp planlamaya devam edebilirsin.')
    render_center('planning','planning_requests')

import streamlit as st
from core.request_ui import render_center


def render():
    st.subheader('Planlama Talep Merkezi')
    st.caption('Takım liderinin onaylayıp ilettiği kayıtlar burada değerlendirilir. Onaylanan kayıtlar otomatik vardiya motoruna aktarılır; içerik ve işlem geçmişi tüm ekranlarda aynıdır.')
    render_center('planning','planning_requests')

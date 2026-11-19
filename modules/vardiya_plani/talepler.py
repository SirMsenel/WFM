# Vardiya Plani / Talepler — bu ekranın / servisin uygulama kodu.
import streamlit as st
from ortak.talep_gorunumu import render_center


def render():
    st.subheader('Planlama Talep Merkezi')
    render_center('planning','planning_requests')

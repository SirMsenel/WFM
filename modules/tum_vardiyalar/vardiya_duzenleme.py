"""Tüm Vardiyalar — değişim oluşturma ve Planlama onayı."""
import streamlit as st
from ortak.degisim_ekrani import render_change_form,render_change_approvals
from ortak.gezinme import sections


def render():
    st.subheader('Vardiya Değişim Alanı')
    sections('nav_change_area',{'Yeni Değişiklik':lambda:render_change_form(st.session_state,'all_change'),'Talep ve Onay Takibi':lambda:render_change_approvals(st.session_state)})

"""Tüm Vardiyalar — değişim oluşturma ve Planlama onayı."""
import streamlit as st
from ortak.degisim_ekrani import render_change_form,render_change_approvals
from ortak.gezinme import sections


def render():
    st.subheader('Vardiya Değişim Alanı')
    sections('nav_change_area',{'Yeni Değişiklik':lambda:render_change_form(st.session_state,'all_change'),'Talep ve Onay Takibi':lambda:render_change_approvals(st.session_state),'Ek Mesai Talebi':render_overtime})


def render_overtime():
    from datetime import datetime,time
    from zoneinfo import ZoneInfo
    from ortak.talep_servisi import create_request
    s=st.session_state
    if s['profile'].get('position')!='agent':st.info('Ek mesai talebini personel kendi hesabından iletir.');return
    a,b,c=st.columns(3);day=a.date_input('Ek mesai günü',datetime.now(ZoneInfo('Europe/Istanbul')).date(),key='all_overtime_day');start=b.time_input('Ek mesai başlangıcı',time(17),key='all_overtime_start');end=c.time_input('Ek mesai bitişi',time(20),key='all_overtime_end');reason=st.text_area('Ek mesai gerekçesi',key='all_overtime_reason')
    if st.button('Ek Mesai Talebini İlet',key='all_overtime_send'):
        try:
            if start is None or end is None:raise ValueError('Saatleri doldurun.')
            create_request(s,{'type':'Mesai Talebi','start_date':str(day),'end_date':str(day),'overtime_start':start.strftime('%H:%M'),'overtime_end':end.strftime('%H:%M'),'note':reason});st.success('Talep değerlendirmeye iletildi.')
        except ValueError as e:st.warning(str(e))

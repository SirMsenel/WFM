"""Boş widget değerlerinde kod hatası yerine alanı belirten mesaj."""
import streamlit as st

def number(label,*args,**kwargs):
    value=st.number_input(label,*args,**kwargs)
    if value is None:st.warning(label+' boş kalamaz; lütfen doldurun.');st.stop()
    return value

def clock(label,*args,**kwargs):
    value=st.time_input(label,*args,**kwargs)
    if value is None:st.warning(label+' boş kalamaz; lütfen saat seçin.');st.stop()
    return value

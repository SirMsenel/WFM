"""Ortak, aynı yükseklikte renkli bilgi kartları."""
from html import escape
import streamlit as st

def metric_cards(items):
    colors=['#168390','#7663ac','#619757','#ca8960','#b06999','#5878aa']
    for col,(label,value),color in zip(st.columns(len(items)),items,colors):
        col.markdown(f'<div style="border:1px solid {color}33;border-top:4px solid {color};background:linear-gradient(135deg,{color}0d,#fff);border-radius:17px;padding:17px;min-height:116px;color:{color}"><div style="font-size:13px;font-weight:650">{escape(str(label))}</div><div style="font-size:29px;font-weight:800;margin-top:14px">{escape(str(value))}</div></div>',unsafe_allow_html=True)

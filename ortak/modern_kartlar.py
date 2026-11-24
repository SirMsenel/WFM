"""Ortak, aynı yükseklikte renkli bilgi kartları."""
from html import escape
import streamlit as st

def metric_cards(items,*,equal_height=False):
    colors=['#168390','#7663ac','#619757','#ca8960','#b06999','#5878aa']
    if equal_height:
        cards=[]
        for (label,value),color in zip(items,colors):
            cards.append(f'<div style="padding:16px;border:1px solid {color}44;border-top:4px solid {color};border-radius:17px;background:{color}0d;color:{color};display:flex;flex-direction:column;justify-content:space-between;gap:12px"><b style="font-size:13px">{escape(str(label))}</b><strong style="font-size:clamp(19px,2vw,29px)">{escape(str(value))}</strong></div>')
        st.markdown('<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(140px,100%),1fr));grid-auto-rows:1fr;gap:10px">'+''.join(cards)+'</div>',unsafe_allow_html=True)
        return
    for col,(label,value),color in zip(st.columns(len(items)),items,colors):
        col.markdown(f'<div style="border:1px solid {color}33;border-top:4px solid {color};background:linear-gradient(135deg,{color}0d,#fff);border-radius:17px;padding:17px;min-height:116px;color:{color}"><div style="font-size:13px;font-weight:650">{escape(str(label))}</div><div style="font-size:29px;font-weight:800;margin-top:14px">{escape(str(value))}</div></div>',unsafe_allow_html=True)

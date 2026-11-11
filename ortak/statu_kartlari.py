from html import escape
import pandas as pd
import streamlit as st


def render_status_cards(items):
    st.markdown('#### Planlanan Statülerim')
    for offset in range(0,len(items),3):
        for col,r in zip(st.columns(3),items[offset:offset+3]):
            color={'Yemek':'#258f94','Mola':'#7c69b0','Koçluk':'#c18e44','Cuma':'#b46b8a'}.get(r['kind'],'#66869c');a,b=pd.Timestamp(r['start']),pd.Timestamp(r['end']);minutes=(b-a).total_seconds()/60
            col.markdown(f'<div style="border:1px solid {color}44;background:linear-gradient(130deg,{color}12,#fff);border-radius:18px;padding:18px;margin:6px 0;min-height:135px;color:{color}"><b>{escape(r["kind"])}</b><div style="font-size:24px;font-weight:750;margin:10px 0">{a:%H:%M} → {b:%H:%M}</div><small>{a:%d.%m.%Y} · {minutes:.0f} dakika</small></div>',unsafe_allow_html=True)

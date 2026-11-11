"""Ders programını renkli gün/saat shiftleriyle gösterir."""
from html import escape
import streamlit as st


def render_course_grid(frame,key):
    from ortak.cagri_tahmin_servisi import DAY_NAMES
    if 'Saat' not in frame or not any(c in frame for c in DAY_NAMES):return
    columns=[c for c in DAY_NAMES if c in frame];head='<th>Saat</th>'+''.join('<th>'+escape(c)+'</th>' for c in columns);rows=[]
    for _,r in frame.fillna('').iterrows():
        cells='<td><b>'+escape(str(r['Saat']))+'</b></td>'
        for day in columns:
            value=str(r[day]);cells+='<td style="background:'+('#e5f3f4' if value.strip() else '#f8fafc')+';border-radius:9px;color:#286374">'+escape(value)+'</td>'
        rows.append('<tr>'+cells+'</tr>')
    st.markdown('<div style="overflow:auto;border:1px solid #dce6ee;border-radius:16px;padding:10px"><table style="width:100%;border-spacing:6px;font-size:13px"><thead><tr>'+head+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>',unsafe_allow_html=True)

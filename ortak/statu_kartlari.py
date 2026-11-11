from html import escape
import pandas as pd
import streamlit as st


def render_status_cards(items):
    st.markdown('#### Planlanan Statülerim')
    for offset in range(0,len(items),3):
        for col,r in zip(st.columns(3),items[offset:offset+3]):
            color={'Yemek':'#258f94','Mola':'#7c69b0','Koçluk':'#c18e44','Cuma':'#b46b8a'}.get(r['kind'],'#66869c');a,b=pd.Timestamp(r['start']),pd.Timestamp(r['end']);minutes=(b-a).total_seconds()/60
            col.markdown(f'<div style="border:1px solid {color}44;background:linear-gradient(130deg,{color}12,#fff);border-radius:18px;padding:18px;margin:6px 0;min-height:135px;color:{color}"><b>{escape(r["kind"])}</b><div style="font-size:24px;font-weight:750;margin:10px 0">{a:%H:%M} → {b:%H:%M}</div><small>{a:%d.%m.%Y} · {minutes:.0f} dakika</small></div>',unsafe_allow_html=True)


def render_status_list(items):
    st.divider();st.markdown('### Planlanan Statülerim')
    for r in sorted(items,key=lambda x:x['start']):
        a,b=pd.Timestamp(r['start']),pd.Timestamp(r['end']);color={'Yemek':'#258f94','Mola':'#7c69b0','Koçluk':'#c18e44'}.get(r['kind'],'#66869c')
        st.markdown(f'<div style="padding:14px 18px;margin:8px 0;border-left:5px solid {color};border-radius:12px;background:{color}12;display:flex;justify-content:space-between;gap:16px"><b style="color:{color}">{escape(r["kind"])}</b><span>{a:%d.%m.%Y} · {a:%H:%M} – {b:%H:%M}</span><b>{(b-a).total_seconds()/60:.0f} dk</b></div>',unsafe_allow_html=True)


def status_cells(items,people,start,end):
    """Statüyü başladığı geceye değil bağlı olduğu vardiya tarihine yerleştir."""
    from ortak.cagri_tahmin_servisi import DAY_NAMES
    lookup={str(p['employee_id']):i for i,p in enumerate(people)};result={};left,right=pd.Timestamp(start).date(),pd.Timestamp(end).date()
    for item in items:
        if item.get('status')=='İptal' or str(item['employee_id']) not in lookup:continue
        day=pd.Timestamp(item.get('date') or item['start'][:10]).date()
        if not left<=day<=right:continue
        col=f'{day:%d.%m} '+DAY_NAMES[day.weekday()];key=(lookup[str(item['employee_id'])],col);result.setdefault(key,[]).append(item)
    for key in result:result[key].sort(key=lambda x:x['start'])
    return result


def compact_status_html(items,label=''):
    parts=[]
    for item in items:
        a,b=pd.Timestamp(item['start']),pd.Timestamp(item['end']);color={'Yemek':'#258f94','Mola':'#7c69b0','Koçluk':'#b17c2c','Cuma':'#ad658a'}.get(item['kind'],'#66869c');minutes=(b-a).total_seconds()/60
        clock=f'{a:%H:%M}–{b:%H:%M}'
        if str(item.get('date') or a.date())!=str(a.date()):clock=f'{a:%d.%m} '+clock
        parts.append(f'<div class="tracking-status-mini" style="margin-top:5px;padding:7px 8px;border-radius:8px;border-left:3px solid {color};background:{color}13;color:{color};text-align:left;white-space:normal;line-height:1.4;font-size:11px"><b>{escape(item["kind"])}</b><span style="float:right;margin-left:5px">{minutes:.0f} dk</span><div style="white-space:nowrap">{escape(clock)}</div></div>')
    return ''.join(parts)

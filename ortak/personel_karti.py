"""Personel Kartı — kimlik, şirket, ekip ve işe girişe göre kıdem."""
from datetime import datetime
from zoneinfo import ZoneInfo
from html import escape
import pandas as pd
import streamlit as st
from ortak.personel import get_people,visible_people,WORK_LABELS,LANG_LABELS


def tenure(start,today=None):
    today=today or datetime.now(ZoneInfo('Europe/Istanbul')).date()
    parsed=pd.to_datetime(start,errors='coerce')
    if pd.isna(parsed):return 'İşe giriş tarihi bekleniyor','#64748b','#edf2f7'
    begin=parsed.date()
    if begin>today:return 'İşe başlamadı','#a85d12','#fff4dc'
    months=(today.year-begin.year)*12+today.month-begin.month-(today.day<begin.day)
    for limit,label,fg,bg in [(3,'0–3 ay','#206ea2','#e6f3ff'),(6,'3–6 ay','#247d7b','#e2f5f1'),(12,'6–12 ay','#3f7a36','#edf7e4'),(24,'1–2 yıl','#7156a8','#f1eaff'),(36,'2–3 yıl','#9e6b17','#fff2d8')]:
        if months<limit:return label,fg,bg
    return '3+ yıl','#a14e72','#fbe8f0'


def pick_person(state,current,key='tracking'):
    if current.get('position')=='agent':
        person=next((p for p in get_people(state) if str(p['employee_id'])==str(current.get('employee_id'))),current)
        return person
    with st.container(border=True):
        a,b,c=st.columns([2,1.2,1.3]);query=a.text_input('Personel ara',placeholder='Ad soyad, sicil, kullanıcı adı',key=key+'_query')
        people=visible_people(current,get_people(state))
        cities=['Tümü']+sorted({p.get('location') or 'Belirtilmemiş' for p in people});teams=['Tümü']+sorted({p.get('team_lead') or 'Belirtilmemiş' for p in people})
        city=b.selectbox('Şehir',cities,key=key+'_city');team=c.selectbox('Takım',teams,key=key+'_team')
        items=[p for p in people if (city=='Tümü' or (p.get('location') or 'Belirtilmemiş')==city) and (team=='Tümü' or (p.get('team_lead') or 'Belirtilmemiş')==team) and (not query or query.casefold() in ' '.join(str(p.get(k,'')) for k in ['full_name','sicil_no','username','company']).casefold())]
        byid={str(p['employee_id']):p for p in items}
        if not byid:st.info('Filtreye uygun personel yok.');return
        selected=st.selectbox('Personel',list(byid),format_func=lambda i:byid[i]['full_name'],key=key+'_person')
        return byid[selected]


def render_person(person):
    label,color,bg=tenure(person.get('employment_start'));name=escape(str(person.get('full_name') or 'Personel'));initials=''.join(w[0] for w in str(person.get('full_name') or '?').split()[:2]).upper()
    hire=pd.to_datetime(person.get('employment_start'),errors='coerce');hire_label='—' if pd.isna(hire) else hire.strftime('%d.%m.%Y')
    left,right=st.columns([3,1])
    def item(label,value):return '<div><small style="color:#64808c">'+escape(label)+'</small><div style="font-weight:600;margin-top:4px;color:#234453">'+escape(str(value or '—'))+'</div></div>'
    content=''.join(item(k,v) for k,v in [('Şehir',person.get('location')),('Şirket',person.get('company')),('Takım Lideri',person.get('team_lead')),('Yönetici',person.get('manager')),('Çalışma biçimi',WORK_LABELS.get(person.get('work_type'),person.get('work_type'))),('Dil',LANG_LABELS.get(person.get('language'),person.get('language')))])
    left.markdown(f'<div style="border:1px solid #d7e6ec;border-radius:21px;background:linear-gradient(120deg,#f0f8fa,#fff);padding:22px;min-height:255px;box-sizing:border-box"><div style="display:flex;gap:15px;align-items:center;margin-bottom:20px"><div style="background:#d5edf1;color:#187389;width:54px;height:54px;display:grid;place-items:center;border-radius:17px;font-size:22px;font-weight:750">{escape(initials)}</div><div><div style="font-size:23px;font-weight:750;color:#193f51">{name}</div><small style="color:#64808c">Sicil {escape(str(person.get("sicil_no") or person.get("employee_id")))} · @{escape(str(person.get("username") or ""))}</small></div></div><div style="display:grid;grid-template-columns:repeat(3,1fr);gap:17px">{content}</div></div>',unsafe_allow_html=True)
    right.markdown(f'<div style="border:1px solid {color}33;border-radius:21px;background:{bg};padding:22px;min-height:255px;box-sizing:border-box;color:{color}"><div style="font-size:13px;font-weight:700;letter-spacing:1px">KIDEM</div><div style="font-size:25px;font-weight:800;margin:22px 0">{escape(label)}</div><small>İşe giriş</small><div style="font-weight:650;margin-top:5px">{hire_label}</div></div>',unsafe_allow_html=True)

"""Grup yemek/mola, Cuma ve yarım saat kayıp kuralları."""
from copy import deepcopy
import streamlit as st
from ortak.statuler import defaults
from ortak.personel import WORK_LABELS
from ortak.calisma_alani_deposu import save_keys


def render():
    s=st.session_state;cfg=deepcopy(s.get('status_rules') or defaults());cfg['enabled']=st.toggle('Vardiyalara otomatik yemek/statü yerleştir',value=cfg.get('enabled',False),key='status_enabled')
    st.caption('Shrinkage diğer kayıpları temsil eder. Burada planlanan yemek ve molalar kapasiteden ayrıca düşülür.')
    cols=st.columns(2)
    for i,(g,r) in enumerate(cfg['groups'].items()):
        with cols[i%2].container(border=True):
            st.markdown('#### '+WORK_LABELS.get(g,g));r['meal_minutes']=st.number_input('Yemek (dk)',0,120,int(r['meal_minutes']),15,key='meal_d_'+g)
            r['relative']=st.checkbox('Pencere vardiya başlangıcına göre',value=r.get('relative',True),key='meal_relative_'+g)
            if r['relative']:
                r['after_start']=st.number_input('Vardiyadan kaç saat sonra başlar',1.,8.,float(r.get('after_start',3)),.5,key='meal_after_'+g);r['before_start']=st.number_input('Vardiyadan kaç saat sonra biter',1.,12.,float(r.get('before_start',6)),.5,key='meal_before_'+g)
            r['meal_start']=st.text_input('Yemek başlangıç penceresi',r['meal_start'],key='meal_s_'+g);r['meal_end']=st.text_input('Yemek bitiş penceresi',r['meal_end'],key='meal_e_'+g)
            r['break_minutes']=st.number_input('Talep edilebilen mola (dk)',5,60,int(r['break_minutes']),5,key='break_d_'+g)
            r['min_shift_hours']=st.number_input('Yemek için en az vardiya (saat)',1.,12.,float(r['min_shift_hours']),.5,key='meal_min_'+g)
    with st.container(border=True):
        st.markdown('#### Cuma öğlen statüsü');r=cfg['friday'];r['enabled']=st.checkbox('Cuma öğlen arası uygula',value=r.get('enabled',False));r['male_only']=st.checkbox('Yalnızca erkek personeller',value=r.get('male_only',False))
        a,b,c=st.columns(3);r['start']=a.text_input('Cuma başlangıç',r['start']);r['end']=b.text_input('Cuma bitiş',r['end']);r['minutes']=c.number_input('Cuma süresi (dk)',15,120,int(r['minutes']),15)
    if st.button('Statü Kurallarını Kaydet',key='status_save'):
        try:
            import datetime
            for r in [*cfg['groups'].values(),cfg['friday']]:
                a=r.get('meal_start',r.get('start'));b=r.get('meal_end',r.get('end'));start=datetime.time.fromisoformat(a);end=datetime.time.fromisoformat(b)
                if end<=start:raise ValueError('Pencere bitişi başlangıçtan sonra olmalı.')
                if r.get('relative') and r['before_start']<=r['after_start']:raise ValueError('Vardiyaya göre yemek penceresinin bitişi başlangıçtan sonra olmalı.')
            s['status_rules']=cfg;save_keys(s);st.success('Statü kuralları kaydedildi. Taslağı yeniden oluşturun.')
        except ValueError as e:st.error(str(e))

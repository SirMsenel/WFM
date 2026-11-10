"""Kompakt ikili kartlarda vardiya kuralları."""
from copy import deepcopy
from datetime import time
import streamlit as st
from ortak.personel import WORK_LABELS
from ortak.cagri_tahmin_servisi import DAY_NAMES
from ortak.calisma_alani_deposu import save_keys


def render():
    s=st.session_state;r=deepcopy(s['shift_rules']);st.subheader('Mesai Kuralları');a,b=st.columns(2)
    with a.container(border=True):
        st.markdown('#### Genel saatler');g=r['general']
        for k,label in [('weekday_general_start','Hafta içi giriş'),('weekend_general_start','Hafta sonu giriş'),('global_latest_end','Genel son çıkış')]:g[k]=st.time_input(label,value=time.fromisoformat(g[k]),key='p7_'+k).strftime('%H:%M')
        boost=r['boosts'];boost['weekday_0700_fulltime_extra_enabled']=st.checkbox('07:00 Full Time takviyesi',boost.get('weekday_0700_fulltime_extra_enabled',False));boost['weekday_0700_fulltime_extra_count']=st.number_input('07:00 kişi sayısı',0,100,int(boost.get('weekday_0700_fulltime_extra_count',0)))
    with b.container(border=True):
        st.markdown('#### Gece kuralları');n=r['night'];n['enabled']=st.checkbox('Gece etkin',n.get('enabled',True));n['mode']=st.selectbox('Gece dönemi',['normal','ramazan','ozel'],index=['normal','ramazan','ozel'].index(n.get('mode','normal')))
        for k,label in [('night_window_start','Gece başlangıç'),('night_window_end','Gece bitiş')]:g[k]=st.time_input(label,value=time.fromisoformat(g[k]),key='p7_'+k).strftime('%H:%M')
        target=n.setdefault(n['mode'],{'tr':0,'en':0,'ar':0});cols=st.columns(3)
        for col,lang in zip(cols,['tr','en','ar']):target[lang]=col.number_input(lang.upper(),0,100,int(target.get(lang,0)))
        n['allowed_work_types']=st.multiselect('Gece grupları',list(WORK_LABELS),default=n.get('allowed_work_types',['akademi']))
    cols=st.columns(2)
    for i,(group,rule) in enumerate(r['work_type'].items()):
        with cols[i%2].container(border=True):
            st.markdown('#### '+WORK_LABELS.get(group,group))
            if group=='akademi':rule['shift_total_hours_max']=st.number_input('Vardiya üst süresi',1.,12.,float(rule.get('shift_total_hours_max',7)),.5,key='p7_hours_'+group)
            else:st.metric('Normal vardiya',str(rule['shift_total_hours'])+' saat')
            rule['min_shift_hours']=st.number_input('En az vardiya (saat)',.5,float(rule.get('shift_total_hours_max',rule.get('shift_total_hours',7))),float(rule.get('min_shift_hours',4)),.5,key='p7_min_'+group)
            rule['min_off_days']=st.number_input('Haftalık en az OFF',1,6,int(rule.get('min_off_days',2 if group=='fulltime' else 1)),key='p7_off_'+group)
            rule['preferred_off_days']=st.multiselect('Öncelikli OFF günleri',list(range(7)),default=rule.get('preferred_off_days',[]),format_func=lambda i:DAY_NAMES[i],key='p7_pref_'+group)
            rule['max_consecutive_days']=st.number_input('Üst üste en fazla gün',1,6,int(rule.get('max_consecutive_days',6)),key='p7_consecutive_'+group)
            rule['min_rest_hours']=st.number_input('En az dinlenme',11,24,int(rule.get('min_rest_hours',11)),key='p7_rest_'+group)
            if group=='fulltime':rule['allow_6th_day']=st.checkbox('6. gün çalışılabilir',rule.get('allow_6th_day',True));rule['max_days_per_week_default']=min(6,7-rule['min_off_days'])
            else:rule['max_days_per_week']=min(6,7-rule['min_off_days'])
            if 'max_end_time' in rule:
                rule['max_end_time']=st.time_input('Grup son çıkış',time.fromisoformat(rule['max_end_time']),key='p7_last_'+group).strftime('%H:%M');rule['max_end_is_hard']=st.checkbox('Bitiş sınırı Hard',rule.get('max_end_is_hard',True),key='p7_hard_'+group);rule['override_required_if_violate']=st.checkbox('Soft aşımında onay iste',rule.get('override_required_if_violate',True),key='p7_soft_'+group)
    with cols[1].container(border=True):
        st.markdown('#### Kapasite ve ek mesai');capacity=r.setdefault('capacity',{})
        capacity['max_overstaff']=st.number_input('Bir dilimde izin verilen fazla personel',0,100,int(capacity.get('max_overstaff',2)))
        capacity['min_overtime_hours']=st.number_input('Yeni ek mesai bloğu en az saat',.5,10.,float(capacity.get('min_overtime_hours',4)),.5)
        school=r.setdefault('school',{});school['holiday_priority']=st.checkbox('Bayram önceliği',school.get('holiday_priority',True));school['summer_months']=st.multiselect('Ders uygulanmayan yaz ayları',list(range(1,13)),default=school.get('summer_months',[6,7,8]))
    sync=st.checkbox('Seçili dönemin kesin gece kayıtlarını yeni saatlere uyarla',True,key='rules_sync_nights')
    if st.button('Kaydet ve Uygula',key='rules_apply',type='primary'):
        from ortak.mesai_kurallari_servisi import apply_rules
        apply_rules(s,r,sync);st.success('Kurallar kaydedildi. Taslağı yeniden oluşturun.')
        from ortak.gece_kontrolleri import show_night_popup
        show_night_popup(s)

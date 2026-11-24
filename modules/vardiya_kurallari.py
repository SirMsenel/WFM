"""Kompakt ikili kartlarda vardiya kuralları."""
from copy import deepcopy
from datetime import time
import streamlit as st
from ortak.zorunlu_alanlar import number,clock
from ortak.personel import WORK_LABELS
from ortak.cagri_tahmin_servisi import DAY_NAMES
from ortak.calisma_alani_deposu import save_keys


def render():
    s=st.session_state;r=deepcopy(s['shift_rules']);st.subheader('Mesai Kuralları');a,b=st.columns(2)
    with a.container(border=True,height=550):
        st.markdown('#### Genel saatler');g=r['general']
        for k,label in [('weekday_general_start','Hafta içi giriş'),('weekend_general_start','Hafta sonu giriş'),('global_latest_end','Genel son çıkış')]:g[k]=clock(label,value=time.fromisoformat(g[k]),key='p7_'+k).strftime('%H:%M')
        boost=r['boosts'];boost['weekday_0700_fulltime_extra_enabled']=st.checkbox('07:00 Full Time takviyesi',boost.get('weekday_0700_fulltime_extra_enabled',False));boost['weekday_0700_fulltime_extra_count']=number('07:00 kişi sayısı',0,100,int(boost.get('weekday_0700_fulltime_extra_count',0)))
    with b.container(border=True,height=550):
        st.markdown('#### Gece kuralları');n=r['night'];n['enabled']=st.checkbox('Gece etkin',n.get('enabled',True));n['mode']=st.selectbox('Gece dönemi',['normal','ramazan','ozel'],index=['normal','ramazan','ozel'].index(n.get('mode','normal')))
        n['auto_fill']=st.checkbox('Eksik gece kotasını otomatik tamamla',n.get('auto_fill',True),help='Taslak oluşturulurken geceye uygun grup, dil ve dinlenme kurallarıyla boşta kalan personel aranır. Uygun kişi bulunamazsa eksik görünür kalır.')
        n['weekly_pattern_enabled']=st.checkbox('Gece vardiyalarını haftalık blok halinde dağıt',n.get('weekly_pattern_enabled',False),help='Personelleri dengeli olarak ilk 3 gece + 4 OFF veya ilk 3 OFF + son 4 gece düzenine ayırır.')
        if n['weekly_pattern_enabled']:
            enforcement=st.segmented_control('Gece blok kuralı',['Esnek','Kesin'],default='Kesin' if n.get('weekly_pattern_hard') else 'Esnek',key='night_weekly_pattern_strength') or 'Esnek'
            n['weekly_pattern_hard']=enforcement=='Kesin'
            st.caption('Esnek: ihtiyaç karşılanamazsa blok dışına çıkabilir ve uyarı üretir. Kesin: personelin belirlenen 3/4 günlük gece bloğu dışına vardiya yazılmaz.')
        for k,label in [('night_window_start','Gece başlangıç'),('night_window_end','Gece bitiş')]:g[k]=clock(label,value=time.fromisoformat(g[k]),key='p7_'+k).strftime('%H:%M')
        target=n.setdefault(n['mode'],{'tr':0,'en':0,'ar':0});cols=st.columns(3)
        for col,lang in zip(cols,['tr','en','ar']):target[lang]=col.number_input(lang.upper(),0,100,int(target.get(lang,0)))
        n['break_total_minutes']=number('8 saatlik gece vardiyasında toplam mola (dk)',0,120,int(n.get('break_total_minutes',60)),5,key='night_break_minutes')
        n['allowed_work_types']=st.multiselect('Gece grupları',list(WORK_LABELS),default=n.get('allowed_work_types',['akademi']))
    cols=st.columns(3)
    for i,group in enumerate(['dis_kaynak','akademi','fulltime']):
        rule=r['work_type'][group]
        with cols[i].container(border=True,height=790):
            st.markdown('#### '+WORK_LABELS.get(group,group))
            if group=='akademi':rule['shift_total_hours_max']=number('Vardiya üst süresi',1.,12.,float(rule.get('shift_total_hours_max',7)),.5,key='p7_hours_'+group)
            else:rule['shift_total_hours']=number('Vardiya süresi (saat)',1.,12.,float(rule.get('shift_total_hours',9)),.5,key='p8_hours_'+group);rule['duration_custom']=True;rule.pop('shift_total_hours_max',None)
            limit=float(rule.get('shift_total_hours_max',rule.get('shift_total_hours',7)))
            if s.get('p7_min_'+group,0)>limit:s['p7_min_'+group]=limit
            rule['min_shift_hours']=number('En az vardiya (saat)',.5,float(rule.get('shift_total_hours_max',rule.get('shift_total_hours',7))),min(float(rule.get('min_shift_hours',4)),float(rule.get('shift_total_hours_max',rule.get('shift_total_hours',7)))),.5,key='p7_min_'+group)
            rule['min_off_days']=number('Haftalık en az OFF',1,6,int(rule.get('min_off_days',2 if group=='fulltime' else 1)),key='p7_off_'+group)
            rule['preferred_off_days']=st.multiselect('Öncelikli OFF günleri',list(range(7)),default=rule.get('preferred_off_days',[]),format_func=lambda i:DAY_NAMES[i],key='p7_pref_'+group)
            rule['max_consecutive_days']=number('Üst üste en fazla gün',1,6,int(rule.get('max_consecutive_days',6)),key='p7_consecutive_'+group)
            rule['min_rest_hours']=number('En az dinlenme',11,24,int(rule.get('min_rest_hours',11)),key='p7_rest_'+group)
            if group=='fulltime':rule['allow_6th_day']=st.checkbox('6. gün çalışılabilir',rule.get('allow_6th_day',True));rule['max_days_per_week_default']=min(6,7-rule['min_off_days'])
            else:rule['max_days_per_week']=min(6,7-rule['min_off_days'])
            if 'max_end_time' in rule:
                rule['max_end_time']=clock('Grup son çıkış',time.fromisoformat(rule['max_end_time']),key='p7_last_'+group).strftime('%H:%M');rule['max_end_is_hard']=st.checkbox('Bitiş sınırı Hard',rule.get('max_end_is_hard',True),key='p7_hard_'+group);rule['override_required_if_violate']=st.checkbox('Soft aşımında onay iste',rule.get('override_required_if_violate',True),key='p7_soft_'+group)
    with st.container(border=True):
        st.markdown('#### Kapasite ve ek mesai');capacity=r.setdefault('capacity',{})
        st.caption('Bu kurallar ihtiyacı kapatırken sistemin ne kadar esneyebileceğini belirler; personelin çalışma süresi ve dinlenme kuralları yine korunur.')
        x,y=st.columns(2)
        with x:
            capacity['max_overstaff']=number('Türkçe planda dilim başına izin verilen fazla personel',0,100,int(capacity.get('max_overstaff',2)),help='İhtiyaç 10 ise ve değer 2 ise o yarım saatte en fazla 12 kişi planlanabilir.')
            capacity['foreign_max_overstaff']=number('Yabancı dil planında dilim başına izin verilen fazla personel',0,100,int(capacity.get('foreign_max_overstaff',0)),key='foreign_overstaff_limit')
            capacity['min_overtime_hours']=number('Yeni ek mesainin en kısa süresi (saat)',.5,10.,float(capacity.get('min_overtime_hours',4)),.5,help='Boş güne önerilecek yeni çalışma bloğu bundan kısa olamaz.')
        with y:
            capacity['recommendation_overstaff_limit']=number('Açık kapatma önerisinde izin verilen fazla kişi',0,5,int(capacity.get('recommendation_overstaff_limit',5)),1,help='Öneri sistemi parçalı eksikleri birleştirirken bu sınıra kadar artıya geçebilir.')
            capacity['bridge_gap_slots']=number('Eksik blokları birleştirme toleransı (yarım saat)',0,6,int(capacity.get('bridge_gap_slots',1)),key='bridge_gap_slots',help='İki eksik blok arasında bu kadar dolu yarım saat varsa tek vardiya önerisi üretilebilir.')
        school=r.setdefault('school',{});school['holiday_priority']=st.checkbox('Bayram önceliği',school.get('holiday_priority',True));school['summer_months']=st.multiselect('Ders uygulanmayan yaz ayları',list(range(1,13)),default=school.get('summer_months',[6,7,8]))
    sync=st.checkbox('Seçili dönemin kesin gece kayıtlarını yeni saatlere uyarla',True,key='rules_sync_nights')
    if st.button('Kaydet ve Uygula',key='rules_apply',type='primary'):
        from ortak.mesai_kurallari_servisi import apply_rules
        try:
            apply_rules(s,r,sync);st.success('Kurallar kaydedildi. Taslağı yeniden oluşturun.')
        except (ValueError,TypeError) as e:st.warning('Kurallar kaydedilemedi: '+str(e));return
        from ortak.gece_kontrolleri import show_night_popup
        show_night_popup(s)

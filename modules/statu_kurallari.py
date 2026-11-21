"""Statü odaklı süre hakları; saatleri kapasite planlayıcısı seçer."""
from copy import deepcopy
import math
import pandas as pd
import streamlit as st
from ortak.zorunlu_alanlar import number,clock
from ortak.statuler import defaults
from ortak.personel import WORK_LABELS
from ortak.calisma_alani_deposu import save_keys


def validate(cfg):
    if not 0<=float(cfg.get('operation_reserve_rate',.05))<=.5:raise ValueError('Operasyon rezervi %0–50 arasında olmalı.')
    for group,r in cfg['groups'].items():
        for key in ['meal_minutes','break_minutes','coaching_monthly_minutes','coaching_chunk_minutes']:
            value=r.get(key,0)
            if value is None or not math.isfinite(float(value)):raise ValueError(WORK_LABELS.get(group,group)+': süre alanı boş kalamaz. Lütfen doldurun.')
            if float(value)<0:raise ValueError('Süre negatif olamaz.')
        if not 1<=int(r.get('break_preferred_minutes',10))<=min(15,int(r.get('break_minutes',15))):raise ValueError(WORK_LABELS[group]+': tercih edilen mola parçası tek mola üst sınırını aşamaz.')
        if any(not all(pd.notna(row.get(c)) for c in ['min_hours','max_hours','minutes']) for row in r.get('break_rules',[])):raise ValueError(WORK_LABELS[group]+': mola tablosunda boş alan var. Çalışma sınırlarını ve toplam mola süresini doldurun.')
        ranges=sorted(r.get('break_rules',[]),key=lambda x:x['min_hours'])
        if 'break_rules' in r and not ranges:raise ValueError(WORK_LABELS[group]+': mola tablosu boş; molasız çalışma için açıkça 0 dakika tanımlayın.')
        for n,row in enumerate(ranges):
            if not all(pd.notna(row.get(c)) for c in ['min_hours','max_hours','minutes']):raise ValueError(WORK_LABELS[group]+': mola tablosunda boş alan var. Başlangıç, bitiş ve süreyi doldurun.')
            if not 0<=float(row['min_hours'])<float(row['max_hours'])<=24 or not math.isfinite(float(row['minutes'])) or float(row['minutes'])<0 or not float(row['minutes']).is_integer():raise ValueError('Mola saat sınırları 0–24 içinde ve başlangıç bitişten küçük olmalı.')
            if n and float(ranges[n-1]['max_hours'])>float(row['min_hours']):raise ValueError('Mola çalışma saati aralıkları çakışamaz.')
            if n and float(ranges[n-1]['max_hours'])<float(row['min_hours']):raise ValueError(WORK_LABELS[group]+': mola aralıkları arasında boşluk var; molasız aralık için açıkça 0 dakika tanımlayın.')
    return cfg


def render():
    s=st.session_state;cfg=deepcopy(s.get('status_rules_edit') or s.get('status_rules') or defaults());cfg.update(automatic=True,shrinkage_included=True,coaching_by_leader=True);cfg['enabled']=True
    st.info('Yemek ve mola hakları vardiya oluşturulurken tamamen ve otomatik dağıtılır. Koçluk kalan kapasiteden ayrılır.')
    def panel(kind):
        cols=st.columns(3)
        for col,group in zip(cols,['fulltime','akademi','dis_kaynak']):
            rule=cfg['groups'].setdefault(group,{})
            with col.container(border=True):
                st.markdown('#### '+WORK_LABELS[group])
                if kind=='Yemek':
                    choice=st.radio('Yemek hakkı',['Var','Yok'],index=1 if rule.get('meal_disabled') else 0,horizontal=True,key='meal_choice_'+group);rule['meal_disabled']=choice=='Yok'
                    if rule['meal_disabled']:rule.update(meal_minutes=0,min_shift_hours=0,meal_day_overrides=[]);st.caption('Yemek molası ve minimum çalışma koşulu kapalı.')
                    else:
                        rule['meal_minutes']=number('Yemek süresi (dk)',5,120,max(5,int(rule.get('meal_minutes',30))),5,key='meal_d_'+group);rule['min_shift_hours']=number('Yemek hakkı için en az çalışma (saat)',0.,12.,float(rule.get('min_shift_hours',4)),.5,key='meal_min_'+group)
                        from ortak.cagri_tahmin_servisi import DAY_NAMES
                        old=rule.get('meal_day_overrides',[{}]);selected=st.multiselect('Farklı yemek süresi uygulanacak günler',list(range(7)),default=old[0].get('weekdays',[]) if old else [],format_func=lambda x:DAY_NAMES[x],key='meal_special_days_'+group)
                        duration=number('Seçili günlerde yemek (dk)',5,180,int(old[0].get('minutes',60)) if old else 60,5,key='meal_special_minutes_'+group) if selected else 0
                        rule['meal_day_overrides']=[{'weekdays':selected,'minutes':duration}] if selected else []
                elif kind=='Mola':
                    rule['break_first_minutes']=number('Mesai başlangıcından itibaren en erken mola süresi (dk)',0,180,int(rule.get('break_first_minutes',60)),15,key='break_first_'+group);rule['break_last_minutes']=number('Mesai bitiminden önce mola verilmeyecek süre (dk)',0,180,int(rule.get('break_last_minutes',60)),15,key='break_last_'+group)
                    rule['break_minutes']=number('Tek mola en fazla (dk)',1,15,min(15,int(rule.get('break_minutes',15))),5,key='break_d_'+group);rule['break_per_hour_max']=number('Bir saat içinde en fazla mola (dk)',5,60,int(rule.get('break_per_hour_max',15)),5,key='break_hour_'+group)
                    rule['break_min_gap_minutes']=number('İki mola arasında en az süre (dk)',0,180,int(rule.get('break_min_gap_minutes',15)),5,key='break_gap_'+group)
                    rule['break_preferred_minutes']=number('Tercih edilen mola parçası (dk)',1,min(15,int(rule['break_minutes'])),min(int(rule.get('break_preferred_minutes',10)),int(rule['break_minutes'])),1,key='break_preferred_'+group)
                    st.markdown('<div style="margin:10px 0 7px;padding:11px 13px;border-radius:13px;background:#f2f8fa;border:1px solid #dce9ee"><b>Çalışma süresine göre toplam mola hakkı</b><br><small>Alt sınır hariç, üst sınır dahildir.</small></div>',unsafe_allow_html=True)
                    preset=st.selectbox('Hızlı kural şablonu',['Mevcut kuralları düzenle','Standart · 3,5 saate kadar 15 dk, üzeri 30 dk','Kısa vardiya · 4 saate kadar 15 dk, üzeri 30 dk'],key='break_preset_'+group)
                    rules=rule.get('break_rules',[{'min_hours':0,'max_hours':3.5,'minutes':15},{'min_hours':3.5,'max_hours':24,'minutes':30}])
                    if preset.startswith('Standart'):rules=[{'min_hours':0,'max_hours':3.5,'minutes':15},{'min_hours':3.5,'max_hours':24,'minutes':30}]
                    elif preset.startswith('Kısa vardiya'):rules=[{'min_hours':0,'max_hours':4,'minutes':15},{'min_hours':4,'max_hours':24,'minutes':30}]
                    df=pd.DataFrame(rules).rename(columns={'min_hours':'Çalışma alt sınırı (hariç)','max_hours':'Çalışma üst sınırı (dahil)','minutes':'Toplam mola (dk)'})
                    with st.container(border=True):
                        table=st.data_editor(df,num_rows='dynamic',hide_index=True,use_container_width=True,key='break_rules_'+group,column_config={'Çalışma alt sınırı (hariç)':st.column_config.NumberColumn('Alt sınır',required=True,min_value=0,max_value=24,step=.5,width='small'),'Çalışma üst sınırı (dahil)':st.column_config.NumberColumn('Üst sınır',required=True,min_value=.5,max_value=24,step=.5,width='small'),'Toplam mola (dk)':st.column_config.NumberColumn('Hak (dk)',required=True,min_value=0,max_value=240,step=5,width='small')})
                    rule['break_rules']=table.rename(columns={'Çalışma alt sınırı (hariç)':'min_hours','Çalışma üst sınırı (dahil)':'max_hours','Toplam mola (dk)':'minutes'}).to_dict('records')

                else:
                    rule['coaching_multiple_per_week']=st.checkbox('Aynı hafta birden fazla koçluk yapılabilir',value=rule.get('coaching_multiple_per_week',False),key='coach_multiple_'+group)
                    rule['coaching_monthly_minutes']=number('Aylık kişi başı koçluk (dk)',0,480,int(rule.get('coaching_monthly_minutes',60)),15,key='coach_month_'+group);rule['coaching_chunk_minutes']=number('Her görüşme parçası (dk)',5,60,int(rule.get('coaching_chunk_minutes',15)),5,key='coach_chunk_'+group)
        if kind=='Koçluk':
            cfg['operation_reserve_rate']=number('Yemek/mola sonrası kalan kapasiteden operasyon rezervi (%)',0.,50.,float(cfg.get('operation_reserve_rate',.05))*100,1.,key='operation_reserve_percent')/100
            cfg['coaching_slot_minutes']=15
            st.caption('Takım lideri uygun 15 dakikalık saat kutularından seçim yapar ve onaylar.')
        if kind=='Koçluk':st.caption('Önce yemek ve mola haklarının tamamı dağıtılır. Kalan kapasiteden operasyon rezervi korunur; geri kalanı ortak koçluk kontenjanıdır. Takım lideri kendi vardiyası ve kişinin uygunluğuna göre atar; aylık kişi sınırı atama sırasında korunur.')
        if kind=='Yemek':st.caption('Yemek saatlerini sistem vardiya içinde hat durumuna göre seçer; yayınlandığında personelin takvimine düşer.')
    kind=st.segmented_control('Statü',['Yemek','Mola','Koçluk','Cuma'],default='Yemek',key='status_kind') or 'Yemek'
    if kind=='Cuma':
        f=cfg.setdefault('friday',{});f['enabled']=False;f['male_only']=False
        st.info('Cuma öğlen ayrı bir süre/statü olarak düşülmez. Seçtiğin gruplarda 12:00–14:00 aralığını kapsayan vardiyalar kadın personele yönlendirilir.')
        cols=st.columns(3);group_rules=f.setdefault('group_rules',{})
        for col,group in zip(cols,['fulltime','akademi','dis_kaynak']):
            current=group_rules.setdefault(group,{})
            with col.container(border=True):
                st.markdown('#### '+WORK_LABELS[group])
                current['avoid_male_midday']=st.toggle('Erkek personele Cuma öğlen vardiyası yazma',current.get('avoid_male_midday',group=='akademi'),key='friday_avoid_'+group)
                if current['avoid_male_midday']:
                    current['hard']=st.segmented_control('Kural tipi',['Esnek','Kesin'],default='Kesin' if current.get('hard') else 'Esnek',key='friday_strength_'+group)=='Kesin'
                    st.caption('Esnek kural ihtiyaç halinde aşılır ve yayın öncesi uyarı verir.' if not current['hard'] else 'Kesin kural uygun olmayan vardiyayı engeller.')
        f['prefer_women_midday']=any(r.get('avoid_male_midday') for r in group_rules.values());f['block_men_midday']=False
    else:panel(kind)
    # Keep edits when switching between status windows; persist only on explicit save.
    s['status_rules_edit']=cfg
    if st.button('Statü Kurallarını Kaydet',key='status_save'):
        try:
            validate(cfg);s['status_rules']=cfg;s['shift_rules']['friday']={'prefer_women_midday':cfg['friday'].get('prefer_women_midday',True),'block_men_midday':False,'group_rules':cfg['friday'].get('group_rules',{})};save_keys(s);st.success('Statü hakları kaydedildi. Saatler yeni vardiya planıyla otomatik oluşur.')
        except (ValueError,TypeError,KeyError) as e:st.warning(str(e))

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
    for group,r in cfg['groups'].items():
        for key in ['meal_minutes','break_minutes','coaching_monthly_minutes','coaching_chunk_minutes']:
            value=r.get(key,0)
            if value is None or not math.isfinite(float(value)):raise ValueError(WORK_LABELS.get(group,group)+': süre alanı boş kalamaz. Lütfen doldurun.')
            if float(value)<0:raise ValueError('Süre negatif olamaz.')
        if any(not all(pd.notna(row.get(c)) for c in ['min_hours','max_hours','minutes']) for row in r.get('break_rules',[])):raise ValueError(WORK_LABELS[group]+': mola tablosunda boş alan var. Çalışma sınırlarını ve toplam mola süresini doldurun.')
        ranges=sorted(r.get('break_rules',[]),key=lambda x:x['min_hours'])
        for n,row in enumerate(ranges):
            if not all(pd.notna(row.get(c)) for c in ['min_hours','max_hours','minutes']):raise ValueError(WORK_LABELS[group]+': mola tablosunda boş alan var. Başlangıç, bitiş ve süreyi doldurun.')
            if not 0<=float(row['min_hours'])<float(row['max_hours'])<=24 or float(row['minutes'])<0:raise ValueError('Mola saat sınırları 0–24 içinde ve başlangıç bitişten küçük olmalı.')
            if n and float(ranges[n-1]['max_hours'])>float(row['min_hours']):raise ValueError('Mola çalışma saati aralıkları çakışamaz.')
    return cfg


def render():
    s=st.session_state;cfg=deepcopy(s.get('status_rules_edit') or s.get('status_rules') or defaults());cfg.update(automatic=True,shrinkage_included=True);cfg['enabled']=st.toggle('Yemek, mola ve koçluğu otomatik planla',value=cfg.get('enabled',True),key='status_enabled')
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
                    rule['break_first_minutes']=number('Vardiya başlangıcından sonra mola yasak (dk)',0,180,int(rule.get('break_first_minutes',60)),15,key='break_first_'+group);rule['break_last_minutes']=number('Vardiya bitiminden önce mola yasak (dk)',0,180,int(rule.get('break_last_minutes',60)),15,key='break_last_'+group)
                    rule['break_minutes']=number('Tek mola en fazla (dk)',5,60,int(rule.get('break_minutes',15)),5,key='break_d_'+group);rule['break_per_hour_max']=number('Bir saat içinde en fazla mola (dk)',5,60,int(rule.get('break_per_hour_max',15)),5,key='break_hour_'+group)
                    rules=rule.get('break_rules',[{'min_hours':0,'max_hours':4,'minutes':15},{'min_hours':4,'max_hours':24,'minutes':30}]);df=pd.DataFrame(rules).rename(columns={'min_hours':'Çalışma alt sınırı','max_hours':'Çalışma üst sınırı','minutes':'Toplam mola (dk)'})
                    table=st.data_editor(df,num_rows='dynamic',hide_index=True,key='break_rules_'+group,column_config={c:st.column_config.NumberColumn(required=True,min_value=0,step=5 if c=='Toplam mola (dk)' else .5) for c in df})
                    rule['break_rules']=table.rename(columns={'Çalışma alt sınırı':'min_hours','Çalışma üst sınırı':'max_hours','Toplam mola (dk)':'minutes'}).to_dict('records')
                else:
                    rule['coaching_monthly_minutes']=number('Aylık kişi başı koçluk (dk)',0,480,int(rule.get('coaching_monthly_minutes',60)),15,key='coach_month_'+group);rule['coaching_chunk_minutes']=number('Her görüşme parçası (dk)',5,60,int(rule.get('coaching_chunk_minutes',15)),5,key='coach_chunk_'+group)
        if kind=='Mola':st.caption('Alt sınır dahil, üst sınır hariçtir. Sistem molaları grup hakkını ve bir saatlik sınırı aşmadan uygun kapasiteye dağıtır.')
        if kind=='Koçluk':cfg['coaching_by_leader']=st.toggle('Koçlukları takım lideri ajandasından atasın',value=cfg.get('coaching_by_leader',True),key='coaching_by_leader')
        if kind=='Koçluk':st.caption('Aylık hedef önceki yayınlardaki görüşmeler düşülerek tamamlanır. Kapasite yoksa ertelenir; ertelenen süre plan kontrolünde görünür.')
        if kind=='Yemek':st.caption('Yemek saatlerini sistem vardiya içinde hat durumuna göre seçer; yayınlandığında personelin takvimine düşer.')
    kind=st.segmented_control('Statü',['Yemek','Mola','Koçluk','Cuma'],default='Yemek',key='status_kind') or 'Yemek'
    if kind=='Cuma':
        with st.container(border=True):
            f=cfg['friday'];f['prefer_women_midday']=st.checkbox('12:00–14:00 aralığını kapsayan vardiyalarda kadınlara öncelik',f.get('prefer_women_midday',True));f['block_men_midday']=st.checkbox('Erkeklere bu aralığı kapsayan vardiya yazma (kesin kural)',f.get('block_men_midday',False));f['enabled']=st.checkbox('Cuma öğlen statüsü uygula',f.get('enabled',False));f['male_only']=st.checkbox('Yalnızca erkek personeller',f.get('male_only',False));f['minutes']=number('Cuma süresi (dk)',15,120,int(f.get('minutes',60)),15);st.caption('Cuma 12:00–14:00 aralığında, çalışma vardiyası içine yerleştirilir.')
    else:panel(kind)
    # Keep edits when switching between status windows; persist only on explicit save.
    s['status_rules_edit']=cfg
    if st.button('Statü Kurallarını Kaydet',key='status_save'):
        try:
            validate(cfg);s['status_rules']=cfg;s['shift_rules']['friday']={'prefer_women_midday':cfg['friday'].get('prefer_women_midday',True),'block_men_midday':cfg['friday'].get('block_men_midday',False)};save_keys(s);st.success('Statü hakları kaydedildi. Saatler yeni vardiya planıyla otomatik oluşur.')
        except (ValueError,TypeError,KeyError) as e:st.warning(str(e))

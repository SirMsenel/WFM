import pandas as pd
import streamlit as st
from ortak.calisma_alani_deposu import save_keys


def render():
    s=st.session_state;st.subheader('Yabancı Dil Vardiya Planlaması');lang=st.segmented_control('Planlanacak dil',['en','ar'],default='en',format_func=lambda x:'İngilizce' if x=='en' else 'Arapça',key='foreign_plan_language') or 'en'
    source=s.get('sp_staffing_result_df')
    if source is None:st.info('Önce Personel Hesap ekranında ihtiyaç hesaplayın.');return
    saved=s.setdefault('language_demands',{}).get(lang);base=source.copy() if saved is None else saved.copy()
    with st.expander('Bu dilin yarım saatlik personel ihtiyacını tanımla'):
        st.caption('İlk açılışta ortak ihtiyaç referans alınır. Bu dile ait ihtiyaçları girip kaydedin; diğer dilin yayını korunur.')
        table=base[['Tarih','Slot','Planlanan Agent']].copy();from ortak.saat_etiketleri import slot_label
        table['Saat']=table.Slot.map(slot_label);edited=st.data_editor(table,disabled=['Tarih','Slot','Saat'],hide_index=True,key='foreign_need_'+lang,column_config={'Planlanan Agent':st.column_config.NumberColumn(min_value=0,step=1,required=True)})
        if st.button('Dil İhtiyacını Kaydet',key='foreign_save_need'):
            values=pd.to_numeric(edited['Planlanan Agent'],errors='coerce')
            if values.isna().any() or (values<0).any():st.warning('İhtiyaç hücreleri boş veya negatif olamaz.')
            else:base['Planlanan Agent']=values;base['Net Agent']=values*(1-base['Shrinkage (%)']/100) if 'Shrinkage (%)' in base else values*.7;source_map=dict(s['language_demands']);source_map[lang]=base;s['language_demands']=source_map;save_keys(s);st.rerun()
    if saved is None:st.info('Bu dilin ihtiyaçlarını kaydettikten sonra otomatik planlama açılır.');return
    s['planning_languages']={x:x==lang for x in ['tr','en','ar']};s['planning_demand_language']=lang
    for x in ['tr','en','ar']:s['planning_include_'+x]=x==lang
    from modules.vardiya_plani.olustur_kontrol_yayinla import render as generate
    generate()

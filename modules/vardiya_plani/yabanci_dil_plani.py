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
        from ortak.cagri_tahmin_servisi import DAY_NAMES
        table['Tarih']=pd.to_datetime(table['Tarih']).dt.normalize();dates=sorted(table['Tarih'].unique());labels={pd.Timestamp(d).strftime('%d.%m')+' '+DAY_NAMES[pd.Timestamp(d).weekday()]:pd.Timestamp(d) for d in dates}
        wide=table.pivot(index='Slot',columns='Tarih',values='Planlanan Agent').reindex(range(1,49));wide.columns=[next(label for label,value in labels.items() if value==pd.Timestamp(d)) for d in wide.columns];wide.insert(0,'Yarım saat',[slot_label(slot) for slot in wide.index]);wide=wide.reset_index(drop=True)
        st.markdown('<div style="padding:12px 15px;border-radius:14px;background:#eef7f9;border:1px solid #d8e8ed"><b>30 Dakikalık Dil İhtiyacı</b><br><small>Satırlar saat aralığı, sütunlar tarih ve gün; hücreler planlanan agent sayısıdır.</small></div>',unsafe_allow_html=True)
        config={'Yarım saat':st.column_config.TextColumn('Yarım saat',width='small')}
        config.update({label:st.column_config.NumberColumn(label,min_value=0,step=1,required=True,width='small') for label in labels})
        edited=st.data_editor(wide,disabled=['Yarım saat'],hide_index=True,use_container_width=True,height=640,key='foreign_need_'+lang,column_config=config)
        if st.button('Dil İhtiyacını Kaydet',key='foreign_save_need'):
            values=edited.drop(columns=['Yarım saat']).apply(pd.to_numeric,errors='coerce')
            if values.isna().any().any() or (values<0).any().any():st.warning('İhtiyaç hücreleri boş veya negatif olamaz.')
            else:
                lookup={(str(day.date()),slot):float(values.iloc[slot-1][label]) for label,day in labels.items() for slot in range(1,49)}
                base['Planlanan Agent']=[lookup[(str(pd.Timestamp(day).date()),int(slot))] for day,slot in zip(base['Tarih'],base['Slot'])]
                base['Net Agent']=base['Planlanan Agent']*(1-base['Shrinkage (%)']/100) if 'Shrinkage (%)' in base else base['Planlanan Agent']*.7;source_map=dict(s['language_demands']);source_map[lang]=base;s['language_demands']=source_map;save_keys(s);st.rerun()
    if saved is None:st.info('Bu dilin ihtiyaçlarını kaydettikten sonra otomatik planlama açılır.');return
    s['planning_languages']={x:x==lang for x in ['tr','en','ar']};s['planning_demand_language']=lang
    for x in ['tr','en','ar']:s['planning_include_'+x]=x==lang
    from modules.vardiya_plani.olustur_kontrol_yayinla import render as generate
    generate()

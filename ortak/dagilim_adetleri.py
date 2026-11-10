"""Yüzde profilini, seçilen haftanın günlük toplamlarıyla 48 tam sayıya böler."""
import math
import pandas as pd
import streamlit as st
from ortak.cagri_tahmin_servisi import DAY_NAMES


def count_matrix(profile,totals):
    output={}
    for day in DAY_NAMES:
        part=profile[profile.Gün==day].sort_values('Slot').drop_duplicates('Slot',keep='last');weights=pd.to_numeric(part['Oran(%)'])
        if len(part)!=48 or abs(weights.sum()-100)>.01:raise ValueError('Her gün 48 dilim ve %100 gerekli.')
        total=int(totals.get(day,0));raw=weights.to_numpy()*total/100;values=[math.floor(v) for v in raw]
        for i in sorted(range(48),key=lambda i:raw[i]-values[i],reverse=True)[:total-sum(values)]:values[i]+=1
        output[day]=values
    from ortak.saat_etiketleri import slot_label
    return pd.DataFrame(output,index=[slot_label(i) for i in range(1,49)])


def render(profile,state,key,expanded=False):
    from contextlib import nullcontext
    with (nullcontext() if expanded else st.expander('Dağılımı çağrı adedi olarak göster')):
        from datetime import date
        fc=state.get('sp_forecast_df');start=pd.to_datetime(profile.Tarih).min().date() if 'Tarih' in profile else pd.to_datetime(fc.tarih).min().date() if fc is not None and not fc.empty else date(2026,11,10)
        totals={day:0 for day in DAY_NAMES}
        if fc is not None:
            for d in pd.date_range(start,periods=7):
                selected=fc[pd.to_datetime(fc.tarih).dt.normalize()==d]
                if not selected.empty:totals[DAY_NAMES[d.weekday()]]=round(float(selected.y_pred.iloc[0]))
        table=pd.DataFrame({'Gün':DAY_NAMES,'Çağrı adedi':[totals[d] for d in DAY_NAMES]});edited=st.data_editor(table,disabled=['Gün'],hide_index=True,use_container_width=True,key=key+'_totals',column_config={'Çağrı adedi':st.column_config.NumberColumn(min_value=0,step=1)})
        try:matrix=count_matrix(profile,dict(zip(edited['Gün'],edited['Çağrı adedi'])));st.dataframe(matrix.style.background_gradient(cmap='Blues').format('{:,.0f}'),use_container_width=True,height=480)
        except (ValueError,TypeError) as e:st.info(str(e))
        st.caption('Bu tablo gösterim içindir; günlük tahmin kaydını değiştirmez.')

"""Grafik İzleme — eğilim, aynı gün karşılaştırması ve yoğunluk."""
import pandas as pd
import streamlit as st
import plotly.express as px
from ortak.cagri_tahmin_servisi import date_column,DAY_NAMES
from ortak.izleme_analitigi import call_history,daily_insights
from ortak.modern_kartlar import metric_cards

def render():
    st.subheader('Grafik İzleme');frame=st.session_state.get('cf_full_df')
    if frame is None or frame.empty:st.info('Önce Veri Kaynağı ekranından veri seçin.');return
    try:date=date_column(frame)
    except ValueError as e:st.warning(str(e));return
    if date is None:st.warning('Tarih sütunu bulunamadı. Veri Kaynağı ekranından tarih sütununu seçin.');return
    numeric=[c for c in frame.select_dtypes(include='number') if c not in {date,'slot','answered','answered_target','staffed','sl_pct'}]
    if not numeric:st.info('Görüntülenecek sayısal çağrı sütunu yok.');return
    a,b,c=st.columns([2,2,1]);target=a.selectbox('Çağrı sütunu',numeric,index=numeric.index('cagri_sayisi') if 'cagri_sayisi' in numeric else 0,key='cf_chart_target');preset=b.selectbox('Dönem',['Son 30 gün','Son 7 gün','Son 90 gün','Tümü','Özel tarih'],key='cf_chart_preset');threshold=c.number_input('Dikkat eşiği (%)',0.,100.,20.,5.,key='cf_chart_threshold')
    data=call_history(frame,date,target)
    if data.empty:st.info('Geçerli tarih ve çağrı verisi yok.');return
    first,last=data.Zaman.min().date(),data.Zaman.max().date()
    if preset=='Özel tarih':
        selected=st.date_input('Grafik tarih aralığı',(first,last),min_value=first,max_value=last,key='cf_chart_range')
        if len(selected)!=2:return
        start,end=selected
    else:start,end=(max(first,last-pd.Timedelta(days={'Son 7 gün':6,'Son 30 gün':29,'Son 90 gün':89}.get(preset,100000))),last)
    full=daily_insights(data);daily=full[full.Tarih.between(pd.Timestamp(start),pd.Timestamp(end))].copy();selected=data[data.Zaman.between(pd.Timestamp(start),pd.Timestamp(end)+pd.Timedelta(days=1)-pd.Timedelta(microseconds=1))]
    if daily.empty:st.info('Seçilen dönemde veri yok.');return
    span=(pd.Timestamp(end)-pd.Timestamp(start)).days+1;prev=full[full.Tarih.between(pd.Timestamp(start)-pd.Timedelta(days=span),pd.Timestamp(start)-pd.Timedelta(days=1))]
    change=100*(daily['Çağrı'].mean()/prev['Çağrı'].mean()-1) if len(prev) and prev['Çağrı'].mean() else None
    metric_cards([('Toplam çağrı',f'{daily["Çağrı"].sum():,.0f}'),('Günlük ortalama',f'{daily["Çağrı"].mean():,.0f}'),('Önceki dönem / günlük ort.',f'{change:+.1f}%' if change is not None else 'Veri yok'),('Veri bulunan gün',f'{len(daily)} / {span}')])
    st.markdown('#### Çağrı eğilimi ve aynı hafta günü referansı')
    fig=px.line(daily,x='Tarih',y=['Çağrı','7 gün ort.','Aynı gün ort.'],color_discrete_sequence=['#178c9b','#b28b55','#8170ad']);fig.update_xaxes(tickformat='%d.%m.%Y');fig.update_layout(height=330,legend_title_text='',margin=dict(t=15,l=15,r=15,b=15));st.plotly_chart(fig,use_container_width=True)
    a,b=st.columns(2)
    with a:
        weekday=daily.groupby('Hafta günü',as_index=False)['Çağrı'].mean();weekday['Gün']=weekday['Hafta günü'].map(dict(enumerate(DAY_NAMES)));fig=px.bar(weekday,x='Gün',y='Çağrı',title='Haftanın gününe göre günlük ortalama',color='Çağrı',color_continuous_scale='Teal');fig.update_layout(height=310,coloraxis_showscale=False);st.plotly_chart(fig,use_container_width=True)
    with b:
        peaks=daily.nlargest(5,'Çağrı').copy();peaks['Gün']=peaks.Tarih.dt.strftime('%d.%m.%Y');fig=px.bar(peaks,x='Çağrı',y='Gün',orientation='h',title='En yoğun 5 gün',color_discrete_sequence=['#8873b5']);fig.update_layout(height=310,yaxis_autorange='reversed');st.plotly_chart(fig,use_container_width=True)
    intraday='slot' in frame or (selected.Zaman!=selected.Zaman.dt.normalize()).any()
    if intraday:
        heat=selected.assign(Gün=selected.Zaman.dt.weekday,Slot=selected.Zaman.dt.hour*2+selected.Zaman.dt.minute//30+1).pivot_table(index='Gün',columns='Slot',values='Çağrı',aggfunc='mean').reindex(range(7),columns=range(1,49))
        from ortak.saat_etiketleri import slot_label
        fig=px.imshow(heat.values,x=[slot_label(i) for i in range(1,49)],y=DAY_NAMES,aspect='auto',color_continuous_scale='Teal',labels={'color':'Ort. çağrı'},title='Gün × 30 dakika yoğunluğu');fig.update_layout(height=310);st.plotly_chart(fig,use_container_width=True)
    st.markdown('#### Referanstan sapmalar')
    anomalies=daily[daily['Sapma (%)'].abs()>threshold].copy();anomalies.Tarih=anomalies.Tarih.dt.strftime('%d.%m.%Y')
    if anomalies.empty:st.success('Seçilen eşik dışında sapma yok. Referansı olmayan günler başarı hesabına katılmaz.')
    else:st.dataframe(anomalies[['Tarih','Çağrı','Aynı gün ort.','Sapma (%)']].style.background_gradient(subset=['Sapma (%)'],cmap='RdYlGn_r').format({'Çağrı':'{:,.0f}','Aynı gün ort.':'{:,.0f}','Sapma (%)':'{:+.1f}'},na_rep='—'),hide_index=True,use_container_width=True)
    st.caption('Aynı gün referansı: o tarihten önceki son 4 aynı hafta günü. Gün toplamları üzerinden karşılaştırılır; eksik günler sıfır sayılmaz.')
    st.download_button('Analizi CSV İndir',daily.to_csv(index=False).encode('utf-8-sig'),'cagri_analizi.csv','text/csv')

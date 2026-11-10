# Mesai Plani / Gecmis Hafta Analizi — bu ekranın / servisin uygulama kodu.
from datetime import timedelta
import numpy as np
import pandas as pd
import streamlit as st

from ortak.cagri_tahmin_servisi import date_column,daily_history,weekday_comparison,DAY_NAMES
from ortak.grafikler import daily_chart,slot_heatmap
from ortak.gezinme import sections


def render_daily():
    raw=st.session_state.get('cf_all_df')
    if raw is None or raw.empty:
        st.info('Çağrı geçmişini yükleyin.')
        return
    date_col=date_column(raw);numeric=list(raw.select_dtypes(include='number').columns)
    preferred=st.session_state.get('cf_target_name','cagri_sayisi')
    target=preferred if preferred in numeric else ('cagri_sayisi' if 'cagri_sayisi' in numeric else numeric[0] if numeric else None)
    if target is None:st.info('Çağrı sayısı verisi yok.');return
    try:
        history=daily_history(raw,target,date_col)
        cutoff=st.date_input('Geçmiş veri kesimi',value=history.tarih.max().date(),min_value=history.tarih.min().date(),max_value=history.tarih.max().date(),key='history_cutoff')
        start=st.date_input('Karşılaştırılacak haftanın başlangıcı',value=cutoff+timedelta(days=7-cutoff.weekday()),min_value=cutoff+timedelta(days=1),key='history_week_start')
        table=weekday_comparison(history,start,7,cutoff)
    except ValueError as exc:
        st.error(str(exc));return
    columns=['Geçen hafta aynı gün','Son 2 hafta aynı gün ort.','Son 30 gün aynı gün ort.']
    st.caption('Eksik geçmiş sıfır sayılmaz. Yalnızca veri kesiminden önceki gerçekleşmeler kullanılır.')
    daily_chart(table,'Tarih',columns)
    a,b,c=st.columns(3)
    for metric,col in zip((a,b,c),columns):
        metric.metric(col,f'{table[col].sum(min_count=1):,.0f}' if table[col].notna().all() else 'Eksik gün var')
    with st.expander('Günlük karşılaştırma tablosu'):
        st.dataframe(table,hide_index=True,use_container_width=True)
    st.download_button('Günlük Analiz CSV İndir',table.to_csv(index=False).encode('utf-8-sig'),'gunluk_gecmis.csv','text/csv')
    options=st.session_state.get('cf_forecast_options',[])
    if options:
        joined=table[['Tarih','Gün']].copy()
        for option in options:
            joined=joined.merge(option['frame'][['tarih','y_pred']].rename(columns={'tarih':'Tarih','y_pred':option['name']}),how='left',on='Tarih')
        st.markdown('### Aynı Haftanın Model Tahminleri')
        daily_chart(joined,'Tarih',[o['name'] for o in options])
    tail=history[history.tarih<=pd.Timestamp(cutoff)].set_index('tarih').asfreq('D').reset_index()
    st.markdown('### Hafta İçi ve Hafta Sonu Hareketli Ortalamaları')
    tail=grouped_rolling(tail)
    st.caption('Her gün kendi içinde hesaplanır: Pazartesi için son 7/30 Pazartesi, Salı için son 7/30 Salı gibi. Eksik günler sıfır sayılmaz; iki grafik yalnızca hafta içi/hafta sonu görünümüdür.')
    columns=st.columns(2)
    for col,kind in zip(columns,['Hafta içi','Hafta sonu']):
        with col:
            st.markdown('**'+kind+'**')
            selected=tail[(tail['Gün türü']==kind)&(tail.tarih>tail.tarih.max()-pd.Timedelta(days=60))]
            selected=selected.rename(columns={'7 günlük hareketli ortalama':'Son 7 aynı hafta günü ort.','30 günlük hareketli ortalama':'Son 30 aynı hafta günü ort.'})
            daily_chart(selected,'tarih',['cagri_sayisi','Son 7 aynı hafta günü ort.','Son 30 aynı hafta günü ort.'],height=260)


def grouped_rolling(history):
    out=history.copy().sort_values('tarih');out['tarih']=pd.to_datetime(out.tarih)
    out['Gün türü']=np.where(out.tarih.dt.weekday<5,'Hafta içi','Hafta sonu')
    for days in (7,30):
        out[f'{days} günlük hareketli ortalama']=np.nan
        for _,part in out.groupby(out.tarih.dt.weekday):
            values=part.cagri_sayisi.rolling(days,min_periods=1).mean()
            out.loc[part.index,f'{days} günlük hareketli ortalama']=values.to_numpy()
    return out


def interval_references(raw,start,cutoff):
    from ortak.interval_servisi import prepare_intervals
    dates,_,counts,_=prepare_intervals(raw)
    counts=counts[counts.index<=pd.Timestamp(cutoff)]
    rows=[]
    for day in pd.date_range(start,periods=7):
        last=counts.reindex([day-pd.Timedelta(days=7)]).iloc[0]
        same=counts[(counts.index.weekday==day.weekday())&(counts.index<day)]
        two=same.tail(2).mean()
        month=counts[(counts.index>pd.Timestamp(cutoff)-pd.Timedelta(days=30))&(counts.index.weekday==day.weekday())].mean()
        for slot in range(1,49):
            rows.append({'Tarih':day,'Gün':DAY_NAMES[day.weekday()],'Slot':slot,'Geçen hafta aynı gün':last[slot],
                         'Son 2 hafta aynı gün ort.':two[slot],'Son 30 gün aynı gün ort.':month.get(slot,np.nan)})
    return pd.DataFrame(rows)


def render_interval_references():
    from ortak.veri_onbellegi import cached_calls
    from ortak.calisma_alani_deposu import DEFAULT_DB
    from ortak.interval_servisi import prepare_intervals
    source=st.radio('30 dk geçmiş kaynağı',['Hazır Veritabanı','Yüklenmiş Çağrı Verisi'],horizontal=True,key='history_interval_source')
    raw=cached_calls(str(st.session_state.get('workspace_db_path',DEFAULT_DB)),True) if source=='Hazır Veritabanı' else st.session_state.get('cf_all_df')
    if raw is None:
        st.info('30 dakikalık çağrı verisi yükleyin.');return
    try:
        dates,_,counts,_=prepare_intervals(raw)
        cutoff=st.date_input('30 dk veri kesimi',value=dates.max().date(),min_value=dates.min().date(),max_value=dates.max().date(),key='history_interval_cutoff')
        start=st.date_input('30 dk karşılaştırma haftası',value=cutoff+timedelta(days=7-cutoff.weekday()),min_value=cutoff+timedelta(days=1),key='history_interval_start')
        table=interval_references(raw,start,cutoff)
    except (ValueError,KeyError) as exc:
        st.error(str(exc));return
    method=st.radio('Karşılaştırma referansı',['Geçen hafta aynı gün','Son 2 hafta aynı gün ort.','Son 30 gün aynı gün ort.'],horizontal=True,key='history_interval_reference')
    st.markdown('### Haftanın Çağrı Yoğunluğu · 7 × 48')
    slot_heatmap(table,value=method)
    day=st.selectbox('Gün eğrisi',DAY_NAMES,key='history_interval_day')
    selected=table[table.Gün==day].copy()
    selected['Saat']=selected.Slot.map(lambda s:f'{(s-1)//2:02d}:{((s-1)%2)*30:02d}')
    st.line_chart(selected.set_index('Saat')[['Geçen hafta aynı gün','Son 2 hafta aynı gün ort.','Son 30 gün aynı gün ort.']])
    st.caption('Bu görünüm çağrı adedidir; interval planlama ekranındaki dağılım yüzdesinden farklıdır. Eksik dilim boş gösterilir.')
    from ortak.saat_etiketleri import slot_label
    view=table.copy();view.insert(2,'Saat aralığı',view.Slot.map(slot_label));view=view.drop(columns='Slot')
    with st.expander('30 dakikalık karşılaştırma tablosu'):
        st.dataframe(view,hide_index=True,use_container_width=True)
    st.download_button('30 dk Analiz CSV İndir',view.to_csv(index=False).encode('utf-8-sig'),'30dk_gecmis.csv','text/csv')


def render():
    st.title('📈 GÜNCEL TAKİP ANALİZİ')
    from modules.mesai_plani.guncel_takip import render_current,render_accuracy
    def interval():
        sections('nav_interval_history',{'Dağılım Başarısı':render_accuracy,'Geçmiş Referanslar':render_interval_references})
    sections('nav_history',{'Canlı İzleme':render_current,'Günlük':render_daily,'30 Dakikalık':interval})

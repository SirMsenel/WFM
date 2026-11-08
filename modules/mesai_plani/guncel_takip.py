# Mesai Plani / Guncel Takip — bu ekranın / servisin uygulama kodu.
import json
import numpy as np
import pandas as pd
import streamlit as st
from ortak.tahmin_kayit_servisi import runs,compare,performance,ingest_actuals,profile_versions,profile_accuracy
from ortak.calisma_alani_deposu import DEFAULT_DB
from ortak.saat_etiketleri import slot_label
from ortak.grafikler import slot_heatmap
from ortak.cagri_tahmin_servisi import DAY_NAMES


def path():return st.session_state.get('workspace_db_path') or DEFAULT_DB


def run_label(record):
    metadata=json.loads(record['metadata']);forecast=metadata.get('forecast') or {}
    return f"{record['start']} – {record['end']} · {forecast.get('model_name') or 'Tahmin'} · {metadata.get('profile') or 'Profil'} · {record['created_at'][:16]} · {record['id'][-5:]}"


def profile_label(version):
    meta=version['meta'];phase='Kullanıldı' if meta.get('usage')=='staffing' else 'Seçildi'
    if meta.get('legacy_timestamp_unknown'):phase='Eski kayıt'
    return f"{pd.to_datetime(version['frame'].Tarih).min():%d.%m.%Y} – {pd.to_datetime(version['frame'].Tarih).max():%d.%m.%Y} · {meta.get('name') or 'Dağılım'} · {phase} · {version['created_at'][:16]} · {version['id'][-5:]}"


@st.fragment(run_every=30)
def render_current():
    st.subheader('Güncel Takip · Tahmin ve Gerçekleşen Çağrı')
    versions=runs(path())
    if not versions:st.info('Henüz kullanılan bir tahmin kaydı yok. Mesai Planı → Personel Hesap ile hesapladığın 48 dilim burada sürümlü saklanır. Eski gerçekleşmelerden geriye dönük tahmin üretilmez.');return
    ident=st.selectbox('Kullanılan tahmin kaydı',[r['id'] for r in versions],format_func=lambda i:next(run_label(r) for r in versions if r['id']==i),key='tracking_forecast_run')
    exclude=st.toggle('03:00–08:00 ölçüme katılmasın',value=True,key='tracking_exclude_early')
    frame=compare(ident,path(),exclude)
    days=sorted(frame.tarih.unique());day=st.selectbox('İzlenecek gün',days,key='tracking_day')
    selected=frame[frame.tarih==day].copy();metrics=performance(selected)
    record=next(r for r in versions if r['id']==ident)
    if pd.Timestamp(record['created_at']).date()>=pd.Timestamp(day).date():st.caption('Bu sürüm seçilen gün başladıktan sonra kaydedilmiş. Sonuç, önceden yapılmış tahmin başarısı olarak yorumlanmamalı; kayıt zamanı korunur.')
    columns=st.columns(4)
    for col,label,value in zip(columns,['Tahmin (verisi gelen dilimler)','Gerçekleşen çağrı','Eksik/fazla (%)','Mutlak hata / WAPE (%)'],[f"{metrics['predicted']:,.0f}",f"{metrics['actual']:,.0f}",'—' if metrics['bias_pct'] is None else f"{metrics['bias_pct']:+.1f}",'—' if metrics['wape_pct'] is None else f"{metrics['wape_pct']:.1f}"]):
        with col.container(border=True):st.metric(label,value)
    st.caption(f"{metrics['observed_slots']} ölçülen dilim · +: tahminden fazla çağrı · −: tahminden az çağrı. Gelmeyen veri 0 sayılmaz; tahmin 0 ise yüzde hesaplanmaz. WAPE toplam mutlak hatanın gerçekleşen çağrıya oranıdır.")
    selected['Saat aralığı']=selected.slot.map(slot_label)
    chart=selected.set_index('Saat aralığı')[['predicted','actual']].rename(columns={'predicted':'Tahmin','actual':'Gerçekleşen'})
    st.line_chart(chart)
    view=selected[['Saat aralığı','predicted','actual','difference','difference_pct','counted']].rename(columns={'predicted':'Tahmin','actual':'Gerçekleşen','difference':'Fark (çağrı)','difference_pct':'Fark (%)','counted':'Ölçüme dahil'})
    st.dataframe(view,hide_index=True,use_container_width=True,height=560,column_config={'Fark (%)':st.column_config.NumberColumn(format='%+.2f')})
    st.download_button('48 Dilim Takip CSV İndir',view.to_csv(index=False).encode('utf-8-sig'),'guncel_takip.csv','text/csv')


def render_accuracy():
    st.subheader('Kullanılan Interval Dağılımının Başarısı')
    versions=profile_versions(path())
    versions=[v for v in versions if 'Tarih' in v['frame']]
    if not versions:st.info('Henüz tarihli dağılım kaydı yok. İnterval ekranında kaydettiğin veya Personel Hesap’ta kullandığın dağılımlar burada geçmişi silinmeden saklanır.');return
    ident=st.selectbox('Ölçülecek dağılım sürümü',[v['id'] for v in versions],format_func=lambda i:next(profile_label(v) for v in versions if v['id']==i),key='interval_accuracy_version')
    version=next(v for v in versions if v['id']==ident)
    exclude=st.toggle('03:00–08:00 dağılım başarısına katılmasın',value=True,key='interval_accuracy_exclude')
    table=profile_accuracy(version,path(),exclude)
    valid=table[table.error_points.notna()]
    if valid.empty:st.info('Bu sürümün tarihlerinde ölçüme dahil bütün dilimleri tamamlanmış bir gün henüz yok. Kısmi günü Güncel Takip ekranından izleyebilirsin.');return
    cols=st.columns(3)
    for col,label,val in zip(cols,['Tamamlanan gün','Ortalama sapma (yüzde puan)','En yüksek sapma (yüzde puan)'],[valid.tarih.nunique(),f'{valid.error_points.abs().mean():.3f}',f'{valid.error_points.abs().max():.3f}']):
        with col.container(border=True):st.metric(label,val)
    if pd.Timestamp(version['created_at']).date()>=pd.to_datetime(version['frame'].Tarih).min().date():st.caption('Bu sürüm ilgili tarihler başladıktan sonra kaydedilmiş; önceden seçilmiş dağılım başarısı yerine geriye dönük karşılaştırma olarak değerlendirilir.')
    if version['meta'].get('legacy_timestamp_unknown'):st.caption('Eski kayıttan taşındı; ilk seçim zamanı bilinmiyor. Ölçüm sürümün ilk oluşturulduğunu kanıtlamaz.')
    st.caption('Kaydedilmiş dağılım, aynı tarihin gerçekleşen paylarıyla karşılaştırılır. Hariç tutulan saatler varsa iki dağılım da kalan saatlerde %100’e normalize edilir. Tamamlanmamış günler ortalamaya katılmaz.')
    heat=valid.copy();heat['Gün']=pd.to_datetime(heat.tarih).dt.weekday.map(dict(enumerate(DAY_NAMES)));heat['Slot']=heat.slot;heat['Mutlak sapma (puan)']=heat.error_points.abs()
    heat=heat.groupby(['Gün','Slot'],as_index=False)['Mutlak sapma (puan)'].mean()
    slot_heatmap(heat,'Mutlak sapma (puan)')
    day=st.selectbox('Başarısı gösterilecek gün',sorted(valid.tarih.unique()),key='interval_accuracy_day')
    chosen=table[table.tarih==day].copy();chosen['Saat aralığı']=chosen.slot.map(slot_label)
    st.line_chart(chosen.set_index('Saat aralığı')[['planned_share','actual_share']].rename(columns={'planned_share':'Kaydedilmiş pay (%)','actual_share':'Gerçekleşen pay (%)'}))
    st.dataframe(chosen[['Saat aralığı','planned_share','actual_share','error_points','counted']].rename(columns={'planned_share':'Kaydedilmiş pay (%)','actual_share':'Gerçekleşen pay (%)','error_points':'Sapma (yüzde puan)','counted':'Ölçüme dahil'}),hide_index=True,use_container_width=True,height=520)

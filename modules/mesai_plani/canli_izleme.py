"""Ortak görünümlü servis seviyesi ve çağrı tahmin izleme."""
import pandas as pd
import streamlit as st
from ortak.tahmin_kayit_servisi import runs,compare,performance
from ortak.canli_metrikler import actual_metrics
from ortak.izleme_analitigi import assess,difference_color
from ortak.saat_etiketleri import slot_label
from ortak.modern_kartlar import metric_cards

@st.fragment(run_every=30)
def render(kind='forecast'):
    s=st.session_state;path=s['workspace_db_path'];service=kind=='sl';prefix='live_'+kind
    st.subheader('Servis Seviyesi İzleme' if service else 'Tahmin İzleme')
    a,b=st.columns([2,1]);tolerance=a.number_input('Kabul edilen fark (yüzde puan)' if service else 'Kabul edilen fark (%)',0.,100.,5. if service else 10.,1.,key=prefix+'_threshold');exclude=b.toggle('03:00–08:00 hariç',True,key=prefix+'_exclude')
    versions=runs(path)
    if not versions:st.info('İzlenecek kayıt yok. Mesai Planı → Personel Hesap ile kullanılan tahmini kaydedin.');return
    from modules.mesai_plani.guncel_takip import run_label
    byid={r['id']:r for r in versions};ident=st.selectbox('Kullanılan tahmin kaydı',list(byid),format_func=lambda i:run_label(byid[i]),key=prefix+'_run')
    frame=compare(ident,path,exclude);day=st.selectbox('İzlenecek gün',sorted(frame.tarih.unique()),key=prefix+'_day');selected=frame[frame.tarih==day].copy();selected['Saat aralığı']=selected.slot.map(slot_label)
    if pd.Timestamp(byid[ident]['created_at']).date()>=pd.Timestamp(day).date():st.caption('Bu kayıt ilgili gün başladıktan sonra oluşturulmuş; sonuç geriye dönük karşılaştırmadır.')
    if service:
        live=actual_metrics(s,selected);target=100*float(s.get('staffing_parameters',{}).get('target_sl',.8));live['Hedef SL (%)']=target;live['Fark (puan)']=live['Gerçek SL (%)']-target;diff='Fark (puan)'
        live['Sonuç']=assess(live[diff],tolerance,live.counted)
        valid=live[live.counted & live['Gerçek SL (%)'].notna()];den=valid.actual.sum();overall=100*valid.answered_target.sum()/den if den else None
        cards=[('Gerçek servis seviyesi',f'%{overall:.1f}' if overall is not None else 'Veri yok'),('Hedef SL',f'%{target:.1f}'),('Genel fark',f'{overall-target:+.1f} puan' if overall is not None else '—')]
        columns=['Saat aralığı','Hedef SL (%)','Gerçek SL (%)',diff,'Gerçekleşene göre net ihtiyaç','Sonuç'];view=live[columns];chart=live.set_index('Saat aralığı')[['Hedef SL (%)','Gerçek SL (%)']]
    else:
        selected['Sonuç']=assess(selected.difference_pct,tolerance,selected.counted);metrics=performance(selected);live=selected;diff='Fark (%)';view=selected[['Saat aralığı','predicted','actual','difference','difference_pct','Sonuç']].rename(columns={'predicted':'Tahmin','actual':'Gerçekleşen','difference':'Fark (çağrı)','difference_pct':diff});chart=view.set_index('Saat aralığı')[['Tahmin','Gerçekleşen']]
        cards=[('Tahmin · ölçülen dilimler',f'{metrics["predicted"]:,.0f}'),('Gerçekleşen çağrı',f'{metrics["actual"]:,.0f}'),('Genel fark',f'{metrics["bias_pct"]:+.1f}%' if metrics['bias_pct'] is not None else '—')]
    evaluated=live[live['Sonuç'].isin(['Uygun','Sınır dışında'])];success=100*(evaluated['Sonuç']=='Uygun').mean() if len(evaluated) else None
    metric_cards(cards+[('Eşik içindeki dilimler',f'%{success:.1f}' if success is not None else 'Veri yok')]);st.line_chart(chart,color=['#8c77b3','#1c98a4'])
    styles=pd.DataFrame('',index=view.index,columns=view.columns)
    for i,row in view.iterrows():
        style='background-color:#edf1f5;color:#7a8699' if row['Sonuç'] in {'Ölçüm dışı','Veri yok'} else difference_color(row[diff],tolerance)
        styles.loc[i,:]=style
    st.dataframe(view.style.apply(lambda _:styles,axis=None).format({diff:'{:+.2f}'},na_rep='—'),hide_index=True,use_container_width=True,height=540)
    st.caption('Yeşil: seçtiğin fark sınırında. Kırmızı: sınır dışında; fark arttıkça koyulaşır. Veri olmayan ve ölçüm dışındaki dilimler gri, başarı hesabı dışındadır.')
    st.download_button('Takip CSV İndir',view.to_csv(index=False).encode('utf-8-sig'),kind+'_izleme.csv','text/csv',key=prefix+'_csv')

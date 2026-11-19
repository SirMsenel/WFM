"""Yönetim raporlarının güvenli başlangıç ekranı.

Skor/performans ölçütleri kurum verisiyle kesinleştirilmeden puan üretmez.
Bu ekran, ilerideki karnelerin tek ve yetkili başlangıç noktasıdır.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st


REPORT_ROLES={'wfm','planning_manager','manager','assistant_manager','moderator'}


def render():
    state=st.session_state; profile=state.get('profile') or {}
    st.title('📑 Raporlar')
    if profile.get('position') not in REPORT_ROLES:
        st.info('Raporlar yönetim ve planlama rolleri içindir.')
        return
    from ortak.demo_zamani import today as active_today
    today=active_today(state)
    a,b,c=st.columns([1,1,1.4])
    start=a.date_input('Rapor başlangıcı',value=today.replace(day=1),key='report_start')
    end=b.date_input('Rapor bitişi',value=today,key='report_end')
    category=c.selectbox('Rapor alanı',['Yönetim özeti','Planlama ve kapasite','Personel karnesi (hazırlık)'],key='report_category')
    if end<start:
        st.warning('Bitiş tarihi başlangıçtan önce olamaz.');return
    st.markdown('### Rapor Merkezi')
    st.caption('Bu alan; planlama, kalite ve personel karnesi raporlarını aynı tarih ve yetki filtresiyle üretmek için hazırlandı.')
    if category=='Yönetim özeti':
        from ortak.personel import get_people
        people=[p for p in get_people(state) if p.get('position')=='agent' and not p.get('employment_end')]
        published=[r for r in state.get('published_shift_plan',[]) if str(start)<=str(r.get('date'))<=str(end)]
        from ortak.modern_kartlar import metric_cards
        metric_cards([('Aktif çağrı personeli',len(people)),('Yayınlanmış vardiya kaydı',len(published)),('Rapor dönemi',f'{(end-start).days+1} gün')])
        st.info('Yönetim özeti şu an doğrulanmış plan ve personel verisini gösterir. Çağrı, kalite ve anket kaynakları bağlandığında bu karta gerçek operasyon metrikleri eklenir.')
    elif category=='Planlama ve kapasite':
        frame=state.get('sp_staffing_result_df')
        if isinstance(frame,pd.DataFrame) and not frame.empty:
            view=frame.copy();view['Tarih']=pd.to_datetime(view['Tarih']).dt.date
            view=view[view.Tarih.between(start,end)]
            if view.empty:st.info('Seçilen dönemde hesaplanmış personel ihtiyacı yok.')
            else:
                from ortak.modern_kartlar import metric_cards
                metric_cards([('Tahmin çağrı',f"{view['Tahmin Çağrı'].sum():,.0f}"),('Ortalama net agent',f"{view['Net Agent'].mean():.1f}"),('Ortalama planlanan agent',f"{view['Planlanan Agent'].mean():.1f}")])
                chart=view.groupby('Tarih')[['Net Agent','Planlanan Agent']].mean();st.line_chart(chart,color=['#287ca6','#3c9b6e'])
        else:st.info('Önce Mesai Planı → Personel Hesap ekranında ihtiyaç hesabı oluşturun.')
    else:
        st.markdown('#### Personel Karnesi · Veri Kaynağı Hazırlığı')
        st.warning('Şikayet, NPS, destek puanı ve kalite puanı için kurumdan doğrulanmış kaynak henüz bağlı değil. Bu nedenle uygulama sentetik “performans puanı” üretmez.')
        st.dataframe(pd.DataFrame([
            {'Gösterge':'Şikayet sayısı','Kaynak':'CRM / şikayet kaydı','Durum':'Bağlantı bekliyor'},
            {'Gösterge':'NPS / anket puanı','Kaynak':'Anket platformu','Durum':'Bağlantı bekliyor'},
            {'Gösterge':'Destek / kalite puanı','Kaynak':'Kalite değerlendirme sistemi','Durum':'Bağlantı bekliyor'},
            {'Gösterge':'Plan uyumu','Kaynak':'WFM yayın/gerçekleşen vardiya','Durum':'WFM içinde hesaplanabilir'},
        ]),hide_index=True,use_container_width=True)

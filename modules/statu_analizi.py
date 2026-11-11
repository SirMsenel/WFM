"""Statü dağılımı: plan ve gerçekleşme birbirine karıştırılmaz."""
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from ortak.mola_servisi import records
from ortak.statu_gecmisi import actuals
from ortak.personel import get_people,visible_people
from ortak.modern_kartlar import metric_cards


def distribution(items,start,end):
    index=pd.date_range(start,pd.Timestamp(end)+pd.Timedelta(days=1)-pd.Timedelta(minutes=30),freq='30min');data=pd.DataFrame(0.,index=index,columns=['Yemek','Mola','Koçluk','Cuma'])
    for r in items:
        if r.get('kind') not in data or r.get('status')=='İptal':continue
        a,b=pd.Timestamp(r['start']),pd.Timestamp(r['end'])
        for t in pd.date_range(max(a.floor('30min'),index.min()),min(b-pd.Timedelta(seconds=1),index.max()),freq='30min'):
            data.at[t,r['kind']]+=max(0,(min(b,t+pd.Timedelta(minutes=30))-max(a,t)).total_seconds()/1800)
    return data


def render_data(items,start,end,key):
    data=distribution(items,start,end);totals=[]
    for kind in ['Yemek','Mola','Koçluk']:
        selected=[r for r in items if r['kind']==kind and r.get('status')!='İptal'];duration=sum(max(0,(min(pd.Timestamp(r['end']),pd.Timestamp(end)+pd.Timedelta(days=1))-max(pd.Timestamp(r['start']),pd.Timestamp(start))).total_seconds()/60) for r in selected);count=len(selected);totals.append((f'{kind} · {count} × {duration/count:.0f} dk' if count else kind+' · 0 kullanım',f'{data[kind].sum()*.5:.1f} kişi-saat'))
    metric_cards(totals)
    st.caption('Grafik, her yarım saatin ne kadarının statülere ayrıldığını gösterir. Örneğin 1 kişi 15 dakika mola kullanırsa o yarım saatte 0,50 kişi görünür. Toplam süreler kartlarda saat olarak gösterilir.')
    st.area_chart(data,stack=True,color=['#49a8a4','#8c7ac1','#dca760','#c17893'])
    with st.expander('Yarım saatlik dağılım'):
        table=data.copy();table.index=table.index.strftime('%d.%m.%Y %H:%M');st.dataframe(table.style.format('{:.2f}').background_gradient(cmap='Blues'),use_container_width=True)
    return data


@st.fragment(run_every=30)
def render():
    s=st.session_state;today=datetime.now(ZoneInfo('Europe/Istanbul')).date();st.subheader('Statü Kullanım Dağılımları');mode=st.segmented_control('İzleme',['Canlı','Geçmiş'],default='Canlı',key='status_analysis_mode') or 'Canlı'
    dates=(today,today) if mode=='Canlı' else st.date_input('Statü dönemi',(today.replace(day=1),today),key='status_analysis_range')
    if len(dates)!=2:return
    from ortak.personel_deposu import list_people
    source_people=list_people(s,True) if mode=='Geçmiş' else get_people(s)
    people=visible_people(s['profile'],source_people);ids={str(p['employee_id']) for p in people};source=st.segmented_control('Kaynak',['Planlanan','Gerçekleşen'],default='Planlanan',key='status_analysis_source') or 'Planlanan'
    if source=='Planlanan':items=[r for r in records(s) if str(r['employee_id']) in ids and r['start'][:10]<=str(dates[1]) and r['end'][:10]>=str(dates[0])]
    else:
        frame=actuals(s,*dates,ids);items=frame.to_dict('records')
        if not frame.empty and (frame.source=='synthetic').any():st.info('Bu gerçekleşme verileri sentetik örnektir; kurum statü servisi henüz bağlı değildir.')
    if not items:st.info('Seçilen kapsamda statü kaydı yok.');return
    render_data(items,*dates,'status_analysis');summary=[]
    for kind in ['Yemek','Mola','Koçluk']:
        selected=[x for x in items if x['kind']==kind];minutes=sum(max(0,(min(pd.Timestamp(x['end']),pd.Timestamp(dates[1])+pd.Timedelta(days=1))-max(pd.Timestamp(x['start']),pd.Timestamp(dates[0]))).total_seconds()/60) for x in selected);summary.append({'Statü':kind,'Kullanım adedi':len(selected),'Ort. süre (dk)':minutes/len(selected) if selected else 0,'Toplam dakika':minutes})
    st.divider();st.markdown('### Kullanım Özeti')
    for col,row,color in zip(st.columns(3),summary,['#258f94','#7c69b0','#c18e44']):
        col.markdown(f'<div style="padding:20px;border-radius:18px;border-top:5px solid {color};background:{color}12;color:{color}"><b>{row["Statü"]}</b><h2 style="color:{color}">{row["Toplam dakika"]/60:.2f} saat</h2><div>{row["Kullanım adedi"]} kullanım</div><small>Ortalama kullanım: {row["Ort. süre (dk)"]:.2f} dakika</small></div>',unsafe_allow_html=True)
    daily=distribution(items,*dates).resample('D').sum()*.5
    st.markdown('#### Günlere Göre Statülere Ayrılan Toplam Süre (saat)')
    st.bar_chart(daily,stack=True,color=['#49a8a4','#8c7ac1','#dca760','#c17893'])


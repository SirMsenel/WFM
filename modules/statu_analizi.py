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
    from ortak.statu_kapasite_raporu import person_headcounts
    heads=person_headcounts(items,start,end)
    st.caption('Grafik ve tablo yarım saatte statü kullanan tekil kişi adedidir. Bir kişi 10 dakika mola kullansa da 1 sayılır; toplam süreler üst kartlarda ayrıca gösterilir.')
    st.area_chart(heads,stack=True,color=['#49a8a4','#8c7ac1','#dca760','#c17893'])
    with st.expander('Yarım saatlik dağılım'):
        table=heads.copy();table.index=table.index.strftime('%d.%m.%Y %H:%M');st.dataframe(table.style.format('{:.0f}').background_gradient(cmap='Blues'),use_container_width=True)
    return data


@st.fragment(run_every=30)
def render():
    s=st.session_state
    from ortak.statu_kapasite_raporu import capacity_visible
    if not capacity_visible(s['profile']):st.info('Statü ve kapasite analizi Planlama ve yönetim içindir.');return
    today=datetime.now(ZoneInfo('Europe/Istanbul')).date();st.subheader('Statü Kullanım Dağılımları');mode=st.segmented_control('İzleme',['Canlı','Geçmiş'],default='Canlı',key='status_analysis_mode') or 'Canlı'
    dates=(today,today) if mode=='Canlı' else st.date_input('Statü dönemi',(today.replace(day=1),today),key='status_analysis_range')
    if len(dates)!=2:return
    from ortak.personel_deposu import list_people
    source_people=list_people(s,True) if mode=='Geçmiş' else get_people(s)
    people=visible_people(s['profile'],source_people);ids={str(p['employee_id']) for p in people};source=st.segmented_control('Kaynak',['Planlanan','Gerçekleşen'],default='Planlanan',key='status_analysis_source') or 'Planlanan'
    if source=='Planlanan':items=[r for r in records(s) if str(r['employee_id']) in ids and r['start'][:10]<=str(dates[1]) and r['end'][:10]>=str(dates[0])]
    else:
        frame=actuals(s,*dates,ids);items=frame.to_dict('records')
        if not frame.empty and (frame.source=='synthetic').any():st.info('Bu gerçekleşme verileri sentetik örnektir; kurum statü servisi henüz bağlı değildir.')
    from ortak.statu_kapasite_raporu import capacity_visible,published_entitlements,capacity_openings,render_capacity_report
    if capacity_visible(s['profile']):
        from ortak.sabit_demo import history_rows
        roster=[r for r in history_rows(s,pd.Timestamp(dates[0])-pd.Timedelta(days=1),dates[1]) if str(r['employee_id']) in ids]
        from ortak.statu_kapasite_raporu import associate_items
        items=associate_items(items,roster)
        rights,approximate=published_entitlements(s,roster,people);openings=capacity_openings(s,*dates,ids)
        if approximate:st.caption('Bazı eski/örnek yayınlarda tarihsel hak sürümü yok; bu kayıtların hakları mevcut kurallarla yaklaşık hesaplanır.')
        reference=[r for r in records(s) if str(r['employee_id']) in ids] if source=='Gerçekleşen' else None
        render_capacity_report(s,rights,items,openings,*dates,'status_capacity',actual=source=='Gerçekleşen',reference_items=reference)
    if not items:st.info('Seçilen kapsamda statü kaydı yok.');return
    with st.expander('Süre ve günlük eğilim detayları'):
        render_data(items,*dates,'status_analysis');summary=[]
        for kind in ['Yemek','Mola','Koçluk']:
            selected=[x for x in items if x['kind']==kind];minutes=sum(max(0,(min(pd.Timestamp(x['end']),pd.Timestamp(dates[1])+pd.Timedelta(days=1))-max(pd.Timestamp(x['start']),pd.Timestamp(dates[0]))).total_seconds()/60) for x in selected);summary.append({'Statü':kind,'Kullanım adedi':len(selected),'Ort. süre (dk)':minutes/len(selected) if selected else 0,'Toplam dakika':minutes})
        st.divider();st.markdown('### Kullanım Özeti')
        for col,row,color in zip(st.columns(3),summary,['#258f94','#7c69b0','#c18e44']):
            col.markdown(f'<div style="padding:20px;border-radius:18px;border-top:5px solid {color};background:{color}12;color:{color}"><b>{row["Statü"]}</b><h2 style="color:{color}">{row["Toplam dakika"]/60:.2f} saat</h2><div>{row["Kullanım adedi"]} kullanım</div><small>Ortalama kullanım: {row["Ort. süre (dk)"]:.2f} dakika</small></div>',unsafe_allow_html=True)
        daily=distribution(items,*dates).resample('D').sum()*.5
        st.markdown('#### Günlere Göre Statülere Ayrılan Toplam Süre (saat)')
        st.bar_chart(daily,stack=True,color=['#49a8a4','#8c7ac1','#dca760','#c17893'])
    

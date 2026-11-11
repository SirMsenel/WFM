"""Geçmiş 12 ayın gün/mevsim örüntüsüyle iyi-normal-kötü kapasite senaryosu."""
import math
import numpy as np
import pandas as pd
from modules.mesai_plani.personel_ihtiyaci import erlang_c_required_agents,erlang_c_metrics_for_m


def simulate(history,start,months,headcount,aht=300,shrinkage=.3,target_sl=.8,seconds=20,occupancy=.85,growth=.02,attrition=.02,days=5,hours=8,peak_share=1/32,forecast=None):
    if not 1<=months<=24 or headcount<0 or not 0<=shrinkage<1 or not 0<target_sl<1:raise ValueError('Senaryo parametreleri geçerli aralıkta olmalı.')
    h=history[['tarih','cagri_sayisi']].copy();h['tarih']=pd.to_datetime(h.tarih).dt.normalize();h=h[h.tarih<pd.Timestamp(start)];h=h[h.tarih>=h.tarih.max()-pd.DateOffset(years=1)].sort_values('tarih')
    if h.empty:raise ValueError('Senaryo tarihinden önce çağrı geçmişi gerekli.')
    h['weekday']=h.tarih.dt.weekday;h['month']=h.tarih.dt.month;base=h.tail(90).groupby('weekday').cagri_sayisi.mean();season=h.groupby('month').cagri_sayisi.mean()/h.cagri_sayisi.mean()
    # Walk-forward reference: each day's previous four same weekdays only.
    reference=h.groupby('weekday').cagri_sayisi.transform(lambda x:x.shift().rolling(4,min_periods=2).mean());mask=reference.notna()&(h.cagri_sayisi>0);wape=float((h.loc[mask,'cagri_sayisi']-reference[mask]).abs().sum()/h.loc[mask,'cagri_sayisi'].sum()) if mask.any() else .15;spread=float(np.clip(wape,.05,.35));output=[]
    horizon=pd.date_range(pd.Timestamp(start).replace(day=1),periods=months,freq='MS')
    for i,month in enumerate(horizon):
        dates=pd.date_range(month,month+pd.offsets.MonthEnd());normal=[]
        for date in dates:
            known=forecast[pd.to_datetime(forecast.tarih).dt.normalize()==date] if forecast is not None else pd.DataFrame()
            normal.append(float(known.y_pred.iloc[0]) if not known.empty else float(base.get(date.weekday(),h.cagri_sayisi.mean()))*float(season.get(date.month,1))*(1+growth)**(i+1))
        for name,mult,loss in [('İyi',1-spread,attrition*.5),('Normal',1.,attrition),('Kötü',1+spread,min(1.,attrition*1.5))]:
            calls=np.asarray(normal)*mult;peak=max(calls)*peak_share;net=erlang_c_required_agents(peak,aht,1800,target_sl,seconds,occupancy)['m'];needed=math.ceil(net/(1-shrinkage)*7*16/(days*hours));available=math.floor(headcount*(1-loss)**(i+1));agents=math.floor(available*days*hours/(7*16)*(1-shrinkage));modeled=erlang_c_metrics_for_m(peak,aht,1800,agents,seconds)[1] if agents else 0
            output.append({'Ay':month.strftime('%Y-%m'),'Senaryo':name,'Çağrı tahmini':round(calls.sum()),'Mevcut personel':available,'Gerekli personel':needed,'Önerilen alım':max(0,needed-available),'Simüle SL (%)':round(100*modeled,1),'Tepe yarım saat çağrı':round(peak)})
    return pd.DataFrame(output),{'history_days':len(h),'wape':100*wape,'spread':100*spread,'history_start':str(h.tarih.min().date()),'history_end':str(h.tarih.max().date())}

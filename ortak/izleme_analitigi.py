"""Takip toleransı: eksik veri hiçbir zaman başarılı sayılmaz."""
import pandas as pd
import math

def assess(values,tolerance,counted=None):
    tolerance=float(tolerance)
    if not math.isfinite(tolerance) or tolerance<0:raise ValueError('Kabul edilen fark sıfır veya pozitif olmalı.')
    numbers=pd.to_numeric(values,errors='coerce');valid=numbers.notna()
    if counted is not None:valid &= counted.fillna(False).astype(bool)
    result=pd.Series('Veri yok',index=numbers.index)
    if counted is not None:result.loc[~counted.fillna(False).astype(bool)]='Ölçüm dışı'
    result.loc[valid & (numbers.abs()<=tolerance)]='Uygun';result.loc[valid & (numbers.abs()>tolerance)]='Sınır dışında'
    return result

def difference_color(value,tolerance):
    if pd.isna(value):return 'background-color:#edf1f5;color:#7a8699'
    if abs(float(value))<=tolerance:return 'background-color:#e0f3e9;color:#166349'
    strength=min(1.,(abs(float(value))-tolerance)/max(1.,tolerance*3));green=int(226-116*strength);blue=int(224-113*strength)
    return f'background-color:rgb(255,{green},{blue});color:#923333'

def call_history(frame,date_col,target):
    data=frame.copy();dates=pd.to_datetime(data[date_col],errors='coerce')
    if 'slot' in data and dates.dt.normalize().equals(dates):dates=dates+pd.to_timedelta((pd.to_numeric(data.slot,errors='coerce')-1)*30,unit='m')
    data=pd.DataFrame({'Zaman':dates,'Çağrı':pd.to_numeric(data[target],errors='coerce')});return data.dropna().sort_values('Zaman')

def daily_insights(history):
    daily=history.assign(Tarih=history.Zaman.dt.normalize()).groupby('Tarih',as_index=False)['Çağrı'].sum();daily['Hafta günü']=daily.Tarih.dt.weekday
    daily['Aynı gün ort.']=daily.groupby('Hafta günü')['Çağrı'].transform(lambda x:x.shift().rolling(4,min_periods=2).mean())
    daily['Sapma (%)']=100*(daily['Çağrı']-daily['Aynı gün ort.'])/daily['Aynı gün ort.'].replace(0,float('nan'))
    daily['7 gün ort.']=daily['Çağrı'].rolling(7,min_periods=1).mean();return daily

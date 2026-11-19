# Ortak / Ornek Gecmis Tahmin — bu ekranın / servisin uygulama kodu.
"""Örnek Geçmiş Tahmin — yalnızca sentetik çalışma alanında zaman ayrımlı bir hafta."""
import pandas as pd
from ortak.calisma_alani_deposu import connect,load_calls
from ortak.tahmin_kayit_servisi import capture_forecast,capture_profile
from ortak.interval_servisi import build_weekly_distribution


def prepare_demo_backtest(state):
    path=state.get('workspace_db_path')
    if not path:return
    with connect(path) as db:
        source=db.execute("SELECT value FROM metadata WHERE key='synthetic'").fetchone()
        if not source or source[0]!='true' or db.execute("SELECT 1 FROM metadata WHERE key='demo_backtest_week_v1'").fetchone():return
    raw=load_calls(True,path);daily=load_calls(False,path)
    if raw.empty:return
    latest=raw.tarih.max().normalize();week=latest-pd.Timedelta(days=latest.weekday()+7)
    training=daily[pd.to_datetime(daily.tarih)<week]
    if len(training)<35:return
    forecast=[]
    for day in pd.date_range(week,periods=7):
        same=training[pd.to_datetime(training.tarih).dt.weekday==day.weekday()].tail(4)
        forecast.append({'tarih':day,'y_pred':float(same.cagri_sayisi.mean())})
    profile=build_weekly_distribution(raw,str(week.date()))['profile']
    sample={**dict(state),'sp_active_ratio_profile_name':'Örnek geçmiş hafta · sentetik','sp_forecast_meta':{'model_name':'Geçmiş aynı gün ortalaması · zaman ayrımlı demo','demo_backtest':True},'sp_active_ratio_profile_meta':{'demo_backtest':True},'profile':{'username':'demo-generator'}}
    run=capture_forecast(sample,pd.DataFrame(forecast),profile)
    capture_profile(sample,profile,{'name':'Örnek geçmiş hafta · sentetik','demo_backtest':True,'forecast_run':run})
    with connect(path) as db:db.execute("INSERT OR IGNORE INTO metadata VALUES('demo_backtest_week_v1',?)",(run,))


def prepare_six_month_history(state):
    from ortak.calisma_modu import demo_enabled
    from ortak.gunluk_tahmin_deposu import capture_daily
    from ortak.cagri_tahmin_servisi import DAY_NAMES
    if not demo_enabled():return
    path=state['workspace_db_path']
    with connect(path) as db:
        if not db.execute("SELECT 1 FROM metadata WHERE key='synthetic' AND value='true'").fetchone() or db.execute("SELECT 1 FROM metadata WHERE key='faz4_six_month_forecasts'").fetchone():return
    raw=load_calls(True,path);daily=load_calls(False,path)
    if raw.empty:return
    raw['tarih']=pd.to_datetime(raw.tarih);daily['tarih']=pd.to_datetime(daily.tarih)
    latest=raw.tarih.max().normalize();first=latest-pd.DateOffset(months=6);first-=pd.Timedelta(days=first.weekday())
    for week in pd.date_range(first,latest,freq='7D'):
        training=raw[(raw.tarih<week)&(raw.tarih>=week-pd.Timedelta(days=56))].copy()
        if training.empty:continue
        training['Gün']=training.tarih.dt.weekday;training['Slot']=training.tarih.dt.hour*2+training.tarih.dt.minute//30+1
        profile=[];forecast=[]
        for day in pd.date_range(week,min(week+pd.Timedelta(days=6),latest)):
            hist=training[training['Gün']==day.weekday()];weights=hist.groupby('Slot').cagri_sayisi.mean().reindex(range(1,49),fill_value=0)
            if weights.sum()<=0:continue
            for slot,w in (weights/weights.sum()*100).items():profile.append({'Gün':DAY_NAMES[day.weekday()],'Slot':slot,'Oran(%)':float(w),'Tarih':day})
            totals=daily[(daily.tarih<week)&(daily.tarih>=week-pd.Timedelta(days=28))&(daily.tarih.dt.weekday==day.weekday())]
            forecast.append({'tarih':day,'y_pred':float(totals.cagri_sayisi.mean()) if not totals.empty else float(hist.groupby(hist.tarih.dt.date).cagri_sayisi.sum().mean())})
        if not forecast:continue
        meta={'model_name':'Sentetik geçmiş karşılaştırması · aynı gün ortalaması','synthetic':True,'retrospective':True,'training_cutoff':str(week.date()),'note':'Şimdi üretilen örnektir; geçmişte kaydedilmiş gerçek tahmin değildir.'}
        sample={**dict(state),'profile':{'username':'demo-generator'},'sp_forecast_meta':meta,'sp_active_ratio_profile_name':'Sentetik geçmiş dağılımı','sp_active_ratio_profile_meta':meta,'staffing_parameters':{'aht':300.,'target_sl':.8,'target_time':20.,'shrinkage':.3,'occ_target':.85}}
        frame=pd.DataFrame(forecast);ratios=pd.DataFrame(profile)
        capture_daily(sample,frame,meta);capture_forecast(sample,frame,ratios);capture_profile(sample,ratios,meta)
    with connect(path) as db:db.execute("INSERT OR IGNORE INTO metadata VALUES('faz4_six_month_forecasts','1')")

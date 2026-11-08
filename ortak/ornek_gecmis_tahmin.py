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

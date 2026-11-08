# Ortak / Odeme Takvimi — bu ekranın / servisin uygulama kodu.
"""One shared billing calendar for feature engineering and future predictions."""
import calendar
import pandas as pd


def billing_dates(first_year,last_year):
    cuts=set();due=set()
    for year in range(first_year-1,last_year+2):
        for month in range(1,13):
            last=calendar.monthrange(year,month)[1]
            dates=[pd.Timestamp(year,month,d) for d in (9,16,24)]
            dates.append(pd.Timestamp(year,month,31) if last==31 else pd.Timestamp(year,month,last)+pd.Timedelta(days=1))
            for cut in dates:
                cuts.add(cut.date());pay=cut+pd.Timedelta(days=9)
                while pay.weekday()>=5:pay+=pd.Timedelta(days=1)
                due.add(pay.date())
    return cuts,due


def billing_flag(series,kind):
    dates=pd.to_datetime(series,errors='coerce');years=dates.dt.year.dropna()
    if years.empty:return pd.Series(0,index=series.index,dtype=int)
    cuts,due=billing_dates(int(years.min()),int(years.max()))
    return dates.dt.date.isin(cuts if kind=='cut' else due).astype(int)

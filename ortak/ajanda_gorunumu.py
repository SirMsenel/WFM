"""Ajanda için ortak vardiya renkleriyle haftalık shift matrisi."""
import pandas as pd
from ortak.cagri_tahmin_servisi import DAY_NAMES


def weekly_grid(items,start,name):
    days=pd.date_range(pd.Timestamp(start).normalize(),periods=7);columns=[f'{d:%d.%m} {DAY_NAMES[d.weekday()]}' for d in days]
    work={'Personel':name+' · Çalışma',**dict.fromkeys(columns,'OFF')};meetings={}
    for item in items:
        a,b=pd.Timestamp(item['start']),pd.Timestamp(item['end'])
        for day,col in zip(days,columns):
            left,right=max(a,day),min(b,day+pd.Timedelta(days=1))
            if left>=right:continue
            clock=f'{left:%H:%M}–'+('24:00' if right==day+pd.Timedelta(days=1) else f'{right:%H:%M}')
            if item['kind']=='Çalışma':work[col]=(work[col]+'\n' if work[col]!='OFF' else '')+clock
            else:
                key=item.get('name') or item.get('employee_id','Personel');row=meetings.setdefault(key,{'Personel':key+' · Koçluk',**dict.fromkeys(columns,'—')});row[col]=(row[col]+'\n' if row[col]!='—' else '')+'Koçluk '+clock
    return pd.DataFrame([work]+list(meetings.values()))


def opportunity_grid(openings,start,name):
    days=pd.date_range(pd.Timestamp(start).normalize(),periods=7);data={'Personel':name+' · Kontenjan'}
    for day in days:
        groups={}
        for r in openings:
            a,b=pd.Timestamp(r['start']),pd.Timestamp(r['end'])
            if a.date()==day.date():groups[(a,b)]=groups.get((a,b),0)+int(r.get('remaining_capacity',1))
        data[f'{day:%d.%m} {DAY_NAMES[day.weekday()]}']='\n'.join(f'Kontenjan {a:%H:%M}–{b:%H:%M} · {count} kişi' for (a,b),count in sorted(groups.items())) or '—'
    return pd.DataFrame([data])

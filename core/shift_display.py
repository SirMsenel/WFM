"""Shared roster colours and calendar-day clipped shift statistics."""
import re
from datetime import timedelta
import pandas as pd
from modules.shift_planing.engine import bounds
from core.planning import SHIFT_LABELS

STATUS_COLORS={'OFF':('#edf2f7','#475569'),'Yıllık izin':('#fce7f3','#9d174d'),'Evlilik izni':('#ffedd5','#9a3412'),
 'Mazeret izni':('#e0f2fe','#075985'),'Rapor':('#fee2e2','#991b1b'),'Ücretsiz izin':('#f1e8df','#784d2c'),
 'Doğum izni':('#f5d0fe','#86198f'),'Bayram izni':('#dcfce7','#166534'),'Sınav':('#fef3c7','#92400e'),'Ders':('#ede9fe','#5b21b6')}
WINDOWS=[('Sabah','08:00–13:00',8,13,'#dff2ff','#075985'),('İkindi','13:00–17:00',13,17,'#fff0ce','#92400e'),
         ('Akşam','17:00–00:00',17,24,'#d5f3e8','#065f46'),('Gece','00:00–08:00',0,8,'#e5defc','#4c1d95')]


def cell_style(value):
    text=str(value)
    if '⚠' in text:return 'background-color:#fee2e2;color:#991b1b;font-weight:600'
    if 'Gece' in text and re.search(r'\d\d:\d\d',text):bg,fg=WINDOWS[3][4:]
    else:
        match=next(((bg,fg) for label,(bg,fg) in STATUS_COLORS.items() if label in text),None)
        if match:bg,fg=match
        else:
            found=re.search(r'(\d{2}):(\d{2})',text)
            if not found:
                part=next((w for w in WINDOWS if w[0] in text),None)
                if part:return f'background-color:{part[4]};color:{part[5]};font-weight:600'
                return 'color:#94a3b8'
            hour=int(found[1]);part=0 if 8<=hour<13 else 1 if 13<=hour<17 else 2 if 17<=hour else 3
            bg,fg=WINDOWS[part][4:]
    return f'background-color:{bg};color:{fg};font-weight:600'


def shift_stats(records,start,end):
    left=pd.Timestamp(start);right=pd.Timestamp(end)+pd.Timedelta(days=1)
    output={'total_hours':0.,'work_days':0,'off_days':0,'night_count':0,'status_counts':{},'parts':{w[0]:0. for w in WINDOWS}}
    worked=set();off=set();statuses={}
    for row in records:
        day=pd.Timestamp(row['date']);interval=bounds(row)
        if interval is None:
            if left<=day<right:
                code=row.get('shift_code','OFF');statuses[code]=statuses.get(code,0)+1
                if code=='OFF':off.add(str(day.date()))
            continue
        a=max(pd.Timestamp(interval[0]),left);b=min(pd.Timestamp(interval[1]),right)
        if b<=a:continue
        output['total_hours']+=(b-a).total_seconds()/3600
        night_hours=0.
        for date in pd.date_range(a.normalize(),b.normalize()):
            if max(a,date)<min(b,date+pd.Timedelta(days=1)):worked.add(str(date.date()))
            for name,_,begin,finish,*_ in WINDOWS:
                x=max(a,date+pd.Timedelta(hours=begin));y=min(b,date+pd.Timedelta(hours=finish))
                if y>x:
                    hours=(y-x).total_seconds()/3600;output['parts'][name]+=hours
                    if name=='Gece':night_hours+=hours
        start_min=interval[0].hour*60+interval[0].minute
        if night_hours>0 and (row.get('shift_code')=='GECE' or interval[1].date()>interval[0].date() or start_min<420):output['night_count']+=1
    output.update(work_days=len(worked),off_days=len(off),status_counts=statuses)
    return output

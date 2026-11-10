"""Statü kuralları, yarım saat shrinkage ve planlı yemeklerin kapasite etkisi."""
import pandas as pd
from modules.vardiya_plani.vardiya_motoru import bounds


def defaults():
    return {'groups':{g:{'meal_minutes':30,'meal_start':'12:00','meal_end':'15:00','break_minutes':15,'min_shift_hours':4,'relative':True,'after_start':3,'before_start':6} for g in ('fulltime','akademi','dis_kaynak')},'friday':{'enabled':False,'male_only':False,'start':'12:00','end':'14:00','minutes':60}}


def shrinkage_for(state,day,slot,fallback=.30):
    value=float(fallback)
    for rule in state.get('slot_shrinkage',[]):
        if (not rule.get('weekdays') or pd.Timestamp(day).weekday() in rule['weekdays']) and int(rule['start_slot'])<=slot<=int(rule['end_slot']):value=float(rule['rate'])
    if not 0<=value<1:raise ValueError('Shrinkage %0–%99 arasında olmalı.')
    return value


def meal_plan(state,rows,coverage,people):
    cfg=state.get('status_rules') or {};lookup={str(e['employee_id']):e for e in people};scheduled=[];issues=[]
    if not cfg.get('enabled',False):return scheduled,coverage,issues
    out=coverage.copy();out['Mola kaybı']=0.
    for row in rows:
        interval=bounds(row)
        if not interval:continue
        person=lookup.get(str(row['employee_id']),{});rule=cfg.get('groups',{}).get(person.get('work_type'),{});a,b=map(pd.Timestamp,interval)
        if (b-a).total_seconds()/3600<float(rule.get('min_shift_hours',4)):continue
        items=[('Yemek',rule.get('meal_minutes',30),rule.get('meal_start','12:00'),rule.get('meal_end','15:00'))]
        friday=cfg.get('friday',{})
        if a.weekday()==4 and friday.get('enabled') and (not friday.get('male_only') or person.get('gender')=='Erkek'):items.append(('Cuma',friday.get('minutes',60),friday.get('start','12:00'),friday.get('end','14:00')))
        for kind,duration,left,right in items:
            if not duration:continue
            day=a.normalize()
            if kind=='Yemek' and rule.get('relative',True):left=a+pd.Timedelta(hours=float(rule.get('after_start',3)));right=min(b-pd.Timedelta(minutes=30),a+pd.Timedelta(hours=float(rule.get('before_start',6))))
            else:left=max(a+pd.Timedelta(hours=1),day+pd.Timedelta(left+':00'));right=min(b-pd.Timedelta(minutes=30),day+pd.Timedelta(right+':00'))
            if kind=='Cuma' and (left>=b or right<=a):continue
            selected=out.index[(pd.to_datetime(out.Tarih)>=a.normalize())&(pd.to_datetime(out.Tarih)<=b.normalize())].to_numpy()
            stamps=(pd.to_datetime(out.loc[selected,'Tarih'])+pd.to_timedelta((out.loc[selected,'Slot']-1)*30,unit='m')).to_numpy(dtype='datetime64[ns]')
            import numpy as np
            needs=out.loc[selected,'İhtiyaç'].to_numpy(dtype=float);assigned=out.loc[selected,'Atanan'].to_numpy(dtype=float);losses=out.loc[selected,'Mola kaybı'].to_numpy(dtype=float)
            best=None
            for t in pd.date_range(left,right-pd.Timedelta(minutes=duration),freq='15min'):
                finish=t+pd.Timedelta(minutes=duration)
                if any(x['employee_id']==str(row['employee_id']) and t<pd.Timestamp(x['end']) and pd.Timestamp(x['start'])<finish for x in scheduled):continue
                impact=[]
                overlap=np.maximum(0,(np.minimum(np.datetime64(finish),stamps+np.timedelta64(30,'m'))-np.maximum(np.datetime64(t),stamps))/np.timedelta64(30,'m'))
                cost=float(np.maximum(0,needs-assigned+losses+overlap)[overlap>0].sum())
                impact=[(int(i),float(v)) for i,v in zip(selected,overlap) if v>0]
                candidate=(cost,t,finish,impact)
                if best is None or candidate[0]<best[0]:best=candidate
            if best is None:issues.append({'employee_id':str(row['employee_id']),'date':row['date'],'Sorun':kind+' için vardiya içinde uygun pencere yok'});continue
            _,t,finish,impact=best;scheduled.append({'employee_id':str(row['employee_id']),'date':row['date'],'kind':kind,'start':str(t),'end':str(finish),'status':'Planlı'})
            for i,amount in impact:out.at[i,'Mola kaybı']+=amount
    out['Brüt Atanan']=out['Atanan'];out['Atanan']=(out['Atanan']-out['Mola kaybı']).clip(lower=0)
    out['Eksik']=(out['İhtiyaç']-out['Atanan']).clip(lower=0);out['Fazla']=(out['Atanan']-out['İhtiyaç']).clip(lower=0)
    if 'Sayaca Dahil' in out:out.loc[~out['Sayaca Dahil'],['Eksik','Fazla']]=0
    return scheduled,out,issues

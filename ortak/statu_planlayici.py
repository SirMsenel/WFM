"""Hat kapasitesine göre yemek, mola ve aylık koçluk yerleştirmesi."""
import numpy as np
import pandas as pd
from modules.vardiya_plani.vardiya_motoru import bounds
from ortak.calisma_alani_deposu import connect,loads


def coaching_used(state):
    used={};path=state.get('workspace_db_path')
    if not path:return used
    with connect(path) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='planned_breaks'").fetchone():return used
        reserved=[]
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='coaching_openings'").fetchone():reserved=[r[0] for r in db.execute("SELECT payload FROM coaching_openings WHERE status='Açık'")]
        for row in list(db.execute('SELECT payload FROM planned_breaks'))+[(r,) for r in reserved]:
            p=loads(row[0])
            if p.get('kind')!='Koçluk' or p.get('status')=='İptal':continue
            a,b=pd.Timestamp(p['start']),pd.Timestamp(p['end']);k=(str(p['employee_id']),a.strftime('%Y-%m'));used[k]=used.get(k,0)+(b-a).total_seconds()/60
    return used


class MolaKuralHatasi(ValueError):
    """Vardiyanın mola hakkı kuraldan belirlenemiyor; sıfır kabul edilmez."""


def allowance(rule,hours):
    import math
    rules=rule.get('break_rules')
    if rules is not None:
        try:choices=[r for r in rules if float(r['min_hours'])<=hours<float(r['max_hours'])]
        except (KeyError,TypeError,ValueError):raise MolaKuralHatasi('Mola tablosundaki çalışma alt/üst sınırlarını ve süreleri doldurun.')
        if not choices:raise MolaKuralHatasi(f'{hours:g} saatlik vardiya için mola kuralı bulunamadı. Alt sınır dahildir, üst sınır hariçtir; bu süreyi kapsayan satır tanımlayın. Mola yoksa 0 dakika açıkça girilmelidir.')
        if len(choices)>1:raise MolaKuralHatasi(f'{hours:g} saatlik vardiya için birden fazla mola kuralı eşleşiyor; aralıkları düzeltin.')
        value=choices[0].get('minutes')
    else:value=rule.get('break_total_minutes',rule.get('break_minutes',15))
    try:minutes=float(value)
    except (TypeError,ValueError):raise MolaKuralHatasi('Toplam mola süresi boş olamaz; dakika cinsinden tam sayı girin.')
    if not math.isfinite(minutes) or minutes<0 or not minutes.is_integer():raise MolaKuralHatasi('Toplam mola süresi negatif olmayan tam dakika olmalı.')
    return int(minutes)


def net_capacity(gross,loss,rate):
    """Shrinkage statüleri kapsar; yalnızca bütçeyi aşan statü fazladan kayıptır."""
    return gross-np.maximum(gross*rate,loss)


def plan(state,rows,coverage,people,used=None):
    cfg=state.get('status_rules') or {};lookup={str(p['employee_id']):p for p in people};scheduled=[];issues=[]
    if not cfg.get('enabled'):return scheduled,coverage,issues
    cfg={**cfg,'automatic':True}
    out=coverage.copy();out['Mola kaybı']=0.;dates=pd.to_datetime(out.Tarih);stamps=(dates+pd.to_timedelta((out.Slot-1)*30,unit='m')).to_numpy(dtype='datetime64[ns]')
    need=out['İhtiyaç'].to_numpy(float);gross=out.Atanan.to_numpy(float);loss=np.zeros(len(out));rates=np.zeros(len(out));included=bool(cfg.get('shrinkage_included'))
    if included:
        from ortak.statuler import shrinkage_for
        params=state.get('staffing_parameters',{});fallback=float(params.get('shrinkage',.3));source=state.get('sp_staffing_result_df');mapping={}
        if source is not None and 'Shrinkage (%)' in source:mapping={(str(pd.Timestamp(r['Tarih']).date()),int(r['Slot'])):float(r['Shrinkage (%)'])/100 for r in source.to_dict('records')}
        rates=np.array([mapping.get((str(pd.Timestamp(r['Tarih']).date()),int(r['Slot'])),shrinkage_for(state,r['Tarih'],int(r['Slot']),fallback)) for r in out.to_dict('records')])
    net_need=need*(1-rates)
    if included and 'Net Agent' in out:
        measured=pd.to_numeric(out['Net Agent'],errors='coerce').to_numpy(float);net_need=np.maximum(net_need,np.where(np.isfinite(measured),measured,net_need))
    coached=dict(coaching_used(state) if used is None else used);by_person={};hour_use={}
    for item in state.get('_status_fixed_baseline',[]):
        a,b=pd.Timestamp(item['start']),pd.Timestamp(item['end']);overlap=np.maximum(0,(np.minimum(np.datetime64(b),stamps+np.timedelta64(30,'m'))-np.maximum(np.datetime64(a),stamps))/np.timedelta64(30,'m'));loss[:]+=overlap;by_person.setdefault(str(item['employee_id']),[]).append(item)
    def place(row,kind,duration,a,b,mandatory=False,probe=False):
        if duration<=0:return True
        eid=str(row['employee_id']);best=None;rule=cfg.get('groups',{}).get(lookup.get(eid,{}).get('work_type'),{})
        indices=np.flatnonzero((stamps+np.timedelta64(30,'m')>np.datetime64(a))&(stamps<np.datetime64(b)))
        local_stamps=stamps[indices];local_need=net_need[indices];local_gross=gross[indices];local_rates=rates[indices];local_loss=loss[indices]
        counted=out['Sayaca Dahil'].to_numpy(bool)[indices] if 'Sayaca Dahil' in out else np.ones(len(indices),bool)
        before=np.maximum(0,local_need-net_capacity(local_gross,local_loss,local_rates))
        for t in pd.date_range(a,b-pd.Timedelta(minutes=duration),freq='5min'):
            finish=t+pd.Timedelta(minutes=duration)
            if any(t<pd.Timestamp(x['end']) and pd.Timestamp(x['start'])<finish for x in by_person.get(eid,[])):continue
            if kind=='Mola':
                limit=int(rule.get('break_per_hour_max',15));
                maximum=min(15,max(1,int(rule.get('break_minutes',15))));left,right=t,finish
                while True:
                    before_span=(left,right)
                    for old in by_person.get(eid,[]):
                        x,y=pd.Timestamp(old['start']),pd.Timestamp(old['end'])
                        if old['kind']=='Mola' and x<=right and left<=y:left,right=min(left,x),max(right,y)
                    if (left,right)==before_span:break
                if (right-left).total_seconds()/60>maximum:continue
                buckets={x.floor('h'):0 for x in pd.date_range(t,finish-pd.Timedelta(seconds=1),freq='5min')}
                for bucket in buckets:buckets[bucket]=max(0,(min(finish,bucket+pd.Timedelta(hours=1))-max(t,bucket)).total_seconds()/60)
                if any(hour_use.get((eid,k),0)+v>limit for k,v in buckets.items()):continue
            overlap=np.maximum(0,(np.minimum(np.datetime64(finish),local_stamps+np.timedelta64(30,'m'))-np.maximum(np.datetime64(t),local_stamps))/np.timedelta64(30,'m'))
            if overlap.sum()+1e-8<duration/30:continue
            after=np.maximum(0,local_need-net_capacity(local_gross,local_loss+overlap,local_rates));cost=float(((after-before)*counted).sum())
            if not mandatory and cost>1e-8:continue
            # Prefer middle of shift; capacity always has precedence.
            preference_penalty=max(0,(right-left).total_seconds()/60-min(maximum,max(1,int(rule.get('break_preferred_minutes',10))))) if kind=='Mola' else 0
            candidate=(cost,preference_penalty*1e9+abs((t+(finish-t)/2-(a+(b-a)/2)).total_seconds()),t,finish,overlap)
            if best is None or candidate[:2]<best[:2]:best=candidate
        if best is None:
            if probe:return False
            issues.append({'employee_id':eid,'date':row['date'],'Sorun':kind+' için uygun kapasite/pencere yok; '+('vardiyayı veya ihtiyacı düzenleyin' if mandatory else 'uygun başka döneme ertelendi'),'severity':'error' if mandatory else 'warning','override_required':False});return False
        _,__,t,finish,overlap=best;loss[indices]+=overlap;item={'employee_id':eid,'date':row['date'],'kind':kind,'start':str(t),'end':str(finish),'status':'Planlı'};scheduled.append(item);by_person.setdefault(eid,[]).append(item)
        if kind=='Mola':
            for bucket in pd.date_range(t.floor('h'),(finish-pd.Timedelta(seconds=1)).floor('h'),freq='h'):hour_use[(eid,bucket)]=hour_use.get((eid,bucket),0)+(min(finish,bucket+pd.Timedelta(hours=1))-max(t,bucket)).total_seconds()/60
        return True
    working=[]
    for row in sorted(rows,key=lambda x:(x['date'],str(x['employee_id']))):
        span=bounds(row)
        if not span:continue
        a,b=map(pd.Timestamp,span);eid=str(row['employee_id']);rule=cfg.get('groups',{}).get(lookup.get(eid,{}).get('work_type'),{});hours=(b-a).total_seconds()/3600;working.append((row,a,b,rule,hours))
        if not rule.get('meal_disabled') and hours>=float(rule.get('min_shift_hours',4)):
            duration=int(rule.get('meal_minutes',30))
            for override in rule.get('meal_day_overrides',[]):
                if a.weekday() in override.get('weekdays',[]):duration=int(override['minutes'])
            if cfg.get('automatic',False):left=a+pd.Timedelta(minutes=min(60,hours*15));right=b-pd.Timedelta(minutes=30)
            elif rule.get('relative',True):left=a+pd.Timedelta(hours=float(rule.get('after_start',3)));right=min(b-pd.Timedelta(minutes=30),a+pd.Timedelta(hours=float(rule.get('before_start',6))))
            else:left=max(a+pd.Timedelta(hours=1),a.normalize()+pd.Timedelta(rule.get('meal_start','12:00')+':00'));right=min(b-pd.Timedelta(minutes=30),a.normalize()+pd.Timedelta(rule.get('meal_end','15:00')+':00'))
            place(row,'Yemek',duration,left,right,True)
        friday=cfg.get('friday',{})
        if a.weekday()==4 and friday.get('enabled') and (not friday.get('male_only') or lookup.get(eid,{}).get('gender')=='Erkek'):
            left=max(a,a.normalize()+pd.Timedelta(friday.get('start','12:00')+':00'));right=min(b,a.normalize()+pd.Timedelta(friday.get('end','14:00')+':00'))
            if left<right:place(row,'Cuma',int(friday.get('minutes',60)),left,right,True)
    if cfg.get('automatic',False):
        for row,a,b,rule,hours in working:
            night=(row.get('shift_code')=='GECE')
            night_rules=(state.get('shift_rules') or {}).get('night',{})
            try:remaining=int(night_rules.get('break_total_minutes',60)) if night and hours>=8 else allowance(rule,hours)
            except MolaKuralHatasi as exc:
                issues.append({'employee_id':str(row['employee_id']),'date':row['date'],'Sorun':str(exc),'severity':'error','override_required':False});continue
            maximum=min(15,max(1,int(rule.get('break_minutes',15))));chunk=min(maximum,max(1,int(rule.get('break_preferred_minutes',10))))
            while remaining>0:
                candidates=range(min(chunk,remaining),0,-1)
                placed=False
                for duration in candidates:
                    if place(row,'Mola',duration,a+pd.Timedelta(minutes=rule.get('break_first_minutes',60)),b-pd.Timedelta(minutes=rule.get('break_last_minutes',60)),mandatory=True,probe=True):
                        remaining-=duration;placed=True;break
                if not placed:
                    issues.append({'employee_id':str(row['employee_id']),'date':row['date'],'Sorun':f'Mola hakkı tamamlanamadı: {remaining} dakika eksik. Vardiya süresi, ilk/son saat ve saatlik mola sınırını düzenleyin.','severity':'error','override_required':False});break
        if cfg.get('coaching_by_leader',False):
            from ortak.kocluk_kapasitesi import reserve_pool
            pools,reserve,pool_loss=reserve_pool(state,rows,coverage,people,scheduled,net_need,by_person,coached,allow=not any(x.get('severity')=='error' for x in issues))
            scheduled.extend(pools);loss+=pool_loss
        else:
            reserve=np.zeros(len(out))
            for row,a,b,rule,hours in (working if (state.get('status_rules') or {}).get('automatic') else []):
                eid=str(row['employee_id']);month=a.strftime('%Y-%m');remaining=int(rule.get('coaching_monthly_minutes',60))-coached.get((eid,month),0)
                if remaining<=0:continue
                duration=int(min(max(5,int(rule.get('coaching_chunk_minutes',15))),remaining));finish=min(b,(a+pd.offsets.MonthBegin(1)).normalize())
                if place(row,'Koçluk',duration,a+pd.Timedelta(minutes=60),finish-pd.Timedelta(minutes=60),probe=True):coached[(eid,month)]=coached.get((eid,month),0)+duration
    else:reserve=np.zeros(len(out))
    out['Brüt Atanan']=out['Atanan'];out['Mola kaybı']=loss;out['Shrinkage statü bütçesi']=gross*rates;out['Operasyon rezervi']=reserve
    # Keep the existing gross-need units throughout planning/approval counters.
    out['Atanan']=np.round(np.maximum(0,net_capacity(gross,loss+reserve,rates)/(1-rates)),8);out['Eksik']=(out['İhtiyaç']-out.Atanan).clip(lower=0);out['Fazla']=(out.Atanan-out['İhtiyaç']).clip(lower=0)
    if 'Sayaca Dahil' in out:out.loc[~out['Sayaca Dahil'],['Eksik','Fazla']]=0
    return scheduled,out,issues

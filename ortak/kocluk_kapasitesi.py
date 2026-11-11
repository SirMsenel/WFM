"""Tam yemek/mola dağıtımından sonra operasyon payı ve ortak koçluk kontenjanı."""
import numpy as np
import pandas as pd
from modules.vardiya_plani.vardiya_motoru import bounds


def reserve_pool(state,rows,coverage,people,scheduled,net_need,by_person,used,allow=True):
    cfg=state.get('status_rules',{});rate=float(cfg.get('operation_reserve_rate',.05));minutes=int(cfg.get('coaching_slot_minutes',15))
    if not 0<=rate<=.5 or minutes not in range(5,61,5):raise ValueError('Operasyon rezervi %0–50, koçluk dilimi 5–60 dakika / 5 dakika adımı olmalı.')
    reserve=np.zeros(len(coverage));pool_loss=np.zeros(len(coverage));output=[]
    if coverage.empty:return output,reserve,pool_loss
    starts=pd.to_datetime(coverage.Tarih)+pd.to_timedelta((coverage.Slot-1)*30,unit='min');mapping={t:i for i,t in enumerate(starts)}
    ticks=pd.date_range(starts.min(),starts.max()+pd.Timedelta(minutes=25),freq='5min');index=np.array([mapping.get(t.floor('30min'),-1) for t in ticks]);valid=index>=0
    counted=coverage['Sayaca Dahil'].to_numpy(bool) if 'Sayaca Dahil' in coverage else np.ones(len(coverage),bool)
    lookup={str(p['employee_id']):p for p in people};on_shift={};eligible={};blocked={};n=len(ticks)
    for eid,items in by_person.items():
        mask=np.zeros(n,bool)
        for item in items:
            a,b=pd.Timestamp(item['start']),pd.Timestamp(item['end']);mask|=(ticks<b)&(ticks+pd.Timedelta(minutes=5)>a)
        blocked[eid]=mask
    for row in state.get('_coaching_roster',rows):
        span=bounds(row)
        if not span:continue
        eid=str(row['employee_id']);a,b=map(pd.Timestamp,span);mask=(ticks>=a)&(ticks+pd.Timedelta(minutes=5)<=b)
        on_shift[eid]=on_shift.get(eid,np.zeros(n,bool))|mask
        rule=cfg.get('groups',{}).get(lookup.get(eid,{}).get('work_type'),{});target=int(rule.get('coaching_monthly_minutes',60))
        permitted=(ticks>=a+pd.Timedelta(minutes=60))&(ticks+pd.Timedelta(minutes=5)<=b-pd.Timedelta(minutes=60))
        monthly=np.array([target-used.get((eid,t.strftime('%Y-%m')),0)>=minutes for t in ticks])
        eligible[eid]=eligible.get(eid,np.zeros(n,bool))|(mask&permitted&monthly)
    workers=np.zeros(n);busy=np.zeros(n)
    for eid,mask in on_shift.items():workers+=mask;busy+=mask&blocked.get(eid,np.zeros(n,bool))
    need=np.zeros(n);need[valid]=net_need[index[valid]];room=np.maximum(0,workers-busy-need)
    active=valid.copy();active[valid]&=counted[index[valid]];room[~active]=0
    hold=room*rate
    for j in np.flatnonzero(valid):reserve[index[j]]+=hold[j]/6
    if not allow:return output,reserve,pool_loss
    available=np.floor(np.maximum(0,room-hold)+1e-8).astype(int)
    length=minutes//5
    # Non-overlapping time windows; each row is one seat, not one predetermined person.
    for begin in range(0,n,length):
        end=begin+length
        if end>n:break
        window=slice(begin,end);a=ticks[begin];b=a+pd.Timedelta(minutes=minutes)
        if a.month!=(b-pd.Timedelta(seconds=1)).month or not active[window].all():continue
        ids=[eid for eid,mask in eligible.items() if mask[window].all() and not blocked.get(eid,np.zeros(n,bool))[window].any()]
        capacity=min(len(ids),int(available[window].min()))
        if capacity:
            output.append({'employee_id':'*','eligible_employee_ids':ids,'pool':True,'capacity':capacity,'remaining_capacity':capacity,'languages':sorted({lookup.get(eid,{}).get('language') or 'tr' for eid in ids}),'date':str(a.date()),'kind':'Koçluk Alanı','start':str(a),'end':str(b),'status':'Açık','operation_reserve_count':float(hold[window].max())})
            np.add.at(pool_loss,index[window],capacity/6)
        available[window]-=capacity
    return output,reserve,pool_loss

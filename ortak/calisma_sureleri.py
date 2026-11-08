# Ortak / Calisma Sureleri — bu ekranın / servisin uygulama kodu.
"""Period hour totals and per-person group hour budgets."""
from datetime import timedelta
import pandas as pd
from modules.vardiya_plani.vardiya_motoru import bounds


def overlap_hours(row,start,end):
    interval=bounds(row)
    if not interval:return 0.
    left=max(interval[0],pd.Timestamp(start).to_pydatetime())
    right=min(interval[1],(pd.Timestamp(end)+pd.Timedelta(days=1)).to_pydatetime())
    return max(0.,(right-left).total_seconds()/3600)


def personnel_hours(state,people,start,end,published_only=False):
    from modules.vardiya_plani.planlama_verileri import collect_inputs
    records={(str(r['employee_id']),str(r['date'])):r for key in (('published_shift_plan',) if published_only else ('published_shift_plan','draft_shift_plan')) for r in state.get(key,[])}
    if not published_only and state.get('employees_cache') and state.get('plan_ctx'):
        source=dict(state);source['plan_ctx']={'start':start,'end':end};source['planning_languages']={'en':True,'ar':True}
        for r in collect_inputs(source)[1]:records[(str(r['employee_id']),str(r['date']))]=r
    days=(pd.Timestamp(end)-pd.Timestamp(start)).days+1
    result=[]
    for person in people:
        hours=sum(overlap_hours(r,start,end) for (eid,_),r in records.items() if eid==str(person['employee_id']))
        result.append({'Personel':person['full_name'],'Grup':person.get('work_type',''),'Toplam saat':hours,'Günlük ortalama saat':hours/max(1,days)})
    return pd.DataFrame(result)


def save_target(state,group,start,end,hours):
    from ortak.calisma_alani_deposu import save_keys
    start,end=str(pd.Timestamp(start).date()),str(pd.Timestamp(end).date())
    if start>end or hours<0:raise ValueError('Tarih aralığı ve süre geçerli olmalı.')
    previous=state.get('group_hour_targets',[])
    other=[t for t in previous if not(t['group']==group and t['start']==start and t['end']==end)]
    if any(t['group']==group and t['start']<=end and start<=t['end'] for t in other):
        raise ValueError('Bu grup için aynı tarihlere denk gelen başka bir süre hedefi var. Önce onu silin.')
    state['group_hour_targets']=other+[{'group':group,'start':start,'end':end,'hours':float(hours)}]
    save_keys(state)

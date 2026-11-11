"""Yemek ve mola hakkı eksik bir taslak onaya/yayına gönderilemez."""
import pandas as pd
from modules.vardiya_plani.vardiya_motoru import bounds
from ortak.statu_planlayici import allowance


def entitlements(state,row,person):
    span=bounds(row)
    if not span:return {'Yemek':0,'Mola':0}
    a,b=map(pd.Timestamp,span);hours=(b-a).total_seconds()/3600;cfg=state.get('status_rules',{});rule=cfg.get('groups',{}).get(person.get('work_type'),{})
    meal=0
    if not rule.get('meal_disabled') and hours>=float(rule.get('min_shift_hours',4)):
        meal=int(rule.get('meal_minutes',30))
        for override in rule.get('meal_day_overrides',[]):
            if a.weekday() in override.get('weekdays',[]):meal=int(override['minutes'])
    rest=int(state.get('shift_rules',{}).get('night',{}).get('break_total_minutes',60)) if row.get('shift_code')=='GECE' and hours>=8 else allowance(rule,hours)
    return {'Yemek':meal,'Mola':rest}


def balance(state,rows,people,items):
    lookup={str(p['employee_id']):p for p in people};output=[]
    for row in rows:
        if not bounds(row):continue
        eid=str(row['employee_id']);day=str(row['date']);person=lookup.get(eid,{})
        for kind,required in entitlements(state,row,person).items():
            booked=[x for x in items if str(x['employee_id'])==eid and str(x.get('date',x['start'][:10]))==day and x['kind']==kind]
            actual=sum((pd.Timestamp(x['end'])-pd.Timestamp(x['start'])).total_seconds()/60 for x in booked)
            output.append({'Personel':person.get('full_name',eid),'employee_id':eid,'date':day,'Statü':kind,'Hak (dk)':required,'Dağıtılan (dk)':actual,'Eksik (dk)':max(0,required-actual),'Fazla (dk)':max(0,actual-required)})
    return output


def assert_complete(state,result):
    if not state.get('status_rules',{}).get('enabled'):return
    bad=[r for r in balance(state,result.get('plan',[]),result.get('staff',[]),result.get('breaks',[])) if r['Eksik (dk)']>1e-8 or r['Fazla (dk)']>1e-8]
    if bad:
        r=bad[0];raise ValueError(f"Yemek/mola hakkı tamamlanmalı: {r['Personel']} · {r['date']} · {r['Statü']}: hak {r['Hak (dk)']:g} dk, dağıtılan {r['Dağıtılan (dk)']:g} dk. Eksikleri kabul ederek yayınlanamaz.")

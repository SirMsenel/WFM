"""Yemek ve mola hakkı eksik bir taslak onaya/yayına gönderilemez."""
import pandas as pd
from modules.vardiya_plani.vardiya_motoru import bounds
from ortak.statu_planlayici import allowance,MolaKuralHatasi


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
        span=bounds(row)
        if not span:continue
        eid=str(row['employee_id']);day=str(row['date']);person=lookup.get(eid,{});base={'Personel':person.get('full_name',eid),'employee_id':eid,'date':day}
        booked=[x for x in items if x.get('status')!='İptal' and str(x['employee_id'])==eid and str(x.get('date') or x['start'][:10])==day]
        try:rights=entitlements(state,row,person)
        except MolaKuralHatasi as exc:
            actual=sum((pd.Timestamp(x['end'])-pd.Timestamp(x['start'])).total_seconds()/60 for x in booked if x['kind']=='Mola')
            output.append({**base,'Statü':'Mola','Hak (dk)':None,'Dağıtılan (dk)':actual,'Eksik (dk)':0.,'Fazla (dk)':0.,'Kural hatası':str(exc)});continue
        rule=state.get('status_rules',{}).get('groups',{}).get(person.get('work_type'),{});maximum=min(15,max(1,int(rule.get('break_minutes',15))))
        for kind,required in rights.items():
            selected=sorted([x for x in booked if x['kind']==kind],key=lambda x:x['start']);actual=0.;errors=[];merged=[];hourly={}
            for item in selected:
                a,b=pd.Timestamp(item['start']),pd.Timestamp(item['end']);minutes=(b-a).total_seconds()/60;actual+=minutes
                if minutes<=0 or a<pd.Timestamp(span[0]) or b>pd.Timestamp(span[1]):errors.append('Statü saati kendi vardiyası içinde olmalı.')
                if any(a<pd.Timestamp(x['end']) and pd.Timestamp(x['start'])<b for x in booked if x is not item):errors.append('Statü saatleri birbiriyle çakışıyor.')
                if kind=='Mola':
                    if minutes>maximum:errors.append(f'Tek mola en fazla {maximum} dakika olabilir; {minutes:g} dakika kayıt var.')
                    if a<pd.Timestamp(span[0])+pd.Timedelta(minutes=rule.get('break_first_minutes',60)) or b>pd.Timestamp(span[1])-pd.Timedelta(minutes=rule.get('break_last_minutes',60)):errors.append('Vardiyanın korunan ilk/son saatinde mola var.')
                    if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
                    else:merged.append((a,b))
                    if b>a:
                        for h in pd.date_range(a.floor('h'),(b-pd.Timedelta(microseconds=1)).floor('h'),freq='h'):hourly[h]=hourly.get(h,0)+(min(b,h+pd.Timedelta(hours=1))-max(a,h)).total_seconds()/60
            if kind=='Mola':
                if any((b-a).total_seconds()/60>maximum for a,b in merged):errors.append(f'Bitişik molalar toplamda {maximum} dakikayı aşamaz; aralarında çalışma olmalı.')
                if any(v>float(rule.get('break_per_hour_max',15))+1e-8 for v in hourly.values()):errors.append('Bir saatteki mola toplamı grup sınırını aşıyor.')
            output.append({**base,'Statü':kind,'Hak (dk)':required,'Dağıtılan (dk)':actual,'Eksik (dk)':max(0,required-actual),'Fazla (dk)':max(0,actual-required),'Kural hatası':' '.join(dict.fromkeys(errors))})
    return output


def assert_complete(state,result):
    if not state.get('status_rules',{}).get('enabled'):return
    bad=[r for r in balance(state,result.get('plan',[]),result.get('staff',[]),result.get('breaks',[])) if r['Eksik (dk)']>1e-8 or r['Fazla (dk)']>1e-8 or r.get('Kural hatası')]
    if bad:
        r=bad[0]
        if r.get('Kural hatası'):raise ValueError(f"{r['Personel']} · {r['date']} · {r['Statü']}: {r['Kural hatası']}")
        raise ValueError(f"Yemek/mola hakkı tamamlanmalı: {r['Personel']} · {r['date']} · {r['Statü']}: hak {r['Hak (dk)']:g} dk, dağıtılan {r['Dağıtılan (dk)']:g} dk. Eksikleri kabul ederek yayınlanamaz.")

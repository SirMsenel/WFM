# Ortak / Off Dagilimi — bu ekranın / servisin uygulama kodu.
"""OFF Dağılımı — tam haftalarda ihtiyacı gözeten dengeli izin rezervasyonu."""
from datetime import timedelta
from modules.vardiya_plani.vardiya_motoru import bounds


def plan_off_days(members,staff,days,demand,existing,rules):
    policy=rules.get('off_rules',{})
    if policy.get('distribution','Mevcut sıra')!='İhtiyaca göre dağıt':return set()
    result=set();byweek={}
    for day in days:byweek.setdefault(day.isocalendar()[:2],[]).append(day)
    for _,week in byweek.items():
        if len(week)!=7:continue
        load={day:float(demand.loc[demand.Tarih==day,'Planlanan Agent'].max()) if (demand.Tarih==day).any() else 0. for day in week}
        reserved={day:0 for day in week};count=max(1,len(members))
        for eid in members:
            group=staff[eid]['work_type'];rule=rules['work_type'][group]
            minimum=int(rule.get('min_off_days',max(1,7-int(rule.get('max_days_per_week',rule.get('max_days_per_week_default',6))))))
            own=[r for r in existing if str(r['employee_id'])==eid and r['date'] in {d.isoformat() for d in week}]
            fixed_work={r['date'] for r in own if bounds(r)};fixed_off={r['date'] for r in own if not bounds(r)}
            chosen={d for d in week if d.isoformat() in fixed_off}
            for day in chosen:reserved[day]+=1
            for _ in range(max(0,minimum-len(chosen))):
                candidates=[d for d in week if d not in chosen and d.isoformat() not in fixed_work]
                if not candidates:break
                preferred=set(rule.get('preferred_off_days',[]))
                day=min(candidates,key=lambda d:(0 if d.weekday() in preferred else 1,load[d]/max(1,count-reserved[d]),reserved[d],(d.weekday()-int(eid) if eid.isdigit() else d.weekday())%7))
                chosen.add(day);reserved[day]+=1
            result.update((eid,d) for d in chosen)
    return result

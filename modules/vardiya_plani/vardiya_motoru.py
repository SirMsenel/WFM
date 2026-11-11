# Vardiya Plani / Vardiya Motoru — bu ekranın / servisin uygulama kodu.
"""Data-source-independent, deterministic half-hour demand scheduler.

Greedy coverage maximisation, not a proof of a globally optimal roster.
All timestamps are local, naive datetimes, as in the source application.
"""
from collections import defaultdict
from datetime import date, datetime, time, timedelta
import math

import numpy as np
import pandas as pd


NON_WORK = {"OFF", "YILLIK_IZIN", "EVLILIK_IZNI", "MAZERET_IZNI", "RAPOR", "UCRETSIZ_IZIN", "DOGUM_IZNI", "SINAV", "DERS", "BAYRAM"}


def minutes(value):
    h, m = map(int, str(value).strip().split(":"))
    if not 0 <= h <= 24 or not 0 <= m < 60 or (h == 24 and m):
        raise ValueError(f"Geçersiz saat: {value}")
    return h * 60 + m


def bounds(row):
    if row.get("shift_code") in NON_WORK:
        return None
    day = date.fromisoformat(str(row["date"])[:10])
    start, end = minutes(row["start"]), minutes(row["end"])
    if start == end:
        raise ValueError("Başlangıç ve bitiş aynı olamaz.")
    if end < start:
        end += 1440
    base = datetime.combine(day, time())
    return base + timedelta(minutes=start), base + timedelta(minutes=end)


def _overlap(a, b):
    return a[0] < b[1] and b[0] < a[1]


def _limit(value):
    result = minutes(value)
    return result + 1440 if result < 8 * 60 else result


def generate_plan(employees, demand, rules, group_order, start, end, fixed=(),
                  history=(), unavailable=None, auto_fill=True, strict_capacity=True, hour_targets=(), languages=None, exclude_early_hours=False, reject_invalid_sources=()):
    """Return plan/coverage/issues. Never mutates caller-owned rows or tables.

    Fixed rows are ordered by source precedence. Conflicting rows are reported
    and the earlier row wins. Outside-period history supplies week/rest limits.
    Unavailable maps employee IDs to absolute datetime intervals.
    """
    start, end = pd.Timestamp(start).date(), pd.Timestamp(end).date()
    fixed, history = list(fixed), list(history)
    if start > end or (end - start).days > 92:
        raise ValueError("Plan dönemi 1–93 gün arasında olmalı.")
    groups = rules.get("work_type", {})
    if len(group_order) != len(groups) or set(group_order) != set(groups):
        raise ValueError("Tüm çalışma grupları birer kez sıralanmalı.")
    staff = {}
    for emp in employees:
        if emp.get("position", "agent") != "agent":
            continue
        eid = str(emp["employee_id"])
        if eid in staff:
            raise ValueError(f"Tekrarlanan personel kimliği: {eid}")
        if emp.get("work_type") not in groups:
            raise ValueError(f"Personel {eid}: çalışma grubu kurallarda yok.")
        staff[eid] = dict(emp)
    if not staff:
        raise ValueError("Planlanabilecek agent bulunamadı.")
    df = demand.copy()
    if not {"Tarih", "Slot", "Planlanan Agent"} <= set(df):
        raise ValueError("İhtiyaç tablosunda Tarih, Slot, Planlanan Agent gerekli.")
    df["Tarih"] = pd.to_datetime(df["Tarih"], errors="raise").dt.date
    df = df[df["Tarih"].between(start, end)].sort_values(["Tarih", "Slot"]).reset_index(drop=True)
    if df.empty or df.duplicated(["Tarih", "Slot"]).any():
        raise ValueError("İhtiyaç tablosu boş veya aynı tarih/slot birden fazla kez var.")
    slots = pd.to_numeric(df["Slot"], errors="raise").to_numpy(dtype=float)
    required = pd.to_numeric(df["Planlanan Agent"], errors="raise").to_numpy(dtype=float)
    if (not np.isfinite(slots).all() or not np.isfinite(required).all()
            or ((slots < 1) | (slots > 48) | (slots % 1 != 0)).any()
            or (required < 0).any()):
        raise ValueError("Slot 1–48 arası tamsayı, ihtiyaç sonlu ve negatif olmayan sayı olmalı.")
    required = np.ceil(required).astype(int)
    df["Slot"] = slots.astype(int)
    slot_starts = [datetime.combine(d, time()) + timedelta(minutes=(int(s)-1)*30)
                   for d, s in zip(df["Tarih"], slots)]
    stamp = np.array(slot_starts, dtype="datetime64[m]")
    covered = np.zeros(len(df), dtype=int)
    effective=~df['Slot'].between(7,16).to_numpy() if exclude_early_hours else np.ones(len(df),dtype=bool)
    unavailable = {str(eid): list(intervals) for eid, intervals in (unavailable or {}).items()}
    # A day off/leave is a full calendar-day exclusion, including work which
    # started on the previous date and continues past midnight.
    adjacent_history = [r for r in history if not str(start) <= str(r.get("date", ""))[:10] <= str(end)]
    for raw in fixed + adjacent_history:
        if raw.get("shift_code") in NON_WORK:
            try:
                day = date.fromisoformat(str(raw["date"])[:10])
                base = datetime.combine(day, time())
                unavailable.setdefault(str(raw.get("employee_id")), []).append((base, base+timedelta(days=1)))
            except (ValueError, KeyError, TypeError):
                pass  # Invalid rows are reported by the regular input pass.
    plan, issues = [], []
    by_employee = defaultdict(list)
    occupied = set()
    general = rules.get("general", {})
    boost = rules.get("boosts", {})

    def issue(row, reason):
        issues.append({"source":row.get("source"),"start":row.get("start"),"end":row.get("end"),"shift_code":row.get("shift_code"),"employee_id": str(row.get("employee_id", "")),
                       "date": str(row.get("date", "")), "Sorun": reason,"severity":"warning" if str(reason).startswith("Soft kural:") else "error","override_required":bool(groups.get(staff.get(str(row.get("employee_id")),{}).get("work_type"),{}).get("override_required_if_violate",True))})

    def indices(interval):
        a, b = map(lambda x: np.datetime64(x, "m"), interval)
        return np.flatnonzero((stamp >= a) & (stamp + np.timedelta64(30, "m") <= b))

    def violations(row, prior):
        eid = str(row["employee_id"])
        emp = staff[eid]
        group = emp["work_type"]
        rule = groups[group]
        day = date.fromisoformat(str(row["date"])[:10])
        interval = bounds(row)
        if interval is None:
            return []
        problems = []
        duration = (interval[1] - interval[0]).total_seconds() / 3600
        max_hours = float(rule.get("shift_total_hours_max", rule.get("shift_total_hours", 24)))
        if group=='fulltime' and row.get('shift_code')=='MESAI' and rules.get('capacity'):
            max_hours=max(max_hours,float(rule.get('shift_total_hours',9))+float(rules['capacity'].get('max_extension_hours',3)))
        if row.get('shift_code')=='GECE':
            ns=minutes(general.get('night_window_start','00:00'));ne=minutes(general.get('night_window_end','08:00'))
            max_hours=((ne-ns)%1440 or 1440)/60
        if emp.get('employment_start') and day<date.fromisoformat(str(emp['employment_start'])[:10]):problems.append('İşe giriş tarihinden önce çalışma yazılamaz')
        if emp.get('employment_end') and day>=date.fromisoformat(str(emp['employment_end'])[:10]):problems.append('Ayrılma tarihinde veya sonrasında çalışma yazılamaz')
        if duration > max_hours:
            problems.append(f"Günlük süre sınırı aşılıyor: {duration:g} saat; izin verilen en fazla {max_hours:g} saat")
        if row.get("shift_code") not in {"MESAI", "GECE"} and "shift_total_hours" in rule and not rule.get("allow_flexible_hours") and not row.get("attendance_adjusted") and duration != float(rule["shift_total_hours"]):
            problems.append("Sabit vardiya süresi sağlanmıyor")
        night = row.get("shift_code") == "GECE"
        if night:
            nr = rules.get("night", {})
            if not nr.get("enabled", True) or group not in nr.get("allowed_work_types", ["akademi"]) or not rule.get("night_allowed", False):
                problems.append("Bu grup için gece vardiyasına izin yok")
            if 'night_window_start' in general and 'night_window_end' in general:
                begin=minutes(row['start']);finish=begin+duration*60
                ns,ne=minutes(general['night_window_start']),minutes(general['night_window_end'])
                if ne<=ns:
                    ne+=1440
                if begin<ns or finish>ne:
                    problems.append('Gece vardiyası tanımlı gece saatleri dışında')
        else:
            earliest = minutes(general.get("weekend_general_start" if day.weekday() >= 5 else "weekday_general_start", "08:00"))
            begin = minutes(row["start"])
            early_boost = (group == "fulltime" and day.weekday() < 5 and begin == 420
                           and boost.get("weekday_0700_fulltime_extra_enabled", False))
            if begin < earliest and not early_boost:
                problems.append("Genel başlangıç saatinden erken")
            finish = minutes(row["end"])
            if finish <= begin:
                finish += 1440
            if finish > _limit(general.get("global_latest_end", "03:00")):
                problems.append("Genel bitiş sınırı aşılıyor")
            if rule.get("max_end_time") and finish > _limit(rule["max_end_time"]):
                problems.append(("" if rule.get("max_end_is_hard",True) else "Soft kural: ")+"Grup bitiş sınırı aşılıyor")
            if not rule.get('night_allowed',False):
                ns=minutes(general.get('night_window_start','00:00'))
                night_boundary=ns if ns>=12*60 else ns+1440
                if finish>night_boundary:
                    problems.append('Gece çalışması yasak olan grup gece dilimine taşıyor')
        if day.weekday()==4 and rules.get('friday',{}).get('block_men_midday') and staff[eid].get('gender')=='Erkek' and interval[0]<datetime.combine(day,time(14)) and datetime.combine(day,time(12))<interval[1]:problems.append('Cuma 12:00–14:00 erkek personel kısıtı')
        if any(_overlap(interval, block) for block in unavailable.get(eid, [])):
            problems.append("Ders/sınav veya uygun olmama kaydıyla çakışıyor")
        week = day.isocalendar()[:2]
        working_days = {date.fromisoformat(str(r["date"])[:10]) for r in prior if bounds(r)}
        max_days = int(rule.get("max_days_per_week", rule.get("max_days_per_week_default", 7)))
        max_days=min(max_days,7-int(rule.get('min_off_days',0)))
        if group == "fulltime" and rule.get("allow_6th_day",False):max_days=min(6,7-int(rule.get('min_off_days',1)))
        if group == "fulltime" and not rule.get("allow_6th_day", False):
            max_days = min(5, max_days)
        if len({d for d in working_days | {day} if d.isocalendar()[:2] == week}) > max_days:
            problems.append(f"Haftalık çalışma günü sınırı aşılıyor: en fazla {max_days} gün")
        consecutive=min(6,int(rule.get('max_consecutive_days',max_days)))
        all_work=working_days|{day};left=day;right=day
        while left-timedelta(days=1) in all_work:left-=timedelta(days=1)
        while right+timedelta(days=1) in all_work:right+=timedelta(days=1)
        count=(right-left).days+1
        if count>consecutive:
            problems.append(f'Üst üste çalışma sınırı aşılıyor: {count} gün; en fazla {consecutive} gün')
        rest = max(11., float(rule.get("min_rest_hours", 11)))
        for other in prior:
            oi = bounds(other)
            if oi is None:
                continue
            if _overlap(interval, oi):
                problems.append("Başka vardiyayla çakışıyor")
                break
            gap = min(abs((interval[0]-oi[1]).total_seconds()), abs((oi[0]-interval[1]).total_seconds())) / 3600
            if gap < rest:
                problems.append(f"Minimum dinlenme süresi sağlanmıyor: {gap:g} saat; en az {rest:g} saat olmalı")
                break
        from ortak.calisma_sureleri import overlap_hours
        for target in hour_targets:
            if target['group']!=group or not overlap_hours(row,target['start'],target['end']):continue
            total=sum(overlap_hours(r,target['start'],target['end']) for r in prior)+overlap_hours(row,target['start'],target['end'])
            if total>float(target['hours'])+1e-9:
                problems.append(f"Dönem çalışma süresi aşılıyor: {total:g} saat / {float(target['hours']):g} saat")
        return problems

    for raw in history:
        row = dict(raw)
        eid = str(row.get("employee_id"))
        if eid not in staff:
            continue
        try:
            day = date.fromisoformat(str(row["date"])[:10])
            interval = bounds(row)
            if not start <= day <= end:
                by_employee[eid].append(row)
                if interval:
                    covered[indices(interval)] += 1
        except (ValueError, TypeError, KeyError) as exc:
            issue(row, f"Geçmiş vardiya okunamadı: {exc}")

    # Adjacent fixed records also constrain weekly limits and rest, even when
    # they have never been published or copied into the draft.
    outside_fixed = set()
    for raw in fixed:
        try:
            day = date.fromisoformat(str(raw["date"])[:10])
            eid = str(raw.get("employee_id"))
            if not start <= day <= end and eid in staff:
                row = dict(raw, employee_id=eid)
                interval = bounds(row)
                key = (eid, day)
                if key in outside_fixed:
                    continue
                outside_fixed.add(key)
                kept = []
                for old in by_employee[eid]:
                    if str(old.get("date")) == str(row["date"]):
                        old_interval = bounds(old)
                        if old_interval:
                            covered[indices(old_interval)] -= 1
                    else:
                        kept.append(old)
                by_employee[eid] = kept + [row]
                if interval:
                    covered[indices(interval)] += 1
        except (ValueError, TypeError, KeyError) as exc:
            issue(raw, f"Komşu sabit vardiya okunamadı: {exc}")

    for raw in fixed:
        row = dict(raw)
        eid = str(row.get("employee_id"))
        try:
            day = date.fromisoformat(str(row["date"])[:10])
            if not start <= day <= end:
                continue
            if eid not in staff:
                issue(row, "Personel listesinde bulunamayan sabit kayıt")
                continue
            row.update(employee_id=eid, date=day.isoformat(), group=staff[eid]["work_type"])
            interval = bounds(row)
            key = (eid, day)
            if key in occupied:
                existing = next(r for r in plan if (r["employee_id"], r["date"]) == (eid, day.isoformat()))
                if any(existing.get(k) != row.get(k) for k in ("shift_code", "start", "end")):
                    issue(row, "Öncelikli sabit kayıtla çakışma; ilk kayıt korundu")
                continue
            problems=violations(row, by_employee[eid])
            for reason in problems:issue(row, reason)
            if any(not p.startswith("Soft kural:") for p in problems) and row.get("source") in reject_invalid_sources:continue
            plan.append(row)
            occupied.add(key)
            by_employee[eid].append(row)
            if interval:
                covered[indices(interval)] += 1
        except (ValueError, TypeError, KeyError) as exc:
            issue(row, f"Geçersiz sabit kayıt: {exc}")

    days = [start + timedelta(days=i) for i in range((end-start).days+1)]
    # Explicit 07:00 quota is placed before ordinary group filling. Otherwise an
    # earlier-priority group can consume every day slot before Full Time is tried.
    if auto_fill and 'fulltime' in group_order and boost.get('weekday_0700_fulltime_extra_enabled'):
        from ortak.off_dagilimi import plan_off_days
        early_members=[eid for eid,e in staff.items() if e['work_type']=='fulltime']
        early_off=plan_off_days(early_members,staff,days,df,plan,rules)
        duration=round(float(groups['fulltime'].get('shift_total_hours',9))*60)
        for day in days:
            if day.weekday()>=5:continue
            quota=int(boost.get('weekday_0700_fulltime_extra_count',0))
            used=sum(r['date']==str(day) and r.get('group')=='fulltime' and r.get('start')=='07:00' for r in plan)
            for eid in sorted(early_members,key=lambda e:(0 if day.weekday()==4 and rules.get('friday',{}).get('prefer_women_midday') and staff[e].get('gender')=='Kadın' else 1,sum((b[1]-b[0]).total_seconds() for r in by_employee[e] if (b:=bounds(r))),e)):
                if used>=quota:break
                if (eid,day) in occupied or (eid,day) in early_off:continue
                finish=420+duration
                row={'employee_id':eid,'date':str(day),'group':'fulltime','shift_code':'WORK','start':'07:00','end':f'{finish//60%24:02d}:{finish%60:02d}','source':'auto','note':'07:00 takviye kotası'}
                span=bounds(row);ix=indices(span);active=ix[effective[ix]]
                expected=sum(not exclude_early_hours or not 180<=((420+offset)%1440)<480 for offset in range(0,duration,30))
                caps=np.full(len(active),int(rules.get('capacity',{}).get('max_overstaff',0)),dtype=int)
                caps[np.asarray([pd.Timestamp(stamp[j]).hour==7 for j in active])]=max(int(rules.get('capacity',{}).get('max_overstaff',0)),quota)
                if strict_capacity and (len(active)!=expected or (covered[active]+1>required[active]+caps).any()):continue
                if violations(row,by_employee[eid]):continue
                plan.append(row);occupied.add((eid,day));by_employee[eid].append(row);covered[ix]+=1;used+=1
    for group in (group_order if auto_fill else []):
        rule = groups[group]
        max_hours = float(rule.get("shift_total_hours_max", rule.get("shift_total_hours", 0)))
        if not 0 < max_hours <= 24:
            raise ValueError(f"{group}: geçersiz vardiya süresi")
        durations = (list(range(round(float(rule['shift_total_hours'])*60),round(max_hours*60)+1,30)) if rule.get('allow_flexible_hours') and 'shift_total_hours' in rule else [round(max_hours*60)]) if 'shift_total_hours' in rule else list(range(max(30,round(float(rule.get('min_shift_hours',.5))*60)),round(max_hours*60)+1,30))
        members = [eid for eid, emp in staff.items() if emp["work_type"] == group]
        from ortak.off_dagilimi import plan_off_days
        off_days=plan_off_days(members,staff,days,df,plan,rules)
        for day in days:
            # Least-worked person goes first; ties are stable between reruns.
            def worked(eid):
                return sum((b[1]-b[0]).total_seconds() for r in by_employee[eid] if (b := bounds(r)))
            for eid in sorted(members, key=lambda e: (0 if day.weekday()==4 and rules.get('friday',{}).get('prefer_women_midday') and staff[e].get('gender')=='Kadın' else 1,worked(e),e)):
                if (eid, day) in occupied or (eid,day) in off_days:
                    continue
                earliest = minutes(general.get("weekend_general_start" if day.weekday() >= 5 else "weekday_general_start", "08:00"))
                starts = list(range(math.ceil(earliest/30)*30, 1440, 30))
                if group == "fulltime" and day.weekday() < 5 and boost.get("weekday_0700_fulltime_extra_enabled"):
                    used = sum(r["date"] == day.isoformat() and r.get("group") == "fulltime" and r.get("start") == "07:00" for r in plan)
                    if used < int(boost.get("weekday_0700_fulltime_extra_count", 0)):
                        starts.insert(0, 420)
                best, best_score = None, (0, 0, 0, 0)
                for begin in starts:
                    for duration in durations:
                        finish = begin + duration
                        if finish > _limit(general.get("global_latest_end", "03:00")):
                            continue
                        if rule.get("max_end_time") and finish > _limit(rule["max_end_time"]):
                            continue
                        row = {"employee_id": eid, "date": day.isoformat(), "group": group,
                               "shift_code": "WORK", "start": f"{begin//60:02d}:{begin%60:02d}",
                               "end": f"{(finish//60)%24:02d}:{finish%60:02d}", "source": "auto", "note": ""}
                        interval = bounds(row)
                        ix = indices(interval)
                        active_ix=ix[effective[ix]]
                        gain = int(np.count_nonzero(covered[active_ix] < required[active_ix]))
                        if not gain:
                            continue
                        expected=duration//30
                        if exclude_early_hours:
                            expected=sum(not 180<=((begin+offset)%1440)<480 for offset in range(0,duration,30))
                        allowance=int(rules.get('capacity',{}).get('max_overstaff',0))
                        early_quota=group=='fulltime' and day.weekday()<5 and begin==420 and boost.get('weekday_0700_fulltime_extra_enabled')
                        caps=np.full(len(active_ix),allowance,dtype=int)
                        if early_quota:caps[np.asarray([pd.Timestamp(stamp[j]).hour==7 for j in active_ix])]=max(allowance,int(boost.get('weekday_0700_fulltime_extra_count',0)))
                        if strict_capacity and (len(active_ix)!=expected or (covered[active_ix]+1>required[active_ix]+caps).any()):
                            continue
                        # Count all shift slots, including those outside the demand table.
                        excess = duration//30 - gain
                        daytime = (not rule.get("prefer_daytime") or
                                   (begin >= minutes(rule.get("daytime_window_start", "07:00"))
                                    and finish <= minutes(rule.get("daytime_window_end", "19:00"))))
                        early_needed=group=='fulltime' and day.weekday()<5 and begin==420 and boost.get('weekday_0700_fulltime_extra_enabled') and sum(r['date']==day.isoformat() and r.get('group')=='fulltime' and r.get('start')=='07:00' for r in plan)<int(boost.get('weekday_0700_fulltime_extra_count',0))
                        score = (gain+len(stamp) if early_needed else gain, -excess, int(daytime), -begin)
                        if score <= best_score or violations(row, by_employee[eid]):
                            continue
                        best, best_score = (row, interval, ix), score
                if best:
                    row, interval, ix = best
                    plan.append(row)
                    by_employee[eid].append(row)
                    occupied.add((eid, day))
                    covered[ix] += 1

    for eid in staff:
        for day in days:
            if (eid, day) not in occupied:
                plan.append({"employee_id": eid, "date": day.isoformat(), "group": staff[eid]["work_type"],
                             "shift_code": "OFF", "start": None, "end": None, "source": "auto", "note": ""})
    if auto_fill and boost.get('weekday_0700_fulltime_extra_enabled'):
        for day in days:
            if day.weekday()>=5:continue
            count=sum(r['date']==str(day) and r.get('group')=='fulltime' and r.get('start')=='07:00' for r in plan)
            target=int(boost.get('weekday_0700_fulltime_extra_count',0))
            if count<target:issue({'date':str(day)},f'Soft kural: 07:00 Full Time takviyesi {target} kişi; uygun yerleştirilen {count}.')
    night_rules=rules.get('night',{})
    targets=night_rules.get(night_rules.get('mode','normal'),{}) if night_rules.get('enabled') else {}
    if targets:
        for day in days:
            assigned=[r for r in plan if r['date']==day.isoformat() and r.get('shift_code')=='GECE']
            for language,needed in targets.items():
                if languages is not None and not languages.get(language,True):continue
                count=sum(staff[r['employee_id']].get('language')==language for r in assigned)
                if count!=int(needed):
                    issue({'date':day.isoformat()},f'Gece {language.upper()}: {needed} gerekli, {count} kesin kayıt var')
    for row in plan:
        row["full_name"] = staff[row["employee_id"]].get("full_name", row["employee_id"])
    df["İhtiyaç"] = required
    df["Atanan"] = covered
    df["Sayaca Dahil"] = effective
    df["Ham Eksik"] = np.maximum(0, required-covered)
    df["Eksik"] = np.where(effective,df["Ham Eksik"],0)
    df["Fazla"] = np.where(effective,np.maximum(0, covered-required),0)
    return {"plan": sorted(plan, key=lambda r: (r["date"], r["employee_id"])),
            "coverage": df, "issues": issues,"rules":rules,"history":history}

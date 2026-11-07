"""Data-source-independent, deterministic half-hour demand scheduler.

Greedy coverage maximisation, not a proof of a globally optimal roster.
All timestamps are local, naive datetimes, as in the source application.
"""
from collections import defaultdict
from datetime import date, datetime, time, timedelta
import math

import numpy as np
import pandas as pd


NON_WORK = {"OFF", "YILLIK_IZIN", "SINAV", "DERS", "BAYRAM"}


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
                  history=(), unavailable=None):
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
        issues.append({"employee_id": str(row.get("employee_id", "")),
                       "date": str(row.get("date", "")), "Sorun": reason})

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
        if duration > max_hours:
            problems.append("Günlük süre sınırı aşılıyor")
        if row.get("shift_code") not in {"MESAI", "GECE"} and "shift_total_hours" in rule and duration != float(rule["shift_total_hours"]):
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
                problems.append("Grup bitiş sınırı aşılıyor; otomatik esnetme yapılmaz")
            if not rule.get('night_allowed',False):
                ns=minutes(general.get('night_window_start','00:00'))
                night_boundary=ns if ns>=12*60 else ns+1440
                if finish>night_boundary:
                    problems.append('Gece çalışması yasak olan grup gece dilimine taşıyor')
        if any(_overlap(interval, block) for block in unavailable.get(eid, [])):
            problems.append("Ders/sınav veya uygun olmama kaydıyla çakışıyor")
        week = day.isocalendar()[:2]
        working_days = {date.fromisoformat(str(r["date"])[:10]) for r in prior if bounds(r)}
        max_days = int(rule.get("max_days_per_week", rule.get("max_days_per_week_default", 7)))
        if group == "fulltime" and not rule.get("allow_6th_day", False):
            max_days = min(5, max_days)
        if len({d for d in working_days | {day} if d.isocalendar()[:2] == week}) > max_days:
            problems.append("Haftalık çalışma günü sınırı aşılıyor")
        rest = float(rule.get("min_rest_hours", 0))
        for other in prior:
            oi = bounds(other)
            if oi is None:
                continue
            if _overlap(interval, oi):
                problems.append("Başka vardiyayla çakışıyor")
                break
            gap = min(abs((interval[0]-oi[1]).total_seconds()), abs((oi[0]-interval[1]).total_seconds())) / 3600
            if gap < rest:
                problems.append("Minimum dinlenme süresi sağlanmıyor")
                break
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
            for reason in violations(row, by_employee[eid]):
                issue(row, reason)
            plan.append(row)
            occupied.add(key)
            by_employee[eid].append(row)
            if interval:
                covered[indices(interval)] += 1
        except (ValueError, TypeError, KeyError) as exc:
            issue(row, f"Geçersiz sabit kayıt: {exc}")

    days = [start + timedelta(days=i) for i in range((end-start).days+1)]
    for group in group_order:
        rule = groups[group]
        max_hours = float(rule.get("shift_total_hours_max", rule.get("shift_total_hours", 0)))
        if not 0 < max_hours <= 24:
            raise ValueError(f"{group}: geçersiz vardiya süresi")
        durations = [round(max_hours*60)] if "shift_total_hours" in rule else list(range(30, round(max_hours*60)+1, 30))
        members = [eid for eid, emp in staff.items() if emp["work_type"] == group]
        for day in days:
            # Least-worked person goes first; ties are stable between reruns.
            def worked(eid):
                return sum((b[1]-b[0]).total_seconds() for r in by_employee[eid] if (b := bounds(r)))
            for eid in sorted(members, key=lambda e: (worked(e), e)):
                if (eid, day) in occupied:
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
                        gain = int(np.count_nonzero(covered[ix] < required[ix]))
                        if not gain:
                            continue
                        # Count all shift slots, including those outside the demand table.
                        excess = duration//30 - gain
                        daytime = (not rule.get("prefer_daytime") or
                                   (begin >= minutes(rule.get("daytime_window_start", "07:00"))
                                    and finish <= minutes(rule.get("daytime_window_end", "19:00"))))
                        score = (gain, -excess, int(daytime), -begin)
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
    night_rules=rules.get('night',{})
    targets=night_rules.get(night_rules.get('mode','normal'),{}) if night_rules.get('enabled') else {}
    if targets:
        for day in days:
            assigned=[r for r in plan if r['date']==day.isoformat() and r.get('shift_code')=='GECE']
            for language,needed in targets.items():
                count=sum(staff[r['employee_id']].get('language')==language for r in assigned)
                if count!=int(needed):
                    issue({'date':day.isoformat()},f'Gece {language.upper()}: {needed} gerekli, {count} kesin kayıt var')
    for row in plan:
        row["full_name"] = staff[row["employee_id"]].get("full_name", row["employee_id"])
    df["İhtiyaç"] = required
    df["Atanan"] = covered
    df["Eksik"] = np.maximum(0, required-covered)
    df["Fazla"] = np.maximum(0, covered-required)
    return {"plan": sorted(plan, key=lambda r: (r["date"], r["employee_id"])),
            "coverage": df, "issues": issues}

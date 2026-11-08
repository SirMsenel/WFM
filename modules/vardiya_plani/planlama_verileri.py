# Vardiya Plani / Planlama Verileri — bu ekranın / servisin uygulama kodu.
"""Adapters for current session/API sources; engine has no Streamlit dependency."""
from datetime import date, datetime, time, timedelta
import hashlib
import json

import pandas as pd

from ortak.servis_istemcisi import api_get
from modules.vardiya_plani.vardiya_motoru import minutes
from ortak.planlama import LEAVE_LABELS,REQUEST_CODES,school_term


SOURCE_KEYS = ("planning_exam_hours", "planning_exclude_early_hours", "planning_languages", "group_hour_targets", "plan_ctx", "plan_ctx_confirmed", "shift_rules", "plan_group_priority",
               "employees_cache", "fixed_shift_records", "trk_requests", "plan_overrides",
               "shift_overrides", "acad_schedules", "acad_exam_calendar", 
               "published_shift_plan", "draft_shift_plan", "plan_removed_assignments")


def fingerprint(state):
    data = {key: state.get(key) for key in SOURCE_KEYS}
    for key in ('employees_cache','fixed_shift_records','trk_requests','plan_overrides','shift_overrides','published_shift_plan','draft_shift_plan','plan_removed_assignments','group_hour_targets'):
        data[key]=state.get(key) or []
    for key in ('acad_schedules','acad_exam_calendar'):data[key]=state.get(key) or {}
    for key in ('planning_exam_hours','planning_exclude_early_hours'):data[key]=bool(state.get(key,False))
    data['planning_languages']={'tr':True,'en':True,'ar':True,**(state.get('planning_languages') or {})}
    data['trk_requests']=sorted(data['trk_requests'],key=lambda r:str(r.get('id','')))
    df = state.get("sp_staffing_result_df")
    data["demand"] = None if df is None else df.to_json(date_format="iso", orient="split")
    return hashlib.sha256(json.dumps(data, default=str, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def fetch_employees(state):
    items, offset = [], 0
    while True:
        res = api_get("/employees/query", token=state.get("auth_token"),
                      params={"position": "agent", "limit": 5000, "offset": offset})
        batch = res.get("items", [])
        items.extend(batch)
        offset += len(batch)
        if offset >= int(res.get("total", 0)):
            break
        if not batch:
            raise ValueError("Personel listesinin tüm sayfaları alınamadı.")
    state["employees_cache"] = validate_employees(items)
    return state["employees_cache"]


def validate_employees(items):
    if not items:
        raise ValueError("Personel listesi boş.")
    ids, users, result = set(), set(), []
    for raw in items:
        row = dict(raw)
        if row.get("position", "agent") != "agent":
            continue
        for field in ("employee_id", "full_name", "work_type"):
            if pd.isna(row.get(field)) or not str(row.get(field, "")).strip():
                raise ValueError(f"Personel listesinde {field} eksik.")
        if row["work_type"] not in {"fulltime", "akademi", "dis_kaynak"}:
            raise ValueError("work_type: fulltime, akademi veya dis_kaynak olmalı.")
        row["employee_id"] = str(row["employee_id"]).strip()
        if row["employee_id"] in ids:
            raise ValueError("Personel kimlikleri benzersiz olmalı.")
        ids.add(row["employee_id"])
        username = str(row.get("username") or "").strip()
        if username and username in users:
            raise ValueError("Kullanıcı adları benzersiz olmalı.")
        if username:
            users.add(username)
        row["username"] = username
        row["position"] = "agent"
        result.append(row)
    if not result:
        raise ValueError("Agent personeli bulunamadı.")
    return result


def collect_inputs(state):
    """Resolve identities exactly. Unsupported/malformed records become blockers."""
    employees = validate_employees(state.get("employees_cache", []))
    included=state.get('planning_languages',{'en':True,'ar':True})
    excluded={str(e['employee_id']) for e in employees if not included.get(e.get('language'),True)}
    excluded.update(e.get('username') for e in employees if str(e['employee_id']) in excluded)
    employees=[e for e in employees if str(e['employee_id']) not in excluded]
    lookup = {str(e["employee_id"]): str(e["employee_id"]) for e in employees}
    for emp in employees:
        if emp.get("username"):
            if emp["username"] in lookup and lookup[emp["username"]] != str(emp["employee_id"]):
                raise ValueError("Kullanıcı adı başka personelin kimliğiyle çakışıyor.")
            lookup[emp["username"]] = str(emp["employee_id"])
    ctx = state["plan_ctx"]
    start, end = pd.Timestamp(ctx["start"]).date(), pd.Timestamp(ctx["end"]).date()
    fixed, issues, unavailable = [], [], {}
    history_start=min([start-timedelta(days=7)]+[pd.Timestamp(t['start']).date() for t in state.get('group_hour_targets',[])])
    history_end=max([end+timedelta(days=7)]+[pd.Timestamp(t['end']).date() for t in state.get('group_hour_targets',[])])

    def problem(raw, reason):
        issues.append({"employee_id": str(raw.get("employee_id", raw.get("created_by", raw.get("employee", "")))),
                       "date": str(raw.get("date", raw.get("start_date", ""))), "Sorun": reason})

    def expand(raw, code, source, identity=None):
        sd = pd.to_datetime(raw.get("date") or raw.get("start_date"), errors="coerce")
        ed = pd.to_datetime(raw.get("date") or raw.get("end_date") or raw.get("start_date"), errors="coerce")
        if pd.isna(sd) or pd.isna(ed) or sd > ed:
            problem(raw, "Kayıt için geçerli başlangıç/bitiş tarihi gerekli")
            return
        if sd.date() > history_end or ed.date() < history_start:
            return
        who = str(identity if identity is not None else raw.get("employee_id", raw.get("created_by", raw.get("employee", ""))))
        if who in excluded:return
        if who not in lookup:
            problem(raw, "Kayıt personelle eşleştirilemedi; kullanıcı adı/employee_id gerekli")
            return
        for d in pd.date_range(max(sd.date(), history_start), min(ed.date(), history_end)):
            fixed.append({"employee_id": lookup[who], "date": d.date().isoformat(),
                          "shift_code": code, "source": source, "note": raw.get("note", ""),"attendance_adjusted":bool(raw.get("attendance_adjusted",False)),
                          "start": raw.get("start") or raw.get("start_time") or raw.get("overtime_start"),
                          "end": raw.get("end") or raw.get("end_time") or raw.get("overtime_end")})

    # First priority: externally entered night shifts and annual leave.
    for row in state.get("fixed_shift_records", []):
        expand(row, row.get("shift_code"), "fixed_external")
    suppressed={tuple(map(str,k)) for k in state.get('plan_removed_assignments',[])}
    draft_manual_keys={(str(r.get('employee_id')),str(r.get('date'))) for r in state.get('draft_shift_plan',[])
                       if r.get('source','manual') in {'manual','manual_single','manual_template'}}
    for row in state.get('published_shift_plan',[]):
        # Registry/request snapshots are refreshed from their original source;
        # legacy/manual published night and leave records are also imported.
        if (row.get('shift_code') in ({'GECE'}|set(LEAVE_LABELS)) and row.get('source') not in {'fixed_external','approved_request'}
                and (str(row.get('employee_id')),str(row.get('date'))) not in suppressed|draft_manual_keys):
            expand(row,row['shift_code'],'published_fixed')
    for row in state.get("shift_overrides", []):
        if row.get("override_type") in ({'GECE'}|set(LEAVE_LABELS)):
            expand(row, row["override_type"], "fixed_external")
    manual_sources = {"manual_template", "manual_single", "manual"}
    for row in state.get("draft_shift_plan", []):
        if row.get("source", "manual") in manual_sources and row.get("shift_code") in ({'GECE'}|set(LEAVE_LABELS)):
            expand(row, row["shift_code"], row.get("source", "manual"))

    # Request archive preserves the full approved snapshot; latest decision wins.
    requests = {str(r.get("id")): dict(r) for r in state.get("trk_requests", [])}
    for archived in state.get("plan_overrides", []):
        key = str(archived.get("request_id"))
        raw = dict(requests.get(key) or archived.get("request") or archived)
        raw.update(status=archived.get("result"), queue="Closed")
        requests[key] = raw
    codes=REQUEST_CODES
    for req in requests.values():
        if req.get("status") not in {"Uygulandı", "Onaylandı"} or req.get("queue") in {"TL", "TL_SWAP", "WFM"}:
            continue
        typ = req.get("type")
        if typ in {"Ders Programı", "Sınav Takvimi", "Genel Talep"}:
            continue  # Structured availability below is the source of truth.
        if typ=='Vardiya Değişim Talebi':
            if not req.get('resolved_assignments'):
                problem(req,'Bu eski değişimin iki taraflı vardiya kaydı yok; yeni bir değişim talebiyle saatleri belirleyin')
            for assignment in req.get('resolved_assignments',[]):expand(assignment,assignment['shift_code'],'approved_request')
            continue
        if typ not in codes:
            problem(req, "Onaylı talep otomatik uygulanamıyor; Vardiya Saatleri'nde elle atayıp talebi kapatın")
            continue
        expand(req, codes[typ], "approved_request")

    for row in state.get("shift_overrides", []):
        code = row.get("override_type")
        if code not in ({'GECE'}|set(LEAVE_LABELS)):
            if code not in ({'OFF','SINAV','DERS','MESAI','WORK'}|set(LEAVE_LABELS)):
                problem(row, "Bilinmeyen vardiya override tipi")
            else:
                expand(row, code, "approved_request")
    for row in state.get("draft_shift_plan", []):
        if row.get("source", "manual") in manual_sources and row.get("shift_code") not in ({'GECE'}|set(LEAVE_LABELS)):
            expand(row, row.get("shift_code"), row.get("source", "manual"))

    day_names=['Pazartesi','Salı','Çarşamba','Perşembe','Cuma','Cumartesi','Pazar']
    exam_days={}
    school=state.get('shift_rules',{}).get('school',{})
    from ortak.interval_servisi import calendar_flags
    calendar=calendar_flags(pd.date_range(start,end+timedelta(days=1)))
    holidays={d.date() for d in calendar.index if calendar.loc[d,'Bayram']==1} if school.get('holiday_priority',True) else set()
    summer=set(school.get('summer_months',[6,7,8]))
    for user,terms in (state.get('acad_exam_calendar') or {}).items():
        if user in excluded:continue
        for data in terms.values():
            for row in pd.DataFrame(data).fillna('').to_dict('records'):
                if not any(str(v).strip() for v in row.values()):
                    continue
                exam=pd.to_datetime(row.get('Tarih'),errors='coerce')
                if pd.isna(exam):
                    problem({'employee':user},'Sınav tarihi okunamadı')
                    continue
                if exam.date() in holidays:continue
                if not start<=exam.date()<=end+timedelta(days=1):
                    continue
                if user not in lookup:
                    problem({'employee':user},'Sınav kaydı personelle eşleştirilemedi')
                    continue
                eid=lookup[user];base=datetime.combine(exam.date(),time())
                exam_days.setdefault(eid,set()).add(exam.date())
                finish=base+timedelta(days=1);begin=base
                if state.get('planning_exam_hours'):
                    try:
                        clock=str(row.get('Saat','')).strip();end_clock=str(row.get('Bitiş','')).strip()
                        if '-' in clock and not end_clock:clock,end_clock=clock.split('-',1)
                        if clock and end_clock:
                            a,b=minutes(clock),minutes(end_clock)
                            if b<=a:raise ValueError('Sınav bitişi başlangıçtan sonra olmalı')
                            begin,finish=base+timedelta(minutes=a),base+timedelta(minutes=b)
                    except ValueError:
                        problem({'employee':user,'date':str(exam.date())},'Sınav saati okunamadı; gün tamamen kapalı tutuldu')
                unavailable.setdefault(eid,[]).append((begin,finish))
    for user,terms in (state.get('acad_schedules') or {}).items():
        if user in excluded:continue
        if user not in lookup:
            problem({'employee':user},'Ders programı personelle eşleştirilemedi')
            continue
        eid=lookup[user]
        for day in pd.date_range(start,end+timedelta(days=1)):
            if day.date() in holidays or day.month in summer:continue
            if day.date() in exam_days.get(eid,set()):
                continue
            data=terms.get(school_term(day))
            if data is None:
                continue
            for _,row in pd.DataFrame(data).fillna('').iterrows():
                if not str(row.get(day_names[day.weekday()], '')).strip():
                    continue
                try:
                    a,b=str(row['Saat']).split('-');begin,finish=minutes(a),minutes(b)
                    if finish<=begin:
                        raise ValueError('Ders bitişi başlangıçtan sonra olmalı')
                    base=datetime.combine(day.date(),time())
                    unavailable.setdefault(eid,[]).append((base+timedelta(minutes=begin),base+timedelta(minutes=finish)))
                except (ValueError,KeyError) as exc:
                    problem({'employee':user},f'Ders saati okunamadı: {exc}')

    changed={}
    for name in ('published_shift_plan','draft_shift_plan'):
        for record in state.get(name,[]):
            if record.get('change_id'):changed[(str(record['employee_id']),str(record['date']))]=record
    if changed:
        fixed=[r for r in fixed if (r['employee_id'],r['date']) not in changed]
        for record in changed.values():expand(record,record['shift_code'],'approved_request')

    # Approved/source records supersede old lower-priority manual entries.
    # Keep conflicts between authoritative sources visible for review.
    strong={(r['employee_id'],r['date']) for r in fixed if r.get('source') in {'fixed_external','approved_request','published_fixed'}}
    fixed=[r for r in fixed if r.get('source') not in manual_sources or (r['employee_id'],r['date']) not in strong]

    # Prefer manual draft over published history for the same employee/day.
    hist = {(str(r.get("employee_id")), str(r.get("date"))): dict(r)
            for r in state.get("published_shift_plan", [])}
    hist.update({(str(r.get("employee_id")), str(r.get("date"))): dict(r)
                 for r in state.get("draft_shift_plan", [])})
    return employees, fixed, list(hist.values()), unavailable, issues

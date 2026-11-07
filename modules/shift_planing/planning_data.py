"""Adapters for current session/API sources; engine has no Streamlit dependency."""
from datetime import date, datetime, time, timedelta
import hashlib
import json

import pandas as pd

from core.api_client import api_get
from .engine import minutes


SOURCE_KEYS = ("plan_ctx", "plan_ctx_confirmed", "shift_rules", "plan_group_priority",
               "employees_cache", "fixed_shift_records", "trk_requests", "plan_overrides",
               "shift_overrides", "acad_schedules", "acad_exam_calendar", "planning_class_term",
               "published_shift_plan", "draft_shift_plan")


def fingerprint(state):
    data = {key: state.get(key) for key in SOURCE_KEYS}
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
    lookup = {str(e["employee_id"]): str(e["employee_id"]) for e in employees}
    for emp in employees:
        if emp.get("username"):
            if emp["username"] in lookup and lookup[emp["username"]] != str(emp["employee_id"]):
                raise ValueError("Kullanıcı adı başka personelin kimliğiyle çakışıyor.")
            lookup[emp["username"]] = str(emp["employee_id"])
    ctx = state["plan_ctx"]
    start, end = pd.Timestamp(ctx["start"]).date(), pd.Timestamp(ctx["end"]).date()
    fixed, issues, unavailable = [], [], {}

    def problem(raw, reason):
        issues.append({"employee_id": str(raw.get("employee_id", raw.get("created_by", raw.get("employee", "")))),
                       "date": str(raw.get("date", raw.get("start_date", ""))), "Sorun": reason})

    def expand(raw, code, source, identity=None):
        sd = pd.to_datetime(raw.get("date") or raw.get("start_date"), errors="coerce")
        ed = pd.to_datetime(raw.get("date") or raw.get("end_date") or raw.get("start_date"), errors="coerce")
        if pd.isna(sd) or pd.isna(ed) or sd > ed:
            problem(raw, "Kayıt için geçerli başlangıç/bitiş tarihi gerekli")
            return
        if sd.date() > end + timedelta(days=7) or ed.date() < start - timedelta(days=7):
            return
        who = str(identity if identity is not None else raw.get("employee_id", raw.get("created_by", raw.get("employee", ""))))
        if who not in lookup:
            problem(raw, "Kayıt personelle eşleştirilemedi; kullanıcı adı/employee_id gerekli")
            return
        for d in pd.date_range(max(sd.date(), start-timedelta(days=7)), min(ed.date(), end+timedelta(days=7))):
            fixed.append({"employee_id": lookup[who], "date": d.date().isoformat(),
                          "shift_code": code, "source": source, "note": raw.get("note", ""),
                          "start": raw.get("start") or raw.get("start_time") or raw.get("overtime_start"),
                          "end": raw.get("end") or raw.get("end_time") or raw.get("overtime_end")})

    # First priority: externally entered night shifts and annual leave.
    for row in state.get("fixed_shift_records", []):
        expand(row, row.get("shift_code"), "fixed_external")
    for row in state.get("shift_overrides", []):
        if row.get("override_type") in {"GECE", "YILLIK_IZIN"}:
            expand(row, row["override_type"], "fixed_external")
    manual_sources = {"manual_template", "manual_single", "manual"}
    for row in state.get("draft_shift_plan", []):
        if row.get("source", "manual") in manual_sources and row.get("shift_code") in {"GECE", "YILLIK_IZIN"}:
            expand(row, row["shift_code"], row.get("source", "manual"))

    # Request archive preserves the full approved snapshot; latest decision wins.
    requests = {str(r.get("id")): dict(r) for r in state.get("trk_requests", [])}
    for archived in state.get("plan_overrides", []):
        key = str(archived.get("request_id"))
        raw = dict(requests.get(key) or archived.get("request") or archived)
        raw.update(status=archived.get("result"), queue="Closed")
        requests[key] = raw
    codes = {"Yıllık İzin Talebi": "YILLIK_IZIN", "Gece Vardiyası Talebi": "GECE",
             "Mesai Talebi": "MESAI", "Bayram Talebi": "BAYRAM"}
    for req in requests.values():
        if req.get("status") not in {"Uygulandı", "Onaylandı"} or req.get("queue") in {"TL", "TL_SWAP", "WFM"}:
            continue
        typ = req.get("type")
        if typ in {"Ders Programı", "Sınav Takvimi"}:
            continue  # Structured availability below is the source of truth.
        if typ not in codes:
            problem(req, "Onaylı talep otomatik uygulanamıyor; Vardiya Saatleri'nde elle atayıp talebi kapatın")
            continue
        expand(req, codes[typ], "approved_request")

    for row in state.get("shift_overrides", []):
        code = row.get("override_type")
        if code not in {"GECE", "YILLIK_IZIN"}:
            if code not in {"OFF", "SINAV", "DERS", "BAYRAM", "MESAI", "WORK"}:
                problem(row, "Bilinmeyen vardiya override tipi")
            else:
                expand(row, code, "approved_request")
    for row in state.get("draft_shift_plan", []):
        if row.get("source", "manual") in manual_sources and row.get("shift_code") not in {"GECE", "YILLIK_IZIN"}:
            expand(row, row.get("shift_code"), row.get("source", "manual"))

    day_names = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    selected_term = state.get("planning_class_term")
    for user, terms in (state.get("acad_schedules") or {}).items():
        if user not in lookup:
            problem({"employee": user}, "Ders programı personelle eşleştirilemedi")
            continue
        relevant = {k: v for k, v in terms.items() if str(start.year) in k or str(end.year) in k}
        if relevant and selected_term not in relevant:
            problem({"employee": user}, "Personelin ders dönemi seçili değil; dönem seçimini kontrol edin")
            continue
        data = relevant.get(selected_term)
        if data is None:
            continue
        table = pd.DataFrame(data).fillna("")
        for day in pd.date_range(start, end+timedelta(days=1)):
            for _, row in table.iterrows():
                if not str(row.get(day_names[day.weekday()], "")).strip():
                    continue
                try:
                    a, b = str(row["Saat"]).split("-")
                    begin, finish = minutes(a), minutes(b)
                    if finish <= begin:
                        raise ValueError("Ders bitişi başlangıçtan sonra olmalı")
                    base = datetime.combine(day.date(), time())
                    unavailable.setdefault(lookup[user], []).append((base+timedelta(minutes=begin), base+timedelta(minutes=finish)))
                except (ValueError, KeyError) as exc:
                    problem({"employee": user}, f"Ders saati okunamadı: {exc}")

    # Source has no exam duration/end time. Conservatively reserve the whole day,
    # explicitly shown in the UI rather than guessing a duration.
    for user, terms in (state.get("acad_exam_calendar") or {}).items():
        for data in terms.values():
            for row in pd.DataFrame(data).fillna("").to_dict("records"):
                if not any(str(v).strip() for v in row.values()):
                    continue
                exam = pd.to_datetime(row.get("Tarih"), errors="coerce")
                if pd.isna(exam):
                    problem({"employee": user}, "Sınav tarihi okunamadı")
                    continue
                if not start <= exam.date() <= end+timedelta(days=1):
                    continue
                if user not in lookup:
                    problem({"employee": user}, "Sınav kaydı personelle eşleştirilemedi")
                    continue
                base = datetime.combine(exam.date(), time())
                unavailable.setdefault(lookup[user], []).append((base, base+timedelta(days=1)))

    # Prefer manual draft over published history for the same employee/day.
    hist = {(str(r.get("employee_id")), str(r.get("date"))): dict(r)
            for r in state.get("published_shift_plan", [])}
    hist.update({(str(r.get("employee_id")), str(r.get("date"))): dict(r)
                 for r in state.get("draft_shift_plan", [])})
    return employees, fixed, list(hist.values()), unavailable, issues

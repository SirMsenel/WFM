# modules/all_shifts/_shift_grid.py
import hashlib
import calendar
from datetime import datetime, date, time

import pandas as pd
import streamlit as st


TR_DAY_SHORT = {
    "Monday": "Pzt",
    "Tuesday": "Sal",
    "Wednesday": "Çar",
    "Thursday": "Per",
    "Friday": "Cum",
    "Saturday": "Cmt",
    "Sunday": "Paz",
}


def _stable_seed(*parts: str) -> int:
    raw = "|".join([p or "" for p in parts])
    h = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _parse_hhmm(s: str) -> time:
    hh, mm = s.split(":")
    return time(int(hh), int(mm))


def _hours_between(start_hhmm: str, end_hhmm: str) -> float:
    s = _parse_hhmm(start_hhmm)
    e = _parse_hhmm(end_hhmm)
    sdt = datetime(2000, 1, 1, s.hour, s.minute)
    edt = datetime(2000, 1, 1, e.hour, e.minute)
    return max(0.0, (edt - sdt).total_seconds() / 3600.0)


def gen_month_schedule_for_employee(emp_key: str, year: int, month: int, work_type: str) -> pd.DataFrame:
    seed = _stable_seed(emp_key, f"{year:04d}-{month:02d}", work_type)
    _, last_day = calendar.monthrange(year, month)

    rows = []
    for day in range(1, last_day + 1):
        d = date(year, month, day)
        is_weekend = d.weekday() >= 5

        x = (seed + day * 1103515245 + 12345) & 0x7FFFFFFF
        p = x % 100

        off_threshold = 55 if is_weekend else 12
        if p < off_threshold:
            rows.append({
                "date": d,
                "shift_code": "OFF",
                "start": None,
                "end": None,
                "display": "OFF",
                "hours": 0.0,
            })
            continue

        if work_type == "akademi":
            if p < 45:
                s, e = "09:00", "18:00"
            elif p < 80:
                s, e = "10:00", "19:00"
            else:
                s, e = "12:00", "21:00"
        elif work_type == "dis_kaynak":
            if p < 60:
                s, e = "08:00", "17:00"
            else:
                s, e = "09:00", "18:00"
        else:
            if p < 80:
                s, e = "09:00", "18:00"
            else:
                s, e = "09:00", "17:00"

        rows.append({
            "date": d,
            "shift_code": "WORK",
            "start": s,
            "end": e,
            "display": f"{s}-{e}",
            "hours": _hours_between(s, e),
        })

    return pd.DataFrame(rows)


def build_shift_grid(employees: list[dict], year: int, month: int) -> pd.DataFrame:
    if not employees:
        return pd.DataFrame()

    _, last_day = calendar.monthrange(year, month)
    date_cols = [date(year, month, d) for d in range(1, last_day + 1)]

    rows = []
    for emp in employees:
        emp_key = str(emp.get("employee_id"))
        full_name = emp.get("full_name", "-")
        work_type = emp.get("work_type", "fulltime")

        sch = gen_month_schedule_for_employee(emp_key, year, month, work_type)

        row = {
            "Ad Soyad": full_name,
        }

        for d in date_cols:
            found = sch.loc[sch["date"] == d, "display"]
            row[d] = found.iloc[0] if not found.empty else ""

        rows.append(row)

    grid = pd.DataFrame(rows)

    rename_map = {}
    for d in date_cols:
        eng = d.strftime("%A")
        rename_map[d] = f"{d.day:02d}\n{TR_DAY_SHORT.get(eng, eng[:3])}"

    grid = grid.rename(columns=rename_map)
    return grid


def _cell_style(val):
    v = str(val or "").strip().upper()

    if v == "OFF":
        return "background-color: rgba(255, 193, 7, 0.18); color:#7a5a00; font-weight:700;"
    if "YILLIK" in v or "İZİN" in v:
        return "background-color: rgba(220, 53, 69, 0.16); color:#842029; font-weight:700;"
    if "22:00" in v or "23:00" in v or "00:00" in v or "21:00" in v:
        return "background-color: rgba(111, 66, 193, 0.16); color:#4b2e83; font-weight:700;"
    if "-" in v and ":" in v:
        return "background-color: rgba(13, 110, 253, 0.07);"
    return ""


def render_shift_grid(employees: list[dict], year: int, month: int, title: str = "Vardiya Grid"):
    st.markdown(f"#### {title}")

    if not employees:
        st.info("Kayıt yok.")
        return

    grid = build_shift_grid(employees, year, month)
    if grid.empty:
        st.info("Grid oluşturulamadı.")
        return

    date_columns = [c for c in grid.columns if c not in ["Ad Soyad"]]

    styler = (
        grid.style
        .map(_cell_style, subset=date_columns)
        .set_properties(**{
            "text-align": "center",
            "white-space": "nowrap",
            "font-size": "12px",
        })
        .set_properties(subset=["Ad Soyad"], **{
            "text-align": "left",
            "font-weight": "700",
        })
    )

    st.dataframe(styler, use_container_width=True, hide_index=True)

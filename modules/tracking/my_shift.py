# modules/tracking/my_shift.py
import os
import requests
import hashlib
import calendar
from datetime import datetime, date, time

import pandas as pd
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8001")


# -------------------------
# API helper
# -------------------------
def _api_get(path: str, token: str | None = None, params: dict | None = None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(f"{BACKEND_URL}{path}", params=params, headers=headers, timeout=15)
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail")
        except Exception:
            detail = r.text
        raise RuntimeError(detail)
    return r.json()


# -------------------------
# Profile helpers
# -------------------------
def _profile() -> dict:
    return st.session_state.get("profile") or {}


def _username(p: dict) -> str:
    return (p.get("username") or "unknown").strip()


def _fullname(p: dict) -> str:
    return (p.get("full_name") or _username(p)).strip()


def _role(p: dict) -> str:
    return (p.get("position") or "-").strip()


def _work_type(p: dict) -> str:
    return (p.get("work_type") or "-").strip()


def _team_lead(p: dict) -> str:
    return (p.get("team_lead") or "-").strip()


def _manager(p: dict) -> str:
    return (p.get("manager") or "-").strip()


def _location(p: dict) -> str:
    return (p.get("location") or "-").strip()


def _language(p: dict) -> str:
    return (p.get("language") or "-").strip()


def _is_academy(p: dict) -> bool:
    return _work_type(p).lower() == "akademi"


def _can_pick_employee(p: dict) -> bool:
    return _role(p).lower().strip() != "agent"


# -------------------------
# Deterministic demo schedule
# -------------------------
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
    diff = edt - sdt
    return max(0.0, diff.total_seconds() / 3600.0)


def _overlap_hours(start_hhmm: str, end_hhmm: str, win_start: str, win_end: str) -> float:
    s = _parse_hhmm(start_hhmm)
    e = _parse_hhmm(end_hhmm)
    ws = _parse_hhmm(win_start)

    sdt = datetime(2000, 1, 1, s.hour, s.minute)
    edt = datetime(2000, 1, 1, e.hour, e.minute)
    ws_dt = datetime(2000, 1, 1, ws.hour, ws.minute)

    if win_end == "00:00":
        we_dt = datetime(2000, 1, 2, 0, 0)
    else:
        we = _parse_hhmm(win_end)
        we_dt = datetime(2000, 1, 1, we.hour, we.minute)

    latest_start = max(sdt, ws_dt)
    earliest_end = min(edt, we_dt)
    diff = earliest_end - latest_start
    return max(0.0, diff.total_seconds() / 3600.0)


def _gen_month_schedule(username: str, year: int, month: int, academy: bool) -> pd.DataFrame:
    seed = _stable_seed(username, f"{year:04d}-{month:02d}", "ACA" if academy else "GEN")
    _, last_day = calendar.monthrange(year, month)

    rows = []
    for day in range(1, last_day + 1):
        d = date(year, month, day)
        is_weekend = d.weekday() >= 5

        x = (seed + day * 1103515245 + 12345) & 0x7FFFFFFF
        p = x % 100

        off_threshold = 55 if is_weekend else 12
        if p < off_threshold:
            rows.append({"date": d, "status": "OFF", "start": None, "end": None, "hours": 0.0})
            continue

        if academy:
            if p < 45:
                s, e = "09:00", "18:00"
            elif p < 80:
                s, e = "10:00", "19:00"
            else:
                s, e = "12:00", "21:00"
        else:
            if p < 80:
                s, e = "09:00", "18:00"
            else:
                s, e = "09:00", "17:00"

        rows.append(
            {"date": d, "status": "WORK", "start": s, "end": e, "hours": float(_hours_between(s, e))}
        )

    return pd.DataFrame(rows)


# -------------------------
# UI Styling
# -------------------------
def _inject_css():
    st.markdown(
        """
<style>
.wfm-card{
  border: 1px solid rgba(0,0,0,.08);
  border-radius: 18px;
  padding: 16px 18px;
  background: rgba(255,255,255,.65);
  box-shadow: 0 10px 26px rgba(0,0,0,.06);
}
.wfm-grid{
  display:grid;
  grid-template-columns: 1.7fr 0.9fr 1fr 1fr 1.1fr;
  gap: 12px;
  align-items: start;
}
.wfm-name{ font-size: 20px; font-weight: 800; margin:0; }
.wfm-sub{ font-size: 12px; opacity: .7; margin-top: 4px; }
.wfm-label{ font-size: 12px; opacity: .65; margin-bottom: 6px; }
.wfm-val{ font-size: 14px; font-weight: 750; }
.wfm-pill{
  display:inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  border: 1px solid rgba(0,0,0,.09);
  background: rgba(0,0,0,.03);
  margin-left: 10px;
}

.wfm-kpi-grid-3{
  display:grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 10px;
}
.wfm-kpi-grid-5{
  display:grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-top: 10px;
}
.wfm-kpi{
  border: 1px solid rgba(0,0,0,.07);
  border-radius: 16px;
  padding: 12px 14px;
  background: rgba(255,255,255,.75);
}
.wfm-kpi .k{ font-size: 12px; opacity: .65; margin-bottom: 6px; }
.wfm-kpi .v{ font-size: 22px; font-weight: 850; line-height: 1.1; }
.wfm-kpi .h{ font-size: 12px; opacity: .55; margin-top: 6px; }

.wfm-table-wrap{
  border: 1px solid rgba(0,0,0,.07);
  border-radius: 16px;
  padding: 10px;
  background: rgba(255,255,255,.72);
}
.wfm-section-title{
  font-size: 16px;
  font-weight: 750;
  margin-bottom: 8px;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _kpi_box(label: str, value: str, hint: str = "") -> str:
    return f"""
<div class="wfm-kpi">
  <div class="k">{label}</div>
  <div class="v">{value}</div>
  {f'<div class="h">{hint}</div>' if hint else ''}
</div>
"""


def _person_card(p: dict):
    full_name = _fullname(p)
    username = _username(p)
    role = _role(p)
    work_type = _work_type(p)
    team_lead = _team_lead(p)
    location = _location(p)

    pill = "AKADEMİ" if _is_academy(p) else work_type.upper()

    st.markdown(
        f"""
<div class="wfm-card">
  <div class="wfm-grid">
    <div>
      <p class="wfm-name">{full_name}<span class="wfm-pill">{pill}</span></p>
      <div class="wfm-sub">@{username}</div>
    </div>
    <div>
      <div class="wfm-label">Rol</div>
      <div class="wfm-val">{role}</div>
    </div>
    <div>
      <div class="wfm-label">Lokasyon</div>
      <div class="wfm-val">{location}</div>
    </div>
    <div>
      <div class="wfm-label">Çalışma Biçimi</div>
      <div class="wfm-val">{work_type}</div>
    </div>
    <div>
      <div class="wfm-label">Takım Lideri</div>
      <div class="wfm-val">{team_lead}</div>
    </div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


# -------------------------
# Pickers
# -------------------------
def _period_selector():
    now = datetime.now()
    current_year = now.year
    current_month = now.month

    with st.container(border=True):
        st.markdown("#### 🗓️ Dönem Seçimi")

        c1, c2, c3 = st.columns([1, 1, 1.2])

        with c1:
            year = st.selectbox(
                "Yıl",
                options=list(range(current_year - 2, current_year + 2)),
                index=2,
                key="my_shift_year",
            )

        with c2:
            month = st.selectbox(
                "Ay",
                options=list(range(1, 13)),
                format_func=lambda m: calendar.month_name[m],
                index=current_month - 1,
                key="my_shift_month",
            )

        with c3:
            custom = st.toggle("Özel seçim", value=False, key="my_shift_custom_range")

    first = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    last = date(year, month, last_day)

    if not custom:
        return year, month, first, last

    with st.container(border=True):
        st.markdown("#### 📅 Özel Seçim")
        d1, d2 = st.columns(2)
        with d1:
            start = st.date_input("Başlangıç", value=first, key="my_shift_period_start_custom")
        with d2:
            end = st.date_input("Bitiş", value=last, key="my_shift_period_end_custom")

        if start > end:
            st.error("Başlangıç tarihi bitişten büyük olamaz.")
            return year, month, first, last

    return year, month, start, end


# -------------------------
# KPI & Table
# -------------------------
def _kpis(df: pd.DataFrame, academy: bool):
    total_hours = float(df["hours"].sum())
    work_days = int((df["status"] == "WORK").sum())
    off_days = int((df["status"] == "OFF").sum())

    if academy:
        dense = 0.0
        for _, r in df.iterrows():
            if r["status"] != "WORK":
                continue
            dense += _overlap_hours(r["start"], r["end"], "11:00", "00:00")
        normal = max(0.0, total_hours - dense)

        st.markdown(
            f"""
<div class="wfm-kpi-grid-5">
  {_kpi_box("Toplam Saat", f"{total_hours:.0f}")}
  {_kpi_box("Çalışma Günü", f"{work_days}")}
  {_kpi_box("OFF", f"{off_days}")}
  {_kpi_box("Yoğun Saat (11:00–00:00)", f"{dense:.0f}")}
  {_kpi_box("Normal Saat", f"{normal:.0f}")}
</div>
            """,
            unsafe_allow_html=True,
        )
        return total_hours, dense, normal

    st.markdown(
        f"""
<div class="wfm-kpi-grid-3">
  {_kpi_box("Toplam Saat", f"{total_hours:.0f}")}
  {_kpi_box("Çalışma Günü", f"{work_days}")}
  {_kpi_box("OFF", f"{off_days}")}
</div>
        """,
        unsafe_allow_html=True,
    )
    return total_hours, 0.0, total_hours


def _schedule_table(df: pd.DataFrame):
    st.markdown('<div class="wfm-section-title">📄 Vardiya Tablosu</div>', unsafe_allow_html=True)

    view = df.copy()
    view["date"] = pd.to_datetime(view["date"]).dt.date
    view["day"] = pd.to_datetime(view["date"]).dt.day_name()

    tr_days = {
        "Monday": "Pazartesi",
        "Tuesday": "Salı",
        "Wednesday": "Çarşamba",
        "Thursday": "Perşembe",
        "Friday": "Cuma",
        "Saturday": "Cumartesi",
        "Sunday": "Pazar",
    }
    view["day"] = view["day"].map(tr_days).fillna(view["day"])

    view["date"] = view["date"].astype(str)
    view["status"] = view["status"].replace({"WORK": "Çalışma", "OFF": "OFF"})

    view["hours"] = pd.to_numeric(view["hours"], errors="coerce").fillna(0)

    def _fmt_hours(x):
        return str(int(x)) if float(x).is_integer() else f"{x:.1f}"

    view["hours"] = view["hours"].apply(_fmt_hours)


    show = view[["date", "day", "status", "start", "end", "hours"]].rename(
        columns={
            "date": "Tarih",
            "day": "Gün",
            "status": "Durum",
            "start": "Başlangıç",
            "end": "Bitiş",
            "hours": "Saat",
        }
    )

    styler = show.style.map(
        lambda x: "background-color: rgba(255, 193, 7, 0.15); font-weight:700;" if str(x) == "OFF" else "",
        subset=["Durum"],
    )

    st.markdown('<div class="wfm-table-wrap">', unsafe_allow_html=True)
    st.dataframe(styler, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)


# -------------------------
# Academy Wage UI
# -------------------------
def _academy_wage_ui(total_hours: float, dense_hours: float, normal_hours: float):
    st.markdown("### 💰 Akademi Ücret Hesabı (Örnek)")

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            base_rate = st.number_input("Normal saat ücreti", min_value=0.0, value=100.0, step=5.0, key="acad_base_rate")
        with c2:
            dense_extra = st.number_input("Yoğun saat ekstra", min_value=0.0, value=25.0, step=5.0, key="acad_dense_extra")
        with c3:
            st.caption("Yoğun saat: 11:00–00:00 aralığına denk gelen süre")

    normal_pay = normal_hours * base_rate
    dense_pay = dense_hours * (base_rate + dense_extra)
    total_pay = normal_pay + dense_pay

    st.markdown(
        f"""
<div class="wfm-kpi-grid-3">
  {_kpi_box("Normal Ücret", f"{normal_pay:,.0f}")}
  {_kpi_box("Yoğun Ücret", f"{dense_pay:,.0f}")}
  {_kpi_box("Toplam", f"{total_pay:,.0f}")}
</div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    summary = pd.DataFrame(
        [
            {"Kalem": "Normal Saat", "Saat": round(normal_hours, 2), "Birim Ücret": base_rate, "Tutar": round(normal_pay, 2)},
            {"Kalem": "Yoğun Saat", "Saat": round(dense_hours, 2), "Birim Ücret": base_rate + dense_extra, "Tutar": round(dense_pay, 2)},
            {"Kalem": "Toplam", "Saat": round(total_hours, 2), "Birim Ücret": "-", "Tutar": round(total_pay, 2)},
        ]
    )
    st.dataframe(summary, use_container_width=True, hide_index=True)


# -------------------------
# Employee picker
# -------------------------
def _employee_picker_if_allowed(current_profile: dict) -> dict:
    if not _can_pick_employee(current_profile):
        return current_profile

    with st.container(border=True):
        st.markdown("#### 👥 Personel Seç (Sadece Agent)")
        q = st.text_input("Ara (isim / TL / manager)", key="trk_emp_search", placeholder="örn: ahmet, ayşe, mehmet...")

        token = st.session_state.get("auth_token")
        try:
            res = _api_get(
                "/employees/query",
                token=token,
                params={
                    "search": q or None,
                    "position": "agent",
                    "limit": 50,
                    "offset": 0,
                },
            )
            items = res.get("items", []) or []
        except Exception as e:
            st.error(f"Personel listesi alınamadı: {e}")
            items = []

        if not items:
            st.info("Agent bulunamadı.")
            return current_profile

        def _fmt(emp: dict) -> str:
            return f"{emp.get('full_name','')} | {emp.get('location','')} | {emp.get('work_type','')} | TL: {emp.get('team_lead','-')}"

        selected = st.selectbox("Agent", options=items, format_func=_fmt, key="trk_emp_selected")

    return {
        "username": str(selected.get("employee_id")),
        "employee_id": selected.get("employee_id"),
        "full_name": selected.get("full_name"),
        "position": selected.get("position"),
        "work_type": selected.get("work_type"),
        "team_lead": selected.get("team_lead"),
        "manager": selected.get("manager"),
        "location": selected.get("location"),
        "language": selected.get("language"),
        "is_superuser": True,
    }


# -------------------------
# Main render
# -------------------------
def render():
    current = _profile()
    _inject_css()

    target = _employee_picker_if_allowed(current)

    st.subheader("🧍 Benim Vardiyam")
    _person_card(target)

    academy = _is_academy(target)

    tab1, tab2 = st.tabs(["📅 Vardiya", "🏫 Akademi Ücret"])

    with tab1:
        year, month, start, end = _period_selector()

        df_month = _gen_month_schedule(_username(target), year, month, academy=academy)
        df = df_month[(df_month["date"] >= start) & (df_month["date"] <= end)].copy()

        st.divider()
        total_hours, dense_hours, normal_hours = _kpis(df, academy=academy)
        st.divider()
        _schedule_table(df)

        st.session_state["my_shift_last_totals"] = {
            "total_hours": total_hours,
            "dense_hours": dense_hours,
            "normal_hours": normal_hours,
            "year": year,
            "month": month,
            "start": str(start),
            "end": str(end),
            "academy": academy,
        }

    with tab2:
        totals = st.session_state.get("my_shift_last_totals") or {}
        if not totals.get("academy", False):
            st.warning("Bu sekme sadece **Akademi (work_type=akademi)** kullanıcıları için aktif.")
            return

        with st.container(border=True):
            st.markdown("#### 📌 Seçili Dönem")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.write(f"**Yıl/Ay:** {totals.get('year','-')}/{totals.get('month','-')}")
            with c2:
                st.write(f"**Başlangıç:** {totals.get('start','-')}")
            with c3:
                st.write(f"**Bitiş:** {totals.get('end','-')}")

        st.divider()
        _academy_wage_ui(
            total_hours=float(totals.get("total_hours", 0.0)),
            dense_hours=float(totals.get("dense_hours", 0.0)),
            normal_hours=float(totals.get("normal_hours", 0.0)),
        )

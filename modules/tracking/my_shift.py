# modules/tracking/my_shift.py
import os
import requests
import hashlib
import calendar
from datetime import datetime, date, time, timedelta
from modules.shift_planing.engine import bounds

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
    from core.planning import SHIFT_LABELS
    view["status"]=view["status"].replace(SHIFT_LABELS)

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
def _employee_picker_if_allowed(current_profile):
    if not _can_pick_employee(current_profile):
        st.markdown('#### Personel')
        st.write(_fullname(current_profile));st.caption('Yalnızca kendi vardiyan ve bilgilerin görüntülenir.')
        return current_profile
    from core.personnel import get_people,visible_people
    st.markdown('#### Personel Seç')
    query=st.text_input('Ara (isim / TL / manager)',key='trk_emp_search')
    items=visible_people(current_profile,get_people(st.session_state))
    items=[e for e in items if not query or query.casefold() in ' '.join(str(e.get(k,'')) for k in ['full_name','team_lead','manager','username']).casefold()]
    if not items:st.info('Bu kapsamda personel bulunamadı.');return None
    people={str(e['employee_id']):e for e in items}
    selected=st.selectbox('Personel',list(people),format_func=lambda i:people[i]['full_name'],key='trk_emp_selected_id')
    return people[selected]


def _compact_period():
    from zoneinfo import ZoneInfo
    now=datetime.now(ZoneInfo('Europe/Istanbul')).date()
    first=now.replace(day=1);last=now.replace(day=calendar.monthrange(now.year,now.month)[1])
    selected=st.date_input('Vardiya tarih aralığı',value=(first,last),key='my_shift_range_v2')
    if len(selected)!=2:st.info('Başlangıç ve bitiş tarihini seçin.');return None
    return selected


def render():
    from html import escape
    from core.shift_display import shift_stats,WINDOWS,cell_style
    from core.planning import SHIFT_LABELS
    from core.forecast_service import DAY_NAMES
    current=_profile();_inject_css();st.subheader('🧍 Benim Vardiyam')
    left,right=st.columns([1,1.4])
    with left:target=_employee_picker_if_allowed(current)
    if not target:return
    with right:
        with st.container(border=True):
            st.markdown('#### '+escape(_fullname(target)))
            st.caption(f"{target.get('location') or '—'} · {target.get('work_type') or '—'} · {target.get('language') or '—'}")
            st.write('Takım lideri: '+str(target.get('team_lead') or '—'))
            st.caption('Personel No: '+str(target.get('employee_id')))
    selected=_compact_period()
    if not selected:return
    start,end=selected
    records=[r for r in st.session_state.get('published_shift_plan',[]) if str(r.get('employee_id'))==str(target.get('employee_id')) and str(start-timedelta(days=1))<=str(r.get('date'))<=str(end)]
    if not records:st.info('Bu personel ve tarih aralığı için yayınlanmış vardiya yok.');return
    summary=shift_stats(records,start,end);counts=summary['status_counts']
    cards=[('Toplam saat',f"{summary['total_hours']:.1f}"),('Çalıştığı gün',summary['work_days']),('OFF',summary['off_days']),('Rapor',counts.get('RAPOR',0)),('Yıllık izin',counts.get('YILLIK_IZIN',0)),('Diğer izin',sum(v for k,v in counts.items() if k not in {'OFF','RAPOR','YILLIK_IZIN'}))]
    for col,(label,value) in zip(st.columns(6),cards):
        with col.container(border=True):st.metric(label,value)
    st.markdown('#### Günün Saatlerine Göre Çalışma')
    columns=st.columns(5)
    for col,(name,hint,_,__,bg,fg) in zip(columns,WINDOWS):
        with col:
            st.markdown(f'<div style="background:linear-gradient(135deg,{bg},#fff);border:1px solid {bg};border-radius:20px;padding:20px;text-align:center;color:{fg}"><b>{name}</b><div style="font-size:28px;font-weight:750;margin:8px 0">{summary["parts"][name]:.1f} sa</div><small>{hint}</small></div>',unsafe_allow_html=True)
    with columns[4]:st.markdown(f'<div style="background:linear-gradient(135deg,#2c2554,#5b4b91);border-radius:20px;padding:20px;text-align:center;color:white"><b>Gece adedi</b><div style="font-size:28px;font-weight:750;margin:8px 0">{summary["night_count"]}</div><small>Geceye girilen vardiya</small></div>',unsafe_allow_html=True)
    st.caption('Saatler yalnızca seçili tarih aralığına düşen gerçek süredir. Gece adedi GECE kodlu, 00:00–07:00 arasında başlayan veya gece yarısını aşan vardiyaları sayar; normal 07:00 girişleri sayılmaz.')
    if counts:
        st.caption('Statü günleri: '+' · '.join(f"{SHIFT_LABELS.get(k,k)}: {v}" for k,v in counts.items()))
    st.markdown('### Vardiya Tablosu')
    output=[]
    for r in sorted(records,key=lambda r:r['date']):
        interval=bounds(r)
        hours=0.
        if interval:
            a=max(pd.Timestamp(interval[0]),pd.Timestamp(start));b=min(pd.Timestamp(interval[1]),pd.Timestamp(end)+pd.Timedelta(days=1));hours=max(0.,(b-a).total_seconds()/3600)
            if not hours:continue
        elif str(r['date'])<str(start):continue
        code=r.get('shift_code');label=SHIFT_LABELS.get(code,code)
        if interval and code!='GECE':
            hour=interval[0].hour;part='Sabah' if 8<=hour<13 else 'İkindi' if 13<=hour<17 else 'Akşam' if hour>=17 else 'Gece'
            label+=' · '+part
        output.append({'Tarih':r['date'],'Gün':DAY_NAMES[pd.Timestamp(r['date']).weekday()],'Durum':label,'Başlangıç':r.get('start') or '—','Bitiş':r.get('end') or '—','Saat':round(hours,2)})
    view=pd.DataFrame(output)
    st.dataframe(view.style.map(cell_style,subset=['Durum','Başlangıç','Bitiş']),hide_index=True,use_container_width=True,height=520)
    if _is_academy(target):
        with st.expander('Akademi Ücret Hesabı'):
            dense=0.
            for record in records:
                interval=bounds(record)
                if not interval:continue
                for day in pd.date_range(start,end):
                    a=max(pd.Timestamp(interval[0]),day+pd.Timedelta(hours=11));b=min(pd.Timestamp(interval[1]),day+pd.Timedelta(days=1))
                    if b>a:dense+=(b-a).total_seconds()/3600
            _academy_wage_ui(summary['total_hours'],dense,max(0,summary['total_hours']-dense))

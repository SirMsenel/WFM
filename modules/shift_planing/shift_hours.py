import calendar
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st


# -------------------------------------------------
# STATE
# -------------------------------------------------
def _ensure_state():
    st.session_state.setdefault("shift_templates", _default_shift_templates())
    st.session_state.setdefault("shift_overrides", [])
    st.session_state.setdefault("draft_shift_plan", [])
    st.session_state.setdefault("published_shift_plan", [])

    st.session_state.setdefault("sp_sh_year", datetime.now().year)
    st.session_state.setdefault("sp_sh_month", datetime.now().month)
    st.session_state.setdefault("sp_sh_group", "fulltime")
    st.session_state.setdefault("sp_sh_location", "Tümü")
    st.session_state.setdefault("sp_sh_language", "Tümü")
    st.session_state.setdefault("sp_sh_person_ids", [])
    st.session_state.setdefault("sp_sh_selected_template", None)


# -------------------------------------------------
# DEFAULTS
# -------------------------------------------------
def _default_shift_templates():
    return {
        "fulltime": [
            {"code": "FT_09_18", "label": "09:00-18:00", "start": "09:00", "end": "18:00"},
            {"code": "FT_09_17", "label": "09:00-17:00", "start": "09:00", "end": "17:00"},
            {"code": "OFF", "label": "OFF", "start": None, "end": None},
        ],
        "akademi": [
            {"code": "AK_09_18", "label": "09:00-18:00", "start": "09:00", "end": "18:00"},
            {"code": "AK_10_19", "label": "10:00-19:00", "start": "10:00", "end": "19:00"},
            {"code": "AK_12_21", "label": "12:00-21:00", "start": "12:00", "end": "21:00"},
            {"code": "OFF", "label": "OFF", "start": None, "end": None},
        ],
        "dis_kaynak": [
            {"code": "DK_08_17", "label": "08:00-17:00", "start": "08:00", "end": "17:00"},
            {"code": "DK_09_18", "label": "09:00-18:00", "start": "09:00", "end": "18:00"},
            {"code": "OFF", "label": "OFF", "start": None, "end": None},
        ],
        "yabanci_dil": [
            {"code": "YD_09_18", "label": "09:00-18:00", "start": "09:00", "end": "18:00"},
            {"code": "YD_10_19", "label": "10:00-19:00", "start": "10:00", "end": "19:00"},
            {"code": "YD_12_21", "label": "12:00-21:00", "start": "12:00", "end": "21:00"},
            {"code": "OFF", "label": "OFF", "start": None, "end": None},
        ],
    }


TR_MONTHS = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
]

TR_DAY_SHORT = {
    "Monday": "Pzt",
    "Tuesday": "Sal",
    "Wednesday": "Çar",
    "Thursday": "Per",
    "Friday": "Cum",
    "Saturday": "Cmt",
    "Sunday": "Paz",
}


# -------------------------------------------------
# PROFILE / EMPLOYEES
# -------------------------------------------------
def _profile():
    return st.session_state.get("profile") or {}


def _role():
    return (_profile().get("position") or "").lower().strip()


def _all_agents() -> list[dict]:
    """
    Şimdilik employees listesi yoksa boş döner.
    İleride backend query ile doldurulur.
    Bu iskelette PersonelTakip / my_shift tarafındaki pattern'e uyumlu basit bir kaynak bekleniyor.
    """
    # İleride burayı backend /employees/query ile genişleteceğiz.
    return st.session_state.get("employees_cache", [])


def _fallback_agents_from_requests() -> list[dict]:
    """
    En azından requestlerden görülen kişileri dummy listeye çevirelim.
    """
    seen = {}
    items = st.session_state.get("trk_requests") or []
    for r in items:
        uname = r.get("created_by")
        if not uname:
            continue
        if uname not in seen:
            seen[uname] = {
                "employee_id": uname,
                "full_name": uname,
                "username": uname,
                "work_type": "fulltime",
                "location": "-",
                "language": "tr",
                "team_lead": "-",
            }
    return list(seen.values())


def _get_agents() -> list[dict]:
    items = _all_agents()
    if items:
        return items
    return _fallback_agents_from_requests()


def _filter_agents(group: str, location: str, language: str) -> list[dict]:
    agents = _get_agents()

    out = []
    for a in agents:
        wt = (a.get("work_type") or "").lower().strip()
        lang = (a.get("language") or "").lower().strip()
        loc = (a.get("location") or "").strip()

        ok = True

        if group == "fulltime":
            ok = wt == "fulltime"
        elif group == "akademi":
            ok = wt == "akademi"
        elif group == "dis_kaynak":
            ok = wt == "dis_kaynak"
        elif group == "yabanci_dil":
            ok = lang in {"ar", "en"}

        if ok and location != "Tümü":
            ok = loc == location

        if ok and language != "Tümü":
            ok = lang == language.lower()

        if ok:
            out.append(a)

    return out


# -------------------------------------------------
# DATE HELPERS
# -------------------------------------------------
def _month_days(year: int, month: int) -> list[date]:
    _, last_day = calendar.monthrange(year, month)
    return [date(year, month, d) for d in range(1, last_day + 1)]


def _fmt_day_col(d: date) -> str:
    eng = d.strftime("%A")
    return f"{d.day:02d}\n{TR_DAY_SHORT.get(eng, eng[:3])}"


# -------------------------------------------------
# TEMPLATE / OVERRIDE / DRAFT HELPERS
# -------------------------------------------------
def _get_templates_for_group(group: str) -> list[dict]:
    templates = st.session_state.get("shift_templates") or {}
    return templates.get(group, [])


def _find_template(group: str, code_or_label: str) -> dict | None:
    for t in _get_templates_for_group(group):
        if t.get("code") == code_or_label or t.get("label") == code_or_label:
            return t
    return None


def _draft_rows_for_period(year: int, month: int) -> list[dict]:
    items = st.session_state.get("draft_shift_plan") or []
    out = []
    for r in items:
        try:
            d = datetime.strptime(str(r.get("date")), "%Y-%m-%d").date()
        except Exception:
            continue
        if d.year == year and d.month == month:
            out.append(r)
    return out


def _upsert_draft_shift(row: dict):
    items = st.session_state.get("draft_shift_plan") or []

    replaced = False
    for i, r in enumerate(items):
        if str(r.get("employee_id")) == str(row.get("employee_id")) and str(r.get("date")) == str(row.get("date")):
            items[i] = row
            replaced = True
            break

    if not replaced:
        items.append(row)

    st.session_state["draft_shift_plan"] = items


def _get_display_for_cell(employee_id, day_iso: str) -> str:
    # 1) draft plan
    for r in st.session_state.get("draft_shift_plan") or []:
        if str(r.get("employee_id")) == str(employee_id) and str(r.get("date")) == str(day_iso):
            start = r.get("start")
            end = r.get("end")
            code = (r.get("shift_code") or "").upper()
            if code == "OFF":
                return "OFF"
            if code == "YILLIK_IZIN":
                return "Yıllık İzin"
            if code == "GECE":
                return f"{start or '17:00'}-{end or '00:00'}"
            if code == "MESAI":
                return f"Mesai {start or ''}-{end or ''}".strip()
            if start and end:
                return f"{start}-{end}"
            return code or ""

    # 2) override
    for ov in st.session_state.get("shift_overrides") or []:
        if str(ov.get("employee_id")) != str(employee_id):
            continue
        s = ov.get("start_date")
        e = ov.get("end_date")
        if not s or not e:
            continue
        if s <= day_iso <= e:
            typ = (ov.get("override_type") or "").upper()
            if typ == "YILLIK_IZIN":
                return "Yıllık İzin"
            if typ == "DERS":
                return "Ders"
            if typ == "SINAV":
                return "Sınav"
            if typ == "BAYRAM":
                return "Bayram"
            if typ == "MESAI":
                return f"Mesai {ov.get('start_time') or ''}-{ov.get('end_time') or ''}".strip()
            if typ == "GECE":
                return f"{ov.get('start_time') or '17:00'}-{ov.get('end_time') or '00:00'}"
            if typ == "OFF":
                return "OFF"

    return ""


def _relevant_overrides_for_period(year: int, month: int, selected_emp_ids: list[str]) -> list[dict]:
    out = []
    for ov in st.session_state.get("shift_overrides") or []:
        emp_id = str(ov.get("employee_id"))
        if selected_emp_ids and emp_id not in [str(x) for x in selected_emp_ids]:
            continue

        s = ov.get("start_date")
        if not s:
            continue
        try:
            sd = datetime.strptime(str(s), "%Y-%m-%d").date()
        except Exception:
            continue

        if sd.year == year and sd.month == month:
            out.append(ov)

    return out


# -------------------------------------------------
# UI - FILTERS
# -------------------------------------------------
def _render_period_box():
    with st.container(border=True):
        st.markdown("#### 📅 Dönem")

        c1, c2 = st.columns(2)
        with c1:
            year = st.selectbox("Yıl", options=[datetime.now().year - 1, datetime.now().year, datetime.now().year + 1], key="sp_sh_year")
        with c2:
            month = st.selectbox("Ay", options=list(range(1, 13)), format_func=lambda m: TR_MONTHS[m - 1], key="sp_sh_month")

        st.markdown(
            f"""
            <div style="
                border:1px solid rgba(0,0,0,.08);
                border-radius:14px;
                padding:12px 14px;
                background:rgba(255,255,255,.72);
                margin-top:8px;
            ">
                <div style="font-size:12px; opacity:.65;">Seçili Dönem</div>
                <div style="font-size:20px; font-weight:800;">{TR_MONTHS[month - 1]} {year}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return year, month


def _render_scope_box():
    with st.container(border=True):
        st.markdown("#### 🎯 Kapsam")

        c1, c2, c3 = st.columns(3)
        with c1:
            group = st.selectbox(
                "Grup",
                options=["fulltime", "dis_kaynak", "yabanci_dil", "akademi"],
                format_func=lambda x: {
                    "fulltime": "Full Time",
                    "dis_kaynak": "Dış Kaynak",
                    "yabanci_dil": "Yabancı Dil",
                    "akademi": "Akademi",
                }[x],
                key="sp_sh_group",
            )
        with c2:
            location = st.selectbox(
                "Lokasyon",
                options=["Tümü", "Ankara", "Konya", "Izmir", "Adana", "Diyarbakir", "Istanbul"],
                key="sp_sh_location",
            )
        with c3:
            language = st.selectbox(
                "Dil",
                options=["Tümü", "TR", "AR", "EN"],
                key="sp_sh_language",
            )

    return group, location, language


def _render_person_picker(filtered_agents: list[dict]) -> list[str]:
    with st.container(border=True):
        st.markdown("#### 👥 Personel Seçimi")

        options = filtered_agents
        ids = [str(a.get("employee_id")) for a in options]

        def _fmt(emp):
            return f"{emp.get('full_name','-')}"

        picked = st.multiselect(
            "Personeller",
            options=options,
            default=[],
            format_func=_fmt,
            key="sp_sh_person_multiselect",
        )

        picked_ids = [str(p.get("employee_id")) for p in picked]
        return picked_ids


# -------------------------------------------------
# UI - REQUESTS / NEED / TEMPLATE
# -------------------------------------------------
def _render_need_summary_placeholder():
    with st.container(border=True):
        st.markdown("#### 📊 İhtiyaç Özeti")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Toplam İhtiyaç", "-")
        with c2:
            st.metric("Atanmış Personel", "-")
        with c3:
            st.metric("Açık / Eksik", "-")
        st.caption("Bu blok staffing / ihtiyaç hesap ekranıyla bağlanacak.")


def _render_request_panel(year: int, month: int, selected_emp_ids: list[str]):
    with st.container(border=True):
        st.markdown("#### 📝 Etkileyen Talepler / Override")
        items = _relevant_overrides_for_period(year, month, selected_emp_ids)

        if not items:
            st.info("Seçili dönem için uygulanmış talep / override yok.")
            return

        df = pd.DataFrame(items)
        show = ["employee_id", "start_date", "end_date", "override_type", "start_time", "end_time", "note", "applied_by"]
        for c in show:
            if c not in df.columns:
                df[c] = None
        st.dataframe(df[show], use_container_width=True, hide_index=True)


def _render_template_panel(group: str):
    with st.container(border=True):
        st.markdown("#### ⏱️ Vardiya Şablonları")

        templates = _get_templates_for_group(group)
        if not templates:
            st.warning("Bu grup için tanımlı vardiya şablonu yok.")
            return None

        opts = [t.get("label") for t in templates]
        selected_label = st.radio("Hazır şablon", options=opts, horizontal=True, key=f"sp_template_{group}")
        st.session_state["sp_sh_selected_template"] = selected_label
        return selected_label


# -------------------------------------------------
# ACTIONS
# -------------------------------------------------
def _apply_template_to_selection(year: int, month: int, person_ids: list[str], group: str, selected_label: str):
    if not person_ids:
        st.warning("Önce personel seç.")
        return

    tmpl = _find_template(group, selected_label)
    if not tmpl:
        st.error("Vardiya şablonu bulunamadı.")
        return

    days = _month_days(year, month)
    for emp_id in person_ids:
        for d in days:
            row = {
                "employee_id": emp_id,
                "date": d.isoformat(),
                "group": group,
                "shift_code": tmpl.get("code"),
                "start": tmpl.get("start"),
                "end": tmpl.get("end"),
                "source": "manual_template",
                "note": "",
            }
            _upsert_draft_shift(row)

    st.success("Seçili personele toplu vardiya atandı.")


def _apply_manual_single_day(employee_id: str, target_date: date, group: str, start: str, end: str, code: str, note: str):
    row = {
        "employee_id": employee_id,
        "date": target_date.isoformat(),
        "group": group,
        "shift_code": code,
        "start": start,
        "end": end,
        "source": "manual_single",
        "note": note,
    }
    _upsert_draft_shift(row)
    st.success("Tekil vardiya kaydedildi.")


# -------------------------------------------------
# GRID
# -------------------------------------------------
def _build_draft_grid(filtered_agents: list[dict], year: int, month: int, selected_emp_ids: list[str]) -> pd.DataFrame:
    agents = filtered_agents
    if selected_emp_ids:
        agents = [a for a in filtered_agents if str(a.get("employee_id")) in [str(x) for x in selected_emp_ids]]

    if not agents:
        return pd.DataFrame()

    days = _month_days(year, month)
    rows = []

    for a in agents:
        emp_id = a.get("employee_id")
        row = {"Ad Soyad": a.get("full_name", "-")}

        for d in days:
            row[_fmt_day_col(d)] = _get_display_for_cell(emp_id, d.isoformat())

        rows.append(row)

    return pd.DataFrame(rows)


def _cell_style(val):
    v = str(val or "").strip().upper()

    if v == "OFF":
        return "background-color: rgba(255, 193, 7, 0.18); color:#7a5a00; font-weight:700;"
    if "YILLIK" in v or "İZİN" in v:
        return "background-color: rgba(220, 53, 69, 0.16); color:#842029; font-weight:700;"
    if "DERS" in v:
        return "background-color: rgba(13, 110, 253, 0.12); color:#084298; font-weight:700;"
    if "SINAV" in v:
        return "background-color: rgba(111, 66, 193, 0.16); color:#4b2e83; font-weight:700;"
    if "MESAI" in v:
        return "background-color: rgba(25, 135, 84, 0.16); color:#0f5132; font-weight:700;"
    if "-" in v and ":" in v:
        return "background-color: rgba(0, 0, 0, 0.04);"
    return ""


def _render_draft_grid(grid: pd.DataFrame):
    with st.container(border=True):
        st.markdown("#### 🗂️ Taslak Vardiya Planı")

        if grid.empty:
            st.info("Gösterilecek taslak plan yok.")
            return

        date_cols = [c for c in grid.columns if c != "Ad Soyad"]
        styler = (
            grid.style
            .map(_cell_style, subset=date_cols)
            .set_properties(**{"text-align": "center", "white-space": "nowrap", "font-size": "12px"})
            .set_properties(subset=["Ad Soyad"], **{"text-align": "left", "font-weight": "700"})
        )
        st.dataframe(styler, use_container_width=True, hide_index=True)


# -------------------------------------------------
# MANUAL INPUT
# -------------------------------------------------
def _render_manual_entry(group: str, filtered_agents: list[dict], selected_emp_ids: list[str]):
    with st.container(border=True):
        st.markdown("#### ✍️ Tekil Elle Giriş")

        if not filtered_agents:
            st.info("Önce kapsam filtresine göre personel bulunmalı.")
            return

        candidates = filtered_agents
        if selected_emp_ids:
            candidates = [a for a in filtered_agents if str(a.get("employee_id")) in [str(x) for x in selected_emp_ids]]

        if not candidates:
            st.info("Elle giriş için personel seç.")
            return

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            emp = st.selectbox(
                "Personel",
                options=candidates,
                format_func=lambda x: x.get("full_name", "-"),
                key="sp_manual_emp",
            )
        with c2:
            d = st.date_input("Tarih", value=date.today(), key="sp_manual_date")
        with c3:
            start = st.text_input("Başlangıç", value="09:00", key="sp_manual_start")
        with c4:
            end = st.text_input("Bitiş", value="18:00", key="sp_manual_end")

        c5, c6 = st.columns([1, 3])
        with c5:
            code = st.selectbox("Kod", options=["WORK", "OFF", "YILLIK_IZIN", "GECE", "MESAI"], key="sp_manual_code")
        with c6:
            note = st.text_input("Not", key="sp_manual_note", placeholder="İsteğe bağlı açıklama")

        if st.button("➕ Tekil Girişi Kaydet", use_container_width=True, key="sp_manual_save"):
            stt = None if code in {"OFF", "YILLIK_IZIN"} else start
            ent = None if code in {"OFF", "YILLIK_IZIN"} else end
            _apply_manual_single_day(
                employee_id=str(emp.get("employee_id")),
                target_date=d,
                group=group,
                start=stt,
                end=ent,
                code=code,
                note=note,
            )


# -------------------------------------------------
# MAIN
# -------------------------------------------------
def render():
    _ensure_state()

    st.subheader("⏱️ Vardiya Saatleri")

    year, month = _render_period_box()
    group, location, language = _render_scope_box()

    filtered_agents = _filter_agents(group, location, language)
    selected_emp_ids = _render_person_picker(filtered_agents)

    left, right = st.columns([1.15, 0.85], vertical_alignment="top")

    with left:
        _render_need_summary_placeholder()
        st.divider()
        _render_request_panel(year, month, selected_emp_ids)

    with right:
        selected_template = _render_template_panel(group)

        if st.button("📌 Şablonu Seçili Personele Uygula", use_container_width=True, key="sp_apply_template"):
            if selected_template:
                _apply_template_to_selection(year, month, selected_emp_ids, group, selected_template)
                st.rerun()

        st.divider()
        _render_manual_entry(group, filtered_agents, selected_emp_ids)

    st.divider()

    grid = _build_draft_grid(filtered_agents, year, month, selected_emp_ids)
    _render_draft_grid(grid)
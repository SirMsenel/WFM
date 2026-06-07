# modules/all_shifts/_common.py
import os
import calendar
from datetime import datetime

import requests
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8001")

ACA_LOCS_DEFAULT = ["Ankara", "Konya", "Izmir"]
OUTSOURCE_LOCS_DEFAULT = ["Adana", "Diyarbakir"]
FOREIGN_LANGS = ["ar", "en"]


def api_get(path: str, token: str | None = None, params: dict | None = None):
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


def get_profile() -> dict:
    return st.session_state.get("profile") or {}


def role() -> str:
    return (get_profile().get("position") or "").lower().strip()


def can_edit() -> bool:
    return role() != "agent"


def month_selector_this_year(key_prefix: str = "allshifts") -> tuple[int, int]:
    now = datetime.now()
    year = now.year
    st.session_state.setdefault(f"{key_prefix}_month", now.month)

    st.markdown(
        """
        <style>
        div[data-testid="column"] button[kind="secondary"]{
            min-height: 40px;
            font-weight: 600;
            border-radius: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    TR_MONTHS = [
        "Ocak",
        "Şubat",
        "Mart",
        "Nisan",
        "Mayıs",
        "Haziran",
        "Temmuz",
        "Ağustos",
        "Eylül",
        "Ekim",
        "Kasım",
        "Aralık",
    ]

    st.markdown("#### 📅 Dönem")
    picked = st.session_state[f"{key_prefix}_month"]

    for row in range(2):
        cols = st.columns(6)
        for col in range(6):
            i = row * 6 + col
            m = i + 1
            label = TR_MONTHS[i]

            if m == picked:
                cols[col].markdown(
                    f"""
                    <div style="
                        text-align:center;
                        padding:10px 0;
                        border-radius:10px;
                        background:rgba(0,0,0,0.08);
                        border:1px solid rgba(0,0,0,0.12);
                        font-weight:800;
                        font-size:13px;
                    ">{label}</div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                if cols[col].button(label, use_container_width=True, key=f"{key_prefix}_m_{m}"):
                    st.session_state[f"{key_prefix}_month"] = m
                    st.rerun()

    return year, st.session_state[f"{key_prefix}_month"]




def render_period_card(year: int, month: int):
    month_name = calendar.month_name[month]
    st.markdown(
        f"""
        <div style="
            border:1px solid rgba(0,0,0,0.08);
            border-radius:16px;
            padding:14px 16px;
            background:rgba(255,255,255,0.72);
            box-shadow:0 8px 20px rgba(0,0,0,0.05);
            margin-bottom:12px;
        ">
            <div style="font-size:12px; opacity:.65; margin-bottom:6px;">Seçili Dönem</div>
            <div style="font-size:22px; font-weight:800; line-height:1.2;">{month_name} {year}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def fetch_agents(
    work_type: str | None = None,
    location: str | None = None,
    language: str | None = None,
    search: str | None = None,
    limit: int = 500,
):
    token = st.session_state.get("auth_token")
    params = {
        "position": "agent",
        "work_type": work_type,
        "location": location,
        "language": language,
        "search": search,
        "limit": limit,
        "offset": 0,
    }
    params = {k: v for k, v in params.items() if v not in (None, "")}
    res = api_get("/employees/query", token=token, params=params)
    return res.get("items", []) or []


def get_locations_by_work_type(work_type: str) -> list[str]:
    if work_type == "akademi":
        return ACA_LOCS_DEFAULT
    if work_type == "dis_kaynak":
        return OUTSOURCE_LOCS_DEFAULT
    return []


def render_edit_placeholder(title: str):
    if can_edit():
        with st.container(border=True):
            st.markdown(f"#### ✏️ {title}")
            st.info("Bu alanı bir sonraki aşamada vardiya planı ile çift yönlü entegre edeceğiz.")
    else:
        st.info("Agent: yalnızca görüntüleme.")

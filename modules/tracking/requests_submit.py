import os
import requests
import streamlit as st
from datetime import datetime, date

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8001")


def _ensure_state():
    st.session_state.setdefault("trk_requests", [])


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _profile() -> dict:
    return st.session_state.get("profile") or {}


def _role() -> str:
    return (_profile().get("position") or "").lower().strip()


def _username() -> str:
    return (_profile().get("username") or "unknown").strip()


def _full_name() -> str:
    return (_profile().get("full_name") or _username()).strip()


def _make_req_id(username: str) -> str:
    return f"REQ-{username}-{int(datetime.now().timestamp())}"


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


def _fetch_agents(search: str | None = None, limit: int = 500) -> list[dict]:
    token = st.session_state.get("auth_token")
    params = {"position": "agent", "limit": limit, "offset": 0}
    if search:
        params["search"] = search
    res = _api_get("/employees/query", token=token, params=params)
    return res.get("items", []) or []


def render():
    _ensure_state()

    st.subheader("📝 Talep İlet")

    # Sadece agent kullanabilsin
    if _role() != "agent":
        st.info("Bu ekran sadece agent kullanıcılar için açıktır.")
        return

    st.caption("Talep oluşturma ekranı (demo state).")

    req_type = st.selectbox(
        "Talep tipi",
        [
            "Gece Vardiyası Talebi",
            "Mesai Talebi",
            "Yıllık İzin Talebi",
            "Genel Talep",
            "Vardiya Değişim Talebi",
        ],
        key="trk_req_type_submit",
    )

    note = st.text_area(
        "Not / Açıklama",
        height=90,
        key="trk_req_note_submit",
        placeholder="Kısa açıklama..."
    )

    payload = {
        "id": _make_req_id(_username()),
        "created_at": _now_str(),
        "created_by": _username(),
        "created_by_name": _full_name(),
        "type": req_type,
        "note": (note or "").strip(),
        "status": "Beklemede",
        "queue": "TL",
        "assigned_tls": [],
        "targets": [],
        "start_date": None,
        "end_date": None,
        "overtime_start": None,
        "overtime_end": None,
        "last_action": None,
        "last_action_by": None,
        "last_action_at": None,
    }

    # -------------------------
    # Vardiya Değişim Talebi
    # -------------------------
    if req_type == "Vardiya Değişim Talebi":
        st.markdown("#### 🔁 Vardiya Değişimi")
        change_date = st.date_input("Değişim tarihi", value=date.today(), key="trk_swap_date")

        st.markdown("##### 👥 Değişim yapılacak kişi(ler)")
        q = st.text_input("Personel ara", key="trk_swap_search", placeholder="isim içinde ara...")
        agents = _fetch_agents(search=q or None)

        # Kendisini listeden çıkar
        agents = [a for a in agents if str(a.get("employee_id")) != str(_profile().get("employee_id"))]

        def _fmt(a: dict) -> str:
            return f"{a.get('full_name','')} | {a.get('location','')} | {a.get('work_type','')} | TL: {a.get('team_lead','-')}"

        picked = st.multiselect(
            "Kişiler",
            options=agents,
            format_func=_fmt,
            key="trk_swap_people",
        )

        tls = sorted({(p.get("team_lead") or "").strip() for p in picked if (p.get("team_lead") or "").strip()})
        payload["queue"] = "TL_SWAP"
        payload["assigned_tls"] = tls
        payload["targets"] = [
            {
                "employee_id": p.get("employee_id"),
                "full_name": p.get("full_name"),
                "team_lead": p.get("team_lead"),
                "location": p.get("location"),
                "work_type": p.get("work_type"),
                "language": p.get("language"),
            }
            for p in picked
        ]
        payload["start_date"] = change_date.isoformat()
        payload["end_date"] = change_date.isoformat()

        st.caption("Not: Hedef kişilerden birinin TL’i onaylayıp uygularsa talep kapanır.")

    # -------------------------
    # Diğer talepler
    # -------------------------
    else:
        st.markdown("#### 📅 Tarih Aralığı")
        c1, c2 = st.columns(2)
        with c1:
            start = st.date_input("Başlangıç", value=date.today(), key="trk_req_start")
        with c2:
            end = st.date_input("Bitiş", value=date.today(), key="trk_req_end")

        if start > end:
            st.error("Başlangıç tarihi bitişten büyük olamaz.")
            return

        payload["start_date"] = start.isoformat()
        payload["end_date"] = end.isoformat()

        if req_type == "Mesai Talebi":
            st.markdown("#### ⏱️ Talep Edilen Mesai Aralığı")
            cc1, cc2 = st.columns(2)
            with cc1:
                ot_s = st.text_input("Mesai başlangıç (HH:MM)", value="18:00", key="trk_ot_s")
            with cc2:
                ot_e = st.text_input("Mesai bitiş (HH:MM)", value="20:00", key="trk_ot_e")

            payload["overtime_start"] = (ot_s or "").strip()
            payload["overtime_end"] = (ot_e or "").strip()

    # -------------------------
    # Gönder
    # -------------------------
    if st.button("📨 Talep Gönder", use_container_width=True, key="trk_req_send_submit"):
        if payload["queue"] == "TL":
            tl_name = (_profile().get("team_lead") or "").strip()
            if tl_name:
                payload["assigned_tls"] = [tl_name]

        st.session_state["trk_requests"].append(payload)
        st.success("Talep oluşturuldu ve kuyruğa alındı (demo).")
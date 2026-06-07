import streamlit as st
import pandas as pd
from datetime import datetime, date


# -------------------------------------------------
# STATE
# -------------------------------------------------
def _ensure_state():
    st.session_state.setdefault("trk_requests", [])
    st.session_state.setdefault("acad_schedules", {})
    st.session_state.setdefault("acad_exam_calendar", {})
    st.session_state.setdefault("acad_bayram_requests", {})
    st.session_state.setdefault("pt_req_pick", None)
    st.session_state.setdefault("pt_action_log", [])


# -------------------------------------------------
# PROFILE
# -------------------------------------------------
def _profile():
    return st.session_state.get("profile") or {}


def _username():
    return (_profile().get("username") or "unknown").strip()


def _full_name():
    return (_profile().get("full_name") or _username()).strip()


def _role():
    return (_profile().get("position") or "").lower().strip()


def _team_lead_name():
    return _full_name().strip()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _today():
    return date.today()


# -------------------------------------------------
# HELPERS
# -------------------------------------------------
def _parse_date(s: str | None):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _is_future(req: dict) -> bool:
    sd = _parse_date(req.get("start_date"))
    return bool(sd and sd > _today())


def _is_direct_tl_applicable(req: dict) -> bool:
    t = (req.get("type") or "").strip()
    return t in {
        "Gece Vardiyası Talebi",
        "Yıllık İzin Talebi",
        "Mesai Talebi",
        "Bayram Talebi",
        "Sınav Takvimi",
        "Ders Programı",
    }


def _safe_df(items: list[dict], cols: list[str]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(items)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


# -------------------------------------------------
# DETAIL TABLE BUILDERS
# -------------------------------------------------
def _load_schedule_table(username: str, ref_term: str | None):
    schedules = st.session_state.get("acad_schedules") or {}
    user_map = schedules.get(username) or {}
    if ref_term and ref_term in user_map:
        try:
            return pd.DataFrame(user_map[ref_term])
        except Exception:
            return None
    return None


def _load_exam_table(username: str, ref_key: str | None):
    exams = st.session_state.get("acad_exam_calendar") or {}
    user_map = exams.get(username) or {}
    if ref_key and ref_key in user_map:
        try:
            return pd.DataFrame(user_map[ref_key])
        except Exception:
            return None
    return None


def _load_bayram_table(username: str, ref_key: str | None):
    bayram = st.session_state.get("acad_bayram_requests") or {}
    user_map = bayram.get(username) or {}
    if ref_key and ref_key in user_map:
        try:
            return pd.DataFrame(user_map[ref_key])
        except Exception:
            return None
    return None


# -------------------------------------------------
# NORMALIZE TRACKING REQUESTS
# -------------------------------------------------
def _normalize_tracking_requests_for_tl() -> list[dict]:
    tl_name = _norm(_team_lead_name())
    items = st.session_state.get("trk_requests") or []

    out = []
    for r in items:
        assigned_tls = [_norm(x) for x in (r.get("assigned_tls") or [])]
        queue = (r.get("queue") or "").strip()

        if queue in {"TL", "TL_SWAP"} and tl_name in assigned_tls:
            out.append(
                {
                    "id": r.get("id"),
                    "source": "tracking",
                    "created_at": r.get("created_at"),
                    "created_by": r.get("created_by"),
                    "type": r.get("type"),
                    "start_date": r.get("start_date"),
                    "end_date": r.get("end_date"),
                    "note": r.get("note"),
                    "status": r.get("status"),
                    "queue": queue,
                    "overtime_start": r.get("overtime_start"),
                    "overtime_end": r.get("overtime_end"),
                    "generated_from": r.get("generated_from"),
                    "generated_ref": r.get("generated_ref"),
                    "raw": r,
                }
            )
    return out


# -------------------------------------------------
# ACTIONS
# -------------------------------------------------
def _log_action(req: dict, result: str, actor: str):
    st.session_state["pt_action_log"].append(
        {
            "request_id": req.get("id"),
            "created_by": req.get("created_by"),
            "type": req.get("type"),
            "result": result,
            "actor": actor,
            "acted_at": _now(),
        }
    )


def _update_request(req_id: str, **updates):
    items = st.session_state.get("trk_requests") or []
    for r in items:
        if r.get("id") == req_id:
            for k, v in updates.items():
                r[k] = v
            break
    st.session_state["trk_requests"] = items


def _tl_apply(req: dict):
    _update_request(
        req.get("id"),
        status="Uygulandı",
        queue="Closed",
        last_action="TL Uyguladı",
        last_action_by=_username(),
        last_action_at=_now(),
    )
    _log_action(req, "TL Uyguladı", _username())


def _forward_to_planning(req: dict):
    _update_request(
        req.get("id"),
        status="Planlamaya İletildi",
        queue="WFM",
        last_action="TL Onayı ile planlamaya gönderildi",
        last_action_by=_username(),
        last_action_at=_now(),
    )
    _log_action(req, "Planlamaya Gönderildi", _username())


def _reject(req: dict):
    _update_request(
        req.get("id"),
        status="Reddedildi",
        queue="Closed",
        last_action="TL Reddetti",
        last_action_by=_username(),
        last_action_at=_now(),
    )
    _log_action(req, "TL Reddetti", _username())


# -------------------------------------------------
# DETAIL RENDER
# -------------------------------------------------
def _render_detail(req: dict):
    with st.container(border=True):
        st.markdown("#### Talep Detayı")
        st.write(f"**Kaynak:** {req.get('source')}")
        st.write(f"**Talep Eden:** {req.get('created_by')}")
        st.write(f"**Tip:** {req.get('type')}")
        st.write(f"**Tarih:** {req.get('start_date')} → {req.get('end_date')}")

        if req.get("type") == "Mesai Talebi":
            st.write(f"**Mesai:** {req.get('overtime_start')} → {req.get('overtime_end')}")

        if req.get("note"):
            st.write(f"**Not:** {req.get('note')}")

    gen_from = req.get("generated_from")
    gen_ref = req.get("generated_ref")
    created_by = req.get("created_by")

    # Ders Programı tablosu
    if req.get("type") == "Ders Programı" and gen_from == "class_schedule" and gen_ref:
        term_key = gen_ref.split("::", 1)[1] if "::" in gen_ref else None
        df = _load_schedule_table(created_by, term_key)
        if df is not None and not df.empty:
            st.markdown("#### Ders Programı Tablosu")
            st.dataframe(df, use_container_width=True, hide_index=True)

    # Sınav Takvimi tablosu
    elif req.get("type") == "Sınav Takvimi" and gen_from == "exam" and gen_ref:
        exam_key = gen_ref.split("::", 1)[1] if "::" in gen_ref else None
        df = _load_exam_table(created_by, exam_key)
        if df is not None and not df.empty:
            st.markdown("#### Sınav Takvimi Tablosu")
            st.dataframe(df, use_container_width=True, hide_index=True)

    # Bayram Talebi tablosu
    elif req.get("type") == "Bayram Talebi" and gen_from == "bayram" and gen_ref:
        bayram_key = gen_ref.split("::", 1)[1] if "::" in gen_ref else None
        df = _load_bayram_table(created_by, bayram_key)
        if df is not None and not df.empty:
            st.markdown("#### Bayram Talebi Tablosu")
            st.dataframe(df, use_container_width=True, hide_index=True)


# -------------------------------------------------
# UI
# -------------------------------------------------
def render():
    _ensure_state()

    st.subheader("👤 Personel Talepleri")

    # Sadece TL
    if _role() != "tl":
        st.info("Bu ekran sadece takım liderleri için açıktır.")
        return

    inbox = _normalize_tracking_requests_for_tl()

    tab1, tab2 = st.tabs(["Bekleyen Talepler", "İşlem Geçmişi"])

    with tab1:
        if not inbox:
            st.info("Bekleyen talep yok.")
        else:
            show = [
                "id",
                "source",
                "created_at",
                "created_by",
                "type",
                "start_date",
                "end_date",
                "status",
                "queue",
                "note",
            ]
            df = _safe_df(inbox, show)
            st.dataframe(df, use_container_width=True, hide_index=True)

            ids = [x.get("id") for x in inbox if x.get("id")]
            if st.session_state.get("pt_req_pick") not in ids:
                st.session_state["pt_req_pick"] = ids[0]

            pick = st.selectbox("Talep seç", ids, key="pt_req_pick")
            req = next((x for x in inbox if x.get("id") == pick), None)

            if req:
                _render_detail(req)

                c1, c2, c3 = st.columns(3)

                with c1:
                    if st.button("✅ Onayla & Uygula", use_container_width=True):
                        if _is_direct_tl_applicable(req) and not _is_future(req):
                            _tl_apply(req)
                            st.success("Talep TL tarafından uygulandı.")
                        else:
                            _forward_to_planning(req)
                            st.success("Talep planlamaya iletildi.")
                        st.rerun()

                with c2:
                    if st.button("↪️ Onayla & Planlamaya Gönder", use_container_width=True):
                        _forward_to_planning(req)
                        st.success("Talep planlamaya iletildi.")
                        st.rerun()

                with c3:
                    if st.button("❌ Reddet", use_container_width=True):
                        _reject(req)
                        st.success("Talep reddedildi.")
                        st.rerun()

    with tab2:
        logs = st.session_state.get("pt_action_log") or []
        if not logs:
            st.info("İşlem geçmişi yok.")
        else:
            st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True)
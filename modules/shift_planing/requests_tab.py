import streamlit as st
import pandas as pd
from datetime import datetime, date


# -------------------------------------------------
# STATE
# -------------------------------------------------
def _ensure_state():
    st.session_state.setdefault("trk_requests", [])
    st.session_state.setdefault("plan_overrides", [])

    st.session_state.setdefault("acad_schedules", {})
    st.session_state.setdefault("acad_exam_calendar", {})
    st.session_state.setdefault("acad_bayram_requests", {})

    st.session_state.setdefault("sp_pending_pick", None)
    st.session_state.setdefault("sp_resolved_pick", None)


def _profile():
    return st.session_state.get("profile") or {}


def _actor():
    return (_profile().get("username") or "unknown").strip()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _today():
    return date.today()


def _parse_date(s: str | None):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


# -------------------------------------------------
# NORMALIZE SOURCES
# -------------------------------------------------
def _normalize_tracking():
    items = st.session_state.get("trk_requests") or []

    pending = []
    resolved = []

    for r in items:
        base = {
            "id": r.get("id"),
            "source": "tracking",
            "created_by": r.get("created_by"),
            "created_at": r.get("created_at"),
            "type": r.get("type"),
            "start_date": r.get("start_date"),
            "end_date": r.get("end_date"),
            "note": r.get("note"),
            "queue": r.get("queue"),
            "status": r.get("status"),
            "overtime_start": r.get("overtime_start"),
            "overtime_end": r.get("overtime_end"),
            "last_action_by": r.get("last_action_by"),
            "last_action_at": r.get("last_action_at"),
        }

        queue = (r.get("queue") or "").strip()
        status = (r.get("status") or "").strip()

        # Planlamaya gelmiş ve bekleyen
        if queue == "WFM":
            pending.append(base)
            continue

        # Çözümlenmiş
        if queue == "Closed" or status in {"Uygulandı", "Reddedildi", "Onaylandı"}:
            resolved.append(base)
            continue

        # Geleceği etkileyen ama henüz WFM'e düşmemiş tracking kayıtları da bekleyene alınabilir
        sd = _parse_date(r.get("start_date"))
        if sd and sd > _today():
            pending.append(base)

    return pending, resolved


def _normalize_academy():
    pending = []

    # Bayram talepleri
    bayram = st.session_state.get("acad_bayram_requests") or {}
    for user, terms in bayram.items():
        for term, data in terms.items():
            try:
                df = pd.DataFrame(data)
            except Exception:
                continue

            for i, row in df.iterrows():
                pending.append(
                    {
                        "id": f"BAYRAM-{user}-{term}-{i}",
                        "source": "bayram",
                        "created_by": user,
                        "created_at": None,
                        "type": "Bayram Talebi",
                        "start_date": row.get("Başlangıç"),
                        "end_date": row.get("Bitiş"),
                        "note": row.get("Açıklama"),
                        "queue": "WFM",
                        "status": "Beklemede",
                        "overtime_start": None,
                        "overtime_end": None,
                        "last_action_by": None,
                        "last_action_at": None,
                    }
                )

    # Sınav takvimi
    exams = st.session_state.get("acad_exam_calendar") or {}
    for user, terms in exams.items():
        for term, data in terms.items():
            try:
                df = pd.DataFrame(data)
            except Exception:
                continue

            for i, row in df.iterrows():
                pending.append(
                    {
                        "id": f"EXAM-{user}-{term}-{i}",
                        "source": "exam",
                        "created_by": user,
                        "created_at": None,
                        "type": "Sınav Takvimi",
                        "start_date": row.get("Tarih"),
                        "end_date": row.get("Tarih"),
                        "note": f"{row.get('Ders', '')} | {row.get('Sınav Türü', '')} | {row.get('Not', '')}",
                        "queue": "WFM",
                        "status": "Beklemede",
                        "overtime_start": row.get("Saat"),
                        "overtime_end": None,
                        "last_action_by": None,
                        "last_action_at": None,
                    }
                )

    # Ders programı
    schedules = st.session_state.get("acad_schedules") or {}
    for user, terms in schedules.items():
        for term, data in terms.items():
            try:
                df = pd.DataFrame(data)
            except Exception:
                continue

            filled = df.fillna("").astype(str).apply(lambda col: col.str.strip() != "").sum().sum()
            if filled > 0:
                pending.append(
                    {
                        "id": f"CLASS-{user}-{term}",
                        "source": "class",
                        "created_by": user,
                        "created_at": None,
                        "type": "Ders Programı",
                        "start_date": None,
                        "end_date": None,
                        "note": f"{term} için ders programı yüklendi",
                        "queue": "WFM",
                        "status": "Beklemede",
                        "overtime_start": None,
                        "overtime_end": None,
                        "last_action_by": None,
                        "last_action_at": None,
                    }
                )

    return pending


# -------------------------------------------------
# ACTIONS
# -------------------------------------------------
def _resolve_request(req: dict, actor: str, result: str):
    """
    result: Uygulandı / Reddedildi
    """
    req_id = req.get("id")
    now = _now()

    # tracking kaynaklı ise ana talebi de güncelle
    items = st.session_state.get("trk_requests") or []
    for r in items:
        if r.get("id") == req_id:
            r["status"] = result
            r["queue"] = "Closed"
            r["last_action_by"] = actor
            r["last_action_at"] = now
            r["last_action"] = "Planlamada sonuçlandı"
            break
    st.session_state["trk_requests"] = items

    # arşiv kaydı
    st.session_state["plan_overrides"].append(
        {
            "request_id": req_id,
            "source": req.get("source"),
            "type": req.get("type"),
            "employee": req.get("created_by"),
            "start_date": req.get("start_date"),
            "end_date": req.get("end_date"),
            "note": req.get("note"),
            "result": result,
            "changed_by": actor,
            "changed_at": now,
        }
    )


# -------------------------------------------------
# UI HELPERS
# -------------------------------------------------
def _safe_df(items: list[dict], cols: list[str]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame(columns=cols)

    df = pd.DataFrame(items)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]


def _pick_request(items: list[dict], key: str, label: str):
    ids = [x.get("id") for x in items if x.get("id")]
    if not ids:
        return None

    if st.session_state.get(key) not in ids:
        st.session_state[key] = ids[0]

    picked = st.selectbox(label, ids, key=key)
    return next((x for x in items if x.get("id") == picked), None)


# -------------------------------------------------
# UI SECTIONS
# -------------------------------------------------
def _section_pending(items: list[dict], actor: str):
    st.markdown("### Bekleyen")

    if not items:
        st.info("Bekleyen talep yok.")
        return

    show = [
        "id",
        "source",
        "created_by",
        "type",
        "start_date",
        "end_date",
        "status",
        "queue",
        "note",
    ]
    df = _safe_df(items, show)
    st.dataframe(df, use_container_width=True, hide_index=True)

    req = _pick_request(items, "sp_pending_pick", "Talep seç")
    if not req:
        return

    with st.container(border=True):
        st.markdown("#### Talep Detayı")
        st.write(f"**Kaynak:** {req.get('source')}")
        st.write(f"**Kullanıcı:** {req.get('created_by')}")
        st.write(f"**Tip:** {req.get('type')}")
        st.write(f"**Tarih:** {req.get('start_date')} → {req.get('end_date')}")
        if req.get("type") == "Mesai Talebi":
            st.write(f"**Mesai:** {req.get('overtime_start')} → {req.get('overtime_end')}")
        st.write(f"**Not:** {req.get('note') or ''}")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Çöz / Uygula", use_container_width=True, key="sp_apply_pending"):
            _resolve_request(req, actor=actor, result="Uygulandı")
            st.success("Talep çözümlendi ve arşive alındı.")
            st.rerun()
    with c2:
        if st.button("❌ Olumsuz Sonuçlandır", use_container_width=True, key="sp_reject_pending"):
            _resolve_request(req, actor=actor, result="Reddedildi")
            st.success("Talep olumsuz sonuçlandırıldı ve arşive alındı.")
            st.rerun()


def _section_resolved(items: list[dict]):
    st.markdown("### Çözümlenen")

    if not items:
        st.info("Çözümlenen talep yok.")
        return

    show = [
        "id",
        "created_at",
        "created_by",
        "type",
        "start_date",
        "end_date",
        "status",
        "note",
        "last_action_at",
        "last_action_by",
    ]
    df = _safe_df(items, show)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _section_archive():
    st.markdown("### Arşiv")

    archive = st.session_state.get("plan_overrides") or []
    if not archive:
        st.info("Arşiv kaydı yok.")
        return

    st.dataframe(pd.DataFrame(archive), use_container_width=True, hide_index=True)


# -------------------------------------------------
# MAIN
# -------------------------------------------------
def render():
    _ensure_state()

    actor = _actor()

    tracking_pending, tracking_resolved = _normalize_tracking()
    academy_pending = _normalize_academy()

    # Bekleyen = planlamaya gelen tracking + akademi kaynakları
    pending = tracking_pending + academy_pending

    tab1, tab2, tab3 = st.tabs(
        [
            "Bekleyen",
            "Çözümlenen",
            "Arşiv",
        ]
    )

    with tab1:
        _section_pending(pending, actor)

    with tab2:
        _section_resolved(tracking_resolved)

    with tab3:
        _section_archive()
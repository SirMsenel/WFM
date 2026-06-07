import streamlit as st
import pandas as pd
from datetime import datetime, date


def _ensure_state():
    st.session_state.setdefault("trk_requests", [])
    st.session_state.setdefault("trk_req_selected_id", None)
    st.session_state.setdefault("trk_req_selected_id_wfm", None)


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


def _employee_id():
    return _profile().get("employee_id")


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _is_direct_type(req: dict) -> bool:
    t = (req.get("type") or "")
    return t in {"Gece Vardiyası Talebi", "Yıllık İzin Talebi", "Mesai Talebi"}


def _is_future(req: dict) -> bool:
    s = req.get("start_date")
    if not s:
        return False
    try:
        sd = datetime.strptime(s, "%Y-%m-%d").date()
        return sd > date.today()
    except Exception:
        return False


def _apply_action(req_id: str, actor: str, action: str, new_status: str, new_queue: str):
    items = st.session_state.get("trk_requests") or []
    for r in items:
        if r.get("id") == req_id:
            r["status"] = new_status
            r["queue"] = new_queue
            r["last_action_by"] = actor
            r["last_action_at"] = _now_str()
            r["last_action"] = action
            break
    st.session_state["trk_requests"] = items


def _safe_selectbox_id(label: str, ids: list[str], key: str) -> str | None:
    if not ids:
        st.session_state[key] = None
        return None

    if st.session_state.get(key) not in ids:
        st.session_state[key] = ids[0]

    return st.selectbox(label, options=ids, key=key)


def _is_related_to_me(req: dict) -> bool:
    """
    Agent kendi taleplerini veya içinde kendi adı/id'si geçen vardiya değişim kayıtlarını görsün.
    """
    if req.get("created_by") == _username():
        return True

    targets = req.get("targets") or []
    my_emp_id = _employee_id()
    my_name = _norm(_full_name())

    for t in targets:
        if my_emp_id is not None and str(t.get("employee_id")) == str(my_emp_id):
            return True
        if _norm(t.get("full_name")) == my_name:
            return True

    return False


def _status_color(val):
    v = str(val or "").strip().lower()

    if "redd" in v:
        return "background-color: rgba(220, 53, 69, 0.18); color: #8b1e2d; font-weight: 700;"
    if "uygul" in v or "onay" in v:
        return "background-color: rgba(25, 135, 84, 0.18); color: #0f5132; font-weight: 700;"
    if "bekle" in v or "iletildi" in v or "geri" in v:
        return "background-color: rgba(255, 193, 7, 0.18); color: #7a5a00; font-weight: 700;"

    return ""


def _queue_color(val):
    v = str(val or "").strip().lower()

    if v == "closed":
        return "background-color: rgba(108, 117, 125, 0.15); color: #495057; font-weight: 700;"
    if v == "wfm":
        return "background-color: rgba(13, 110, 253, 0.15); color: #084298; font-weight: 700;"
    if v in {"tl", "tl_swap"}:
        return "background-color: rgba(255, 193, 7, 0.18); color: #7a5a00; font-weight: 700;"

    return ""


def _beautify_df(df: pd.DataFrame, role_view: str) -> pd.DataFrame:
    out = df.copy()

    col_map = {
        "id": "Talep ID",
        "created_at": "Oluşturulma",
        "created_by": "Oluşturan",
        "type": "Talep Türü",
        "start_date": "Başlangıç",
        "end_date": "Bitiş",
        "status": "Durum",
        "queue": "Kuyruk",
        "note": "Not",
        "last_action": "Son İşlem",
        "last_action_at": "Son İşlem Zamanı",
        "last_action_by": "İşlem Yapan",
    }

    out = out.rename(columns=col_map)

    ordered_cols = [
        "Talep ID",
        "Oluşturulma",
        "Oluşturan",
        "Talep Türü",
        "Başlangıç",
        "Bitiş",
        "Durum",
        "Kuyruk",
        "Not",
        "Son İşlem",
        "Son İşlem Zamanı",
        "İşlem Yapan",
    ]

    existing = [c for c in ordered_cols if c in out.columns]
    return out[existing]


def _render_styled_table(df: pd.DataFrame, role_view: str):
    if df.empty:
        st.info("Kayıt yok.")
        return

    show_df = _beautify_df(df, role_view=role_view)

    styler = show_df.style

    if "Durum" in show_df.columns:
        styler = styler.map(_status_color, subset=["Durum"])

    if "Kuyruk" in show_df.columns:
        styler = styler.map(_queue_color, subset=["Kuyruk"])

    st.dataframe(styler, use_container_width=True, hide_index=True)


def _agent_view():
    st.markdown("### 📌 Taleplerim")
    items = st.session_state.get("trk_requests") or []
    my = [r for r in items if _is_related_to_me(r)]

    if not my:
        st.info("Henüz görüntülenecek talebin yok.")
        return

    df = pd.DataFrame(my)
    show = [
        "id",
        "created_at",
        "created_by",
        "type",
        "start_date",
        "end_date",
        "status",
        "queue",
        "note",
        "last_action",
        "last_action_at",
        "last_action_by",
    ]
    for c in show:
        if c not in df.columns:
            df[c] = None

    _render_styled_table(df[show], role_view="agent")


def _tl_inbox():
    st.markdown("### 📥 TL Talepleri")

    tl_name_norm = _norm(_full_name())

    items = st.session_state.get("trk_requests") or []
    inbox = []
    for r in items:
        q = r.get("queue")
        assigned = r.get("assigned_tls") or []
        assigned_norm = [_norm(x) for x in assigned]

        if q in {"TL", "TL_SWAP"} and tl_name_norm in assigned_norm:
            inbox.append(r)

    if not inbox:
        st.info("TL kuyruğunda talep yok.")
        return

    df = pd.DataFrame(inbox)
    show_cols = [
        "id",
        "created_at",
        "created_by",
        "type",
        "start_date",
        "end_date",
        "status",
        "queue",
        "note",
        "last_action",
        "last_action_at",
        "last_action_by",
    ]
    for c in show_cols:
        if c not in df.columns:
            df[c] = None

    _render_styled_table(df[show_cols], role_view="tl")

    ids = [r.get("id") for r in inbox if r.get("id")]
    selected = _safe_selectbox_id("İşlem yapılacak talep", ids, key="trk_req_selected_id")
    if not selected:
        st.warning("Seçilecek talep bulunamadı.")
        return

    req = next((r for r in inbox if r.get("id") == selected), None)
    if req is None:
        st.warning("Seçilen talep listede bulunamadı. Liste güncellenmiş olabilir.")
        return

    st.divider()
    st.markdown("#### 🧩 Aksiyon")

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("✅ Onayla", use_container_width=True, key="tl_approve"):
            if req.get("type") == "Vardiya Değişim Talebi":
                _apply_action(selected, actor=_username(), action="Onay", new_status="Onaylandı", new_queue="WFM")
                st.success("Onaylandı → Planlamaya iletildi.")
            else:
                _apply_action(selected, actor=_username(), action="Onay", new_status="Onaylandı", new_queue=req.get("queue"))
                st.success("Onaylandı.")
            st.rerun()

    with c2:
        if st.button("🛠️ Uygula (TL)", use_container_width=True, key="tl_apply"):
            if req.get("type") == "Vardiya Değişim Talebi":
                _apply_action(selected, actor=_username(), action="TL Uyguladı", new_status="Uygulandı", new_queue="Closed")
                st.success("Uygulandı ve kapatıldı. (Tek TL uygulaması yeterli)")
                st.rerun()

            if _is_direct_type(req) and not _is_future(req):
                _apply_action(selected, actor=_username(), action="TL Uyguladı", new_status="Uygulandı", new_queue="Closed")
                st.success("TL tarafından uygulandı ve kapatıldı.")
            else:
                _apply_action(selected, actor=_username(), action="Planlamaya iletildi", new_status="Planlamaya iletildi", new_queue="WFM")
                st.success("İleri tarihli / plan gerektiren → WFM kuyruğu.")
            st.rerun()

    with c3:
        if st.button("❌ Reddet", use_container_width=True, key="tl_reject"):
            _apply_action(selected, actor=_username(), action="Red", new_status="Reddedildi", new_queue="Closed")
            st.success("Reddedildi ve kapatıldı.")
            st.rerun()


def _wfm_inbox():
    st.markdown("### 🧾 WFM Kuyruğu (Planlama)")

    items = st.session_state.get("trk_requests") or []
    wfm = [r for r in items if r.get("queue") == "WFM"]

    if not wfm:
        st.info("Planlama kuyruğunda talep yok.")
        return

    df = pd.DataFrame(wfm)
    show_cols = [
        "id",
        "created_at",
        "created_by",
        "type",
        "start_date",
        "end_date",
        "status",
        "queue",
        "note",
        "last_action",
        "last_action_at",
        "last_action_by",
    ]
    for c in show_cols:
        if c not in df.columns:
            df[c] = None

    _render_styled_table(df[show_cols], role_view="wfm")

    ids = [r.get("id") for r in wfm if r.get("id")]
    selected = _safe_selectbox_id("İşlem yapılacak talep", ids, key="trk_req_selected_id_wfm")
    if not selected:
        st.warning("Seçilecek talep bulunamadı.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("✅ Uygula", use_container_width=True, key="wfm_apply"):
            _apply_action(selected, actor=_username(), action="Uygulandı", new_status="Uygulandı", new_queue="Closed")
            st.success("Talep uygulandı ve kapatıldı.")
            st.rerun()
    with c2:
        if st.button("❌ Reddet", use_container_width=True, key="wfm_reject"):
            _apply_action(selected, actor=_username(), action="Red", new_status="Reddedildi", new_queue="Closed")
            st.success("Reddedildi ve kapatıldı.")
            st.rerun()
    with c3:
        if st.button("↩️ TL'e Geri", use_container_width=True, key="wfm_back"):
            _apply_action(selected, actor=_username(), action="TL'e geri", new_status="TL'e geri gönderildi", new_queue="TL")
            st.success("TL kuyruğuna geri gönderildi.")
            st.rerun()


def render():
    _ensure_state()
    st.subheader("📬 Talep Sonuç")
    st.caption("Aktif ve geçmiş talepler.")

    if _role() == "agent":
        _agent_view()
    elif _role() == "tl":
        _tl_inbox()
    else:
        _wfm_inbox()

import streamlit as st
import pandas as pd
from datetime import datetime


# -------------------------------------------------
# STATE
# -------------------------------------------------
def _ensure_state():
    st.session_state.setdefault("acad_schedules", {})
    st.session_state.setdefault("acad_exam_calendar", {})
    st.session_state.setdefault("acad_bayram_requests", {})
    st.session_state.setdefault("trk_requests", [])


# -------------------------------------------------
# PROFILE
# -------------------------------------------------
def _profile():
    return st.session_state.get("profile") or {}


def _username():
    return (_profile().get("username") or "unknown").strip()


def _full_name():
    return (_profile().get("full_name") or _username()).strip()


def _team_lead():
    return (_profile().get("team_lead") or "").strip()


def _work_type():
    return (_profile().get("work_type") or "").strip().lower()


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _make_req_id(prefix: str) -> str:
    return f"{prefix}-{_username()}-{int(datetime.now().timestamp() * 1000)}"


# -------------------------------------------------
# BLANK TABLES
# -------------------------------------------------
def _blank_schedule_df():
    days = ["Saat", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    slots = [
        "08:00-10:00",
        "10:00-12:00",
        "12:00-14:00",
        "14:00-16:00",
        "16:00-18:00",
        "18:00-20:00",
    ]
    return pd.DataFrame([[s, "", "", "", "", "", "", ""] for s in slots], columns=days)


def _blank_exam_df():
    return pd.DataFrame(
        [
            {"Tarih": "", "Saat": "", "Ders": "", "Sınav Türü": "", "Not": ""},
        ]
    )


def _blank_bayram_df():
    return pd.DataFrame(
        [
            {"Başlangıç": "", "Bitiş": "", "Talep Türü": "Bayram İzni", "Açıklama": ""},
        ]
    )


# -------------------------------------------------
# REQUEST HELPERS
# -------------------------------------------------
def _cleanup_generated_requests(source: str, ref_key: str):
    """
    Aynı kayıt tekrar kaydedilince eski otomatik talepleri temizle.
    """
    items = st.session_state.get("trk_requests") or []
    kept = []

    for r in items:
        if r.get("generated_from") == source and r.get("generated_ref") == ref_key:
            continue
        kept.append(r)

    st.session_state["trk_requests"] = kept


def _push_request(
    *,
    req_type: str,
    note: str,
    start_date: str | None,
    end_date: str | None,
    generated_from: str,
    generated_ref: str,
    overtime_start: str | None = None,
    overtime_end: str | None = None,
):
    tl = _team_lead()

    item = {
        "id": _make_req_id(generated_from.upper()),
        "created_at": _now_str(),
        "created_by": _username(),
        "created_by_name": _full_name(),
        "type": req_type,
        "note": (note or "").strip(),
        "status": "Beklemede",
        "queue": "TL",
        "assigned_tls": [tl] if tl else [],
        "targets": [],
        "start_date": start_date,
        "end_date": end_date,
        "overtime_start": overtime_start,
        "overtime_end": overtime_end,
        "last_action": None,
        "last_action_by": None,
        "last_action_at": None,
        "generated_from": generated_from,   # class_schedule / exam / bayram
        "generated_ref": generated_ref,     # unique ref
    }

    st.session_state["trk_requests"].append(item)


def _create_schedule_request(term_key: str, edited: pd.DataFrame):
    """
    Bahar/Güz ders programı kaydından tek bir planlama talebi üret.
    """
    ref = f"{_username()}::{term_key}"
    _cleanup_generated_requests("class_schedule", ref)

    filled = edited.fillna("").astype(str).apply(lambda col: col.str.strip() != "").sum().sum()
    if filled == 0:
        return

    _push_request(
        req_type="Ders Programı",
        note=f"{term_key} dönemine ait ders programı yüklendi. Dolu hücre sayısı: {int(filled)}",
        start_date=None,
        end_date=None,
        generated_from="class_schedule",
        generated_ref=ref,
    )


def _create_bayram_requests(year_key: str, edited: pd.DataFrame):
    ref_prefix = f"{_username()}::{year_key}"
    _cleanup_generated_requests("bayram", ref_prefix)

    for i, row in edited.fillna("").iterrows():
        start = str(row.get("Başlangıç") or "").strip()
        end = str(row.get("Bitiş") or "").strip()
        talep_turu = str(row.get("Talep Türü") or "Bayram Talebi").strip()
        aciklama = str(row.get("Açıklama") or "").strip()

        if not start and not end and not aciklama:
            continue

        _push_request(
            req_type="Bayram Talebi",
            note=f"{talep_turu} | {aciklama}",
            start_date=start or None,
            end_date=end or None,
            generated_from="bayram",
            generated_ref=ref_prefix,
        )


def _create_exam_requests(year_key: str, edited: pd.DataFrame):
    ref_prefix = f"{_username()}::{year_key}"
    _cleanup_generated_requests("exam", ref_prefix)

    for i, row in edited.fillna("").iterrows():
        tarih = str(row.get("Tarih") or "").strip()
        saat = str(row.get("Saat") or "").strip()
        ders = str(row.get("Ders") or "").strip()
        sinav_turu = str(row.get("Sınav Türü") or "").strip()
        not_text = str(row.get("Not") or "").strip()

        if not tarih and not ders and not not_text:
            continue

        _push_request(
            req_type="Sınav Takvimi",
            note=f"{ders} | {sinav_turu} | {not_text}",
            start_date=tarih or None,
            end_date=tarih or None,
            generated_from="exam",
            generated_ref=ref_prefix,
            overtime_start=saat or None,
            overtime_end=None,
        )


# -------------------------------------------------
# MAIN
# -------------------------------------------------
def render():
    _ensure_state()

    st.subheader("📚 Ders Programı")
    if _work_type() != "akademi":
        st.info("Bu ekran sadece **akademi** personelleri için aktif.")
        return

    user = _username()

    col1, col2 = st.columns([1, 1])
    with col1:
        year = st.selectbox("Yıl", options=[2026, 2027, 2028], index=0, key="acad_year")
    with col2:
        st.write("")
        st.write("")
        st.caption("Akademi dönemsel okul planları")

    tab1, tab2, tab3, tab4 = st.tabs([
        "🌱 Bahar",
        "🍂 Güz",
        "🕌 Bayram Talebi",
        "📝 Sınav Takvimi",
    ])

    # -------------------------
    # BAHAR
    # -------------------------
    with tab1:
        st.markdown("#### 🌱 Bahar Dönemi Ders Programı")
        term_key = f"{year}-Bahar"

        saved = st.session_state["acad_schedules"].get(user, {}).get(term_key)
        if saved:
            df = pd.DataFrame(saved)
        else:
            df = _blank_schedule_df()

        edited = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key=f"acad_editor_bahar_{term_key}",
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("💾 Bahar Kaydet", use_container_width=True, key=f"save_bahar_{term_key}"):
                st.session_state["acad_schedules"].setdefault(user, {})
                st.session_state["acad_schedules"][user][term_key] = edited.to_dict(orient="list")

                _create_schedule_request(term_key, edited)

                st.success("Bahar dönemi kaydedildi ve TL onay kuyruğuna gönderildi.")
        with c2:
            if st.button("🧹 Bahar Temizle", use_container_width=True, key=f"clear_bahar_{term_key}"):
                st.session_state["acad_schedules"].setdefault(user, {})
                st.session_state["acad_schedules"][user][term_key] = _blank_schedule_df().to_dict(orient="list")

                _cleanup_generated_requests("class_schedule", f"{_username()}::{term_key}")

                st.success("Bahar dönemi temizlendi.")
                st.rerun()
        with c3:
            st.download_button(
                "⬇️ CSV indir",
                data=edited.to_csv(index=False).encode("utf-8"),
                file_name=f"ders_programi_{user}_{term_key}.csv",
                mime="text/csv",
                use_container_width=True,
                key=f"dl_bahar_{term_key}",
            )

    # -------------------------
    # GÜZ
    # -------------------------
    with tab2:
        st.markdown("#### 🍂 Güz Dönemi Ders Programı")
        term_key = f"{year}-Güz"

        saved = st.session_state["acad_schedules"].get(user, {}).get(term_key)
        if saved:
            df = pd.DataFrame(saved)
        else:
            df = _blank_schedule_df()

        edited = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key=f"acad_editor_guz_{term_key}",
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("💾 Güz Kaydet", use_container_width=True, key=f"save_guz_{term_key}"):
                st.session_state["acad_schedules"].setdefault(user, {})
                st.session_state["acad_schedules"][user][term_key] = edited.to_dict(orient="list")

                _create_schedule_request(term_key, edited)

                st.success("Güz dönemi kaydedildi ve TL onay kuyruğuna gönderildi.")
        with c2:
            if st.button("🧹 Güz Temizle", use_container_width=True, key=f"clear_guz_{term_key}"):
                st.session_state["acad_schedules"].setdefault(user, {})
                st.session_state["acad_schedules"][user][term_key] = _blank_schedule_df().to_dict(orient="list")

                _cleanup_generated_requests("class_schedule", f"{_username()}::{term_key}")

                st.success("Güz dönemi temizlendi.")
                st.rerun()
        with c3:
            st.download_button(
                "⬇️ CSV indir",
                data=edited.to_csv(index=False).encode("utf-8"),
                file_name=f"ders_programi_{user}_{term_key}.csv",
                mime="text/csv",
                use_container_width=True,
                key=f"dl_guz_{term_key}",
            )

    # -------------------------
    # BAYRAM TALEBİ
    # -------------------------
    with tab3:
        st.markdown("#### 🕌 Bayram Talebi")
        bayram_key = f"{year}-Bayram"

        saved = st.session_state["acad_bayram_requests"].get(user, {}).get(bayram_key)
        if saved:
            df = pd.DataFrame(saved)
        else:
            df = _blank_bayram_df()

        edited = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            key=f"acad_bayram_editor_{bayram_key}",
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("💾 Bayram Talebi Kaydet", use_container_width=True, key=f"save_bayram_{bayram_key}"):
                st.session_state["acad_bayram_requests"].setdefault(user, {})
                st.session_state["acad_bayram_requests"][user][bayram_key] = edited.to_dict(orient="list")

                _create_bayram_requests(bayram_key, edited)

                st.success("Bayram talebi kaydedildi ve TL onay kuyruğuna gönderildi.")
        with c2:
            if st.button("🧹 Bayram Talebi Temizle", use_container_width=True, key=f"clear_bayram_{bayram_key}"):
                st.session_state["acad_bayram_requests"].setdefault(user, {})
                st.session_state["acad_bayram_requests"][user][bayram_key] = _blank_bayram_df().to_dict(orient="list")

                _cleanup_generated_requests("bayram", f"{_username()}::{bayram_key}")

                st.success("Bayram talebi temizlendi.")
                st.rerun()
        with c3:
            st.download_button(
                "⬇️ CSV indir",
                data=edited.to_csv(index=False).encode("utf-8"),
                file_name=f"bayram_talebi_{user}_{bayram_key}.csv",
                mime="text/csv",
                use_container_width=True,
                key=f"dl_bayram_{bayram_key}",
            )

    # -------------------------
    # SINAV TAKVİMİ
    # -------------------------
    with tab4:
        st.markdown("#### 📝 Sınav Takvimi")
        exam_key = f"{year}-Sinav"

        saved = st.session_state["acad_exam_calendar"].get(user, {}).get(exam_key)
        if saved:
            df = pd.DataFrame(saved)
        else:
            df = _blank_exam_df()

        edited = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            key=f"acad_exam_editor_{exam_key}",
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("💾 Sınav Takvimi Kaydet", use_container_width=True, key=f"save_exam_{exam_key}"):
                st.session_state["acad_exam_calendar"].setdefault(user, {})
                st.session_state["acad_exam_calendar"][user][exam_key] = edited.to_dict(orient="list")

                _create_exam_requests(exam_key, edited)

                st.success("Sınav takvimi kaydedildi ve TL onay kuyruğuna gönderildi.")
        with c2:
            if st.button("🧹 Sınav Takvimi Temizle", use_container_width=True, key=f"clear_exam_{exam_key}"):
                st.session_state["acad_exam_calendar"].setdefault(user, {})
                st.session_state["acad_exam_calendar"][user][exam_key] = _blank_exam_df().to_dict(orient="list")

                _cleanup_generated_requests("exam", f"{_username()}::{exam_key}")

                st.success("Sınav takvimi temizlendi.")
                st.rerun()
        with c3:
            st.download_button(
                "⬇️ CSV indir",
                data=edited.to_csv(index=False).encode("utf-8"),
                file_name=f"sinav_takvimi_{user}_{exam_key}.csv",
                mime="text/csv",
                use_container_width=True,
                key=f"dl_exam_{exam_key}",
            )
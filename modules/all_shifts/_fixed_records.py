"""Night/annual-leave records consumed before requests and manual assignments."""
from datetime import date
import uuid

import pandas as pd
import streamlit as st

from modules.shift_planing.engine import bounds
from modules.shift_planing.planning_data import fetch_employees


def render_fixed_records(code, year, month):
    state = st.session_state
    records = state.setdefault("fixed_shift_records", [])
    rows = [r for r in records if r.get("shift_code") == code
            and str(r.get("start_date", ""))[:7] <= f"{year}-{month:02d}" <= str(r.get("end_date", ""))[:7]]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    published = [r for r in state.get("published_shift_plan", [])
                 if r.get("shift_code") == code and str(r.get("date", "")).startswith(f"{year}-{month:02d}")]
    if published:
        st.markdown("#### Yayınlanan Plandaki Kayıtlar")
        st.dataframe(published, use_container_width=True, hide_index=True)
    role = (state.get("profile") or {}).get("position")
    if role not in {"wfm", "manager", "moderator"}:
        st.caption("Kayıtlar WFM, yönetici veya moderatör tarafından düzenlenebilir.")
        return
    if st.button("Personel Listesini Al", key=f"fixed_fetch_{code}"):
        try:
            fetch_employees(state)
        except Exception as exc:
            st.error(f"Personeller alınamadı: {exc}")
    employees = state.get("employees_cache", [])
    if not employees:
        st.info("Personelleri al veya Vardiya Planı → Oluştur ekranından personel dosyası yükle.")
        return
    with st.form(f"fixed_form_{code}"):
        ids = [str(e["employee_id"]) for e in employees]
        labels = {str(e["employee_id"]): f"{e.get('full_name', '')} ({e['employee_id']})" for e in employees}
        selected = st.multiselect("Personeller", options=ids, format_func=labels.get)
        dates = st.date_input("Tarih aralığı", value=(date(year, month, 1), date(year, month, 1)))
        start, end = None, None
        if code == "GECE":
            a, b = st.columns(2)
            start = a.text_input("Başlangıç", value=st.session_state.get("shift_rules",{}).get("general",{}).get("night_window_start","00:00"))
            end = b.text_input("Bitiş", value=st.session_state.get("shift_rules",{}).get("general",{}).get("night_window_end","08:00"))
        note = st.text_input("Not")
        save = st.form_submit_button("Planlama İçin Kaydet")
    if save:
        try:
            if not selected or not isinstance(dates, tuple) or len(dates) != 2:
                raise ValueError("Personel ve başlangıç/bitiş tarihini seç.")
            if dates[1] < dates[0] or (dates[1]-dates[0]).days > 366:
                raise ValueError("Tarih aralığı 1–367 gün arasında olmalı.")
            if code == "GECE":
                bounds({"date": str(dates[0]), "shift_code": code, "start": start, "end": end})
            additions = [{"id": uuid.uuid4().hex, "employee_id": eid,
                          "full_name": labels[eid], "start_date": dates[0].isoformat(),
                          "end_date": dates[1].isoformat(), "shift_code": code,
                          "start": start, "end": end, "note": note} for eid in selected]
            state["fixed_shift_records"] = records + additions
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    if rows:
        selected_id = st.selectbox("Silinecek kayıt", [r["id"] for r in rows], key=f"fixed_delete_pick_{code}",
                                  format_func=lambda rid: next(f"{r.get('full_name', r['employee_id'])} | {r['start_date']} → {r['end_date']}" for r in rows if r["id"] == rid))
        if st.button("Seçili Kaydı Sil", key=f"fixed_delete_{code}"):
            state["fixed_shift_records"] = [r for r in records if r["id"] != selected_id]
            st.rerun()
    st.caption("Kayıtlar hazır çalışma alanı veritabanına kaydedilir; otomatik motor bu kayıtları önce yerleştirir. Kural çakışmaları plan kontrolünde gösterilir." if state.get('workspace_db_path') else "Kayıtlar bu oturumda saklanır; otomatik motor bu kayıtları önce yerleştirir.")

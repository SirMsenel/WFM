import streamlit as st
import pandas as pd

from .engine import generate_plan
from .planning_data import collect_inputs, fetch_employees, fingerprint, validate_employees


GROUP_LABELS = {
    "fulltime": "Full Time",
    "akademi": "Akademi",
    "dis_kaynak": "Dış Kaynak",
}


def render_group_priority():
    st.markdown("### Otomatik Planlama Grup Sırası")
    st.caption(
        "Gece vardiyaları, yıllık izinler, onaylanmış talepler ve elle atamalar "
        "yerleştirildikten sonra kalan ihtiyaç için kullanılacak sırayı seç. "
        "Grup sırası, Mesai Kuralları ekranındaki çalışma koşullarını değiştirmez."
    )
    work_types = (st.session_state.get("shift_rules") or {}).get("work_type", {})
    if not work_types:
        st.info("Önce Mevcut Plan → Mesai Kuralları ekranını açarak kuralları tanımla.")
        return

    groups = list(work_types)
    saved = st.session_state.get("plan_group_priority", [])
    order = [group for group in saved if group in groups]
    order += [group for group in groups if group not in order]

    with st.form("plan_group_priority_form"):
        selected = [
            st.selectbox(
                f"{rank + 1}. sırada planlanacak grup",
                options=groups,
                index=groups.index(group),
                format_func=lambda value: GROUP_LABELS.get(value, value),
            )
            for rank, group in enumerate(order)
        ]
        submitted = st.form_submit_button("Grup Sırasını Kaydet")

    if submitted:
        if len(set(selected)) != len(groups):
            st.error("Her grubu yalnızca bir kez seçmelisin. Önceki kayıt korundu.")
        else:
            st.session_state["plan_group_priority"] = selected
            saved = selected
            st.success("Grup sırası kaydedildi.")

    if len(saved) == len(groups) and set(saved) == set(groups):
        st.write("**Kayıtlı sıra:** " + " → ".join(GROUP_LABELS.get(g, g) for g in saved))
    else:
        st.info("Grup sırası henüz kaydedilmedi. Seçimlerini yapıp kaydet.")

    rows = []
    for group in order:
        rule = work_types[group]
        hours = rule.get("shift_total_hours")
        duration = f"{hours} saat" if hours is not None else f"En fazla {rule.get('shift_total_hours_max', '—')} saat"
        rows.append({
            "Grup": GROUP_LABELS.get(group, group),
            "Vardiya süresi": duration,
            "Haftalık gün sınırı": str(rule.get("max_days_per_week", rule.get("max_days_per_week_default", "—"))),
            "Min. dinlenme (saat)": str(rule.get("min_rest_hours", "Tanımlanmamış")),
            "Gece çalışabilir": "Evet" if rule.get("night_allowed") else "Hayır",
            "Grup bitiş sınırı": rule.get("max_end_time", "Genel kurala göre"),
        })
    st.markdown("#### Mevcut Grup Kuralları")
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption("Grup sırası çalışma alanına kaydedilir. Motor ders, sınav ve diğer uygunluk kayıtlarını ayrıca kontrol eder." if st.session_state.get('workspace_db_path') else "Grup sırası bu oturumda saklanır.")


def render():
    st.subheader("Oluştur & Kontrol & Yayınla")
    render_group_priority()
    render_engine()


def render_engine():
    state = st.session_state
    if (state.get("profile") or {}).get("position") not in {"wfm", "manager", "moderator"}:
        st.info("Plan oluşturma ve yayınlama WFM, yönetici ve moderatör rolleri içindir.")
        return
    st.markdown("### Personel Kaynağı")
    if st.button("Personelleri API'den Al / Yenile", key="planning_fetch_employees"):
        try:
            fetch_employees(state)
            st.success("Personeller alındı.")
        except Exception as exc:
            st.error(f"Personeller alınamadı: {exc}")
    upload = st.file_uploader("Alternatif: personel CSV / Excel yükle", type=["csv", "xlsx"], key="planning_employees_file")
    st.caption("Sütunlar: employee_id, full_name, work_type; talepler ve ders kayıtları için username. work_type: fulltime / akademi / dis_kaynak.")
    if upload is not None and st.button("Personel Dosyasını Kullan", key="planning_use_upload"):
        try:
            upload.seek(0)
            table = pd.read_csv(upload, dtype=str) if upload.name.lower().endswith(".csv") else pd.read_excel(upload, dtype=str)
            state["employees_cache"] = validate_employees(table.fillna("").to_dict("records"))
            st.success("Personel dosyası alındı.")
        except Exception as exc:
            st.error(f"Dosya alınamadı: {exc}")
    st.caption(f"Planlamaya hazır personel: {len(state.get('employees_cache', []))}")

    terms = sorted({term for data in (state.get("acad_schedules") or {}).values() for term in data})
    if terms:
        st.selectbox("Planlamada kullanılacak ders dönemi", options=terms, key="planning_class_term")
    st.info("Sınav kayıtlarında bitiş saati bulunmadığı için sınav günü tamamen uygun değil kabul edilir. Derslerin dolu saatleri kapatılır. Mola takvimi henüz tanımlı değil; karşılaştırma shrinkage eklenmiş Planlanan Agent ihtiyacı üzerinden yapılır.")
    st.caption("Otomatik plan, 30 dakikalık açığı azaltan bir dağıtım yapar. Sabit atamalar korunur; soft bitiş sınırları otomatik esnetilmez. Sonuç en iyi olası plan garantisi taşımaz.")
    ctx = state.get("plan_ctx") or {}
    ready = (state.get("plan_ctx_confirmed") and ctx.get("start") and ctx.get("end")
             and state.get("employees_cache") and state.get("plan_group_priority")
             and state.get("shift_rules") and isinstance(state.get("sp_staffing_result_df"), pd.DataFrame))
    if not ready:
        st.info("Plan oluşturmak için dönemi onayla, personel kaynağını ve grup sırasını kaydet, personel ihtiyacını hesapla.")
    else:
        st.write(f"**Plan dönemi:** {ctx['start']} → {ctx['end']}")
    if st.button("Otomatik Vardiya Taslağı Oluştur", disabled=not bool(ready), key="planning_generate"):
        try:
            with st.spinner("Kurallar kontrol ediliyor, vardiyalar yerleştiriliyor..."):
                employees, fixed, history, unavailable, source_issues = collect_inputs(state)
                result = generate_plan(employees, state["sp_staffing_result_df"], state["shift_rules"],
                                       state["plan_group_priority"], ctx["start"], ctx["end"],
                                       fixed=fixed, history=history, unavailable=unavailable)
                result["issues"] = source_issues + result["issues"]
                start, end = str(ctx["start"]), str(ctx["end"])
                outside = [r for r in state.get("draft_shift_plan", []) if not start <= str(r.get("date")) <= end]
                state["draft_shift_plan"] = outside + result["plan"]
                result["period"] = {"start": start, "end": end}
                state["planning_result"] = result
                state["planning_allow_gaps"] = False
                state["planning_result_fingerprint"] = fingerprint(state)
                from core.workspace_store import save_keys
                save_keys(state)
                st.success("Taslak oluşturuldu; Vardiya Saatleri ekranına da aktarıldı.")
        except Exception as exc:
            st.error(f"Plan oluşturulamadı: {exc}")

    result = state.get("planning_result")
    if result is None:
        return
    stale = state.get("planning_result_fingerprint") != fingerprint(state)
    if stale:
        st.warning("Plan girdileri veya elle atamalar değişti. Güncel sonuç ve yayınlama için taslağı yeniden oluştur.")
    coverage = result["coverage"]
    st.markdown("### Plan Kontrolü")
    c1, c2, c3 = st.columns(3)
    total = int(coverage["İhtiyaç"].sum())
    met = total - int(coverage["Eksik"].sum())
    c1.metric("İhtiyaç karşılama", f"%{100*met/total:.1f}" if total else "%100")
    c2.metric("Eksik personel × 30 dk", int(coverage["Eksik"].sum()))
    c3.metric("Fazla personel × 30 dk", int(coverage["Fazla"].sum()))
    st.dataframe(coverage, use_container_width=True, hide_index=True)
    chart = coverage[["Tarih", "Slot", "İhtiyaç", "Atanan"]].copy()
    chart["Zaman"] = pd.to_datetime(chart["Tarih"]) + pd.to_timedelta((chart["Slot"]-1)*30, unit="m")
    st.line_chart(chart.set_index("Zaman")[["İhtiyaç", "Atanan"]])
    roster = pd.DataFrame(result["plan"])
    st.markdown("### Vardiya Taslağı")
    st.dataframe(roster, use_container_width=True, hide_index=True)
    st.download_button("Vardiya CSV İndir", roster.to_csv(index=False).encode("utf-8-sig"), "vardiya_taslagi.csv", "text/csv")
    st.download_button("30 dk İhtiyaç / Atama CSV İndir", coverage.to_csv(index=False).encode("utf-8-sig"), "vardiya_ihtiyac_kontrol.csv", "text/csv")
    if result["issues"]:
        st.error("Çözülmesi gereken kayıt veya kural çakışmaları var. Sabit kayıtlar korundu; sorunlar giderilmeden yayınlanamaz.")
        st.dataframe(result["issues"], use_container_width=True, hide_index=True)
    allow_gaps = False
    if coverage["Eksik"].sum():
        allow_gaps = st.checkbox("Personel açığını gördüm; planı bu açıklarla yayınla", key="planning_allow_gaps")
    blocked = stale or bool(result["issues"]) or (bool(coverage["Eksik"].sum()) and not allow_gaps)
    st.caption("Yayınlanan plan hazır çalışma alanı veritabanına kaydedilir ve diğer hesaplardan görüntülenebilir." if state.get('workspace_db_path') else "Yayınlama bu oturumdaki planı günceller.")
    if st.button("Kontrol Edilen Planı Yayınla", disabled=blocked, key="planning_publish"):
        start, end = result["period"]["start"], result["period"]["end"]
        outside = [r for r in state.get("published_shift_plan", []) if not start <= str(r.get("date")) <= end]
        state["published_shift_plan"] = outside + [dict(row) for row in result["plan"]]
        state["planning_result_fingerprint"] = fingerprint(state)
        from core.workspace_store import save_keys
        save_keys(state)
        st.success("Plan yayınlandı. Tüm Vardiyalar ekranında görüntülenebilir.")

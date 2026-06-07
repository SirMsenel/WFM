# modules/shift_planner/ratio_registry.py
import pandas as pd
import streamlit as st


# ----------------------------
# Render helpers
# ----------------------------
def _render_day_tables(profile_df: pd.DataFrame):
    order = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    df = profile_df.copy()
    df["Gün"] = pd.Categorical(df["Gün"], categories=order, ordered=True)
    df = df.sort_values(["Gün", "Slot"])

    # Daha sade tablo: Gün ismini tekrar etmeyelim (başlık zaten gün)
    day_groups = {
        d: df[df["Gün"] == d][["Aralık", "Oran(%)"]].reset_index(drop=True)
        for d in order
    }

    st.markdown("#### 📋 Gün Bazında Oran Tabloları")
    st.caption("Her gün 48 slot toplamı ~%100 olacak şekilde normalize edilir.")

    top_days = order[:4]
    bot_days = order[4:]

    cols_top = st.columns(4)
    for i, d in enumerate(top_days):
        with cols_top[i]:
            st.markdown(f"**{d}**")
            st.dataframe(
                day_groups[d],
                use_container_width=True,
                hide_index=True,
                height=360,
            )

    cols_bot = st.columns(3)
    for i, d in enumerate(bot_days):
        with cols_bot[i]:
            st.markdown(f"**{d}**")
            st.dataframe(
                day_groups[d],
                use_container_width=True,
                hide_index=True,
                height=360,
            )


def _render_heatmap(profile_df: pd.DataFrame):
    try:
        import plotly.express as px
    except Exception:
        st.info("Plotly yoksa heatmap gösterilemez.")
        return

    order = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    df = profile_df.copy()
    df["Gün"] = pd.Categorical(df["Gün"], categories=order, ordered=True)
    df = df.sort_values(["Gün", "Slot"])

    piv = df.pivot_table(index="Gün", columns="Slot", values="Oran(%)", aggfunc="mean").reindex(order)

    fig = px.imshow(
        piv.values,
        x=list(piv.columns),
        y=list(piv.index),
        aspect="auto",
        labels={"x": "Slot (1-48)", "y": "Gün", "color": "Oran(%)"},
        title="Gün × Slot Oran(%) Isı Haritası",
    )
    fig.update_layout(height=420, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig, use_container_width=True)


def _render_day_line(profile_df: pd.DataFrame, key_prefix: str = "sp_reg_line"):
    try:
        import plotly.express as px
    except Exception:
        st.info("Plotly yoksa çizgi grafiği gösterilemez.")
        return

    order = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

    c1, c2 = st.columns([1.2, 2.8])
    with c1:
        day_pick = st.selectbox("Gün seç", order, index=0, key=f"{key_prefix}_day")
    with c2:
        st.caption("X: Slot (1–48) • Y: Oran(%)")

    dfp = profile_df[profile_df["Gün"] == day_pick].copy().sort_values("Slot")
    fig = px.line(
        dfp,
        x="Slot",
        y="Oran(%)",
        markers=True,
        title=f"{day_pick} — Slot Bazlı Oran(%)",
    )
    fig.update_layout(height=320, margin=dict(l=20, r=20, t=50, b=20))
    fig.update_xaxes(dtick=2)
    st.plotly_chart(fig, use_container_width=True)


def _meta_kpi(meta: dict, pick: str):
    k1, k2, k3, k4 = st.columns([1.6, 1.0, 1.0, 1.0])
    k1.metric("📌 Profil", pick)
    k2.metric("🧼 IQR", "Açık" if meta.get("iqr_used") else "Kapalı")
    k3.metric("⚙️ Yöntem", (meta.get("iqr_mode") or "-").upper())
    rows_after = meta.get("rows_used_after_iqr", 0)
    if isinstance(rows_after, (int, float)):
        k4.metric("📦 Kayıt", f"{int(rows_after):,}")
    else:
        k4.metric("📦 Kayıt", str(rows_after))


# ----------------------------
# UI
# ----------------------------
def render():
    st.subheader("🗂️ Kayıt Seçim (Oran Profilleri)")
    st.caption("Kaydettiğin oran profillerini burada seçer, aktif edebilir veya silebilirsin.")
    st.markdown("---")

    profiles = st.session_state.get("sp_ratio_profiles", [])
    if not profiles:
        st.info("Henüz kayıt yok. Önce 'Oran Profili' ekranında profil üretip kaydet.")
        return
    # --- Kayıt listesi (her zaman açık, ilk 5) ---
    st.markdown("### 📚 Kayıtlı Profiller")

    items = []
    for p in profiles:
        meta = p.get("meta", {}) or {}
        items.append({
            "Profil": p.get("name", "-"),
            "Oluşturma": p.get("created_at", "-"),
            "IQR": "Açık" if meta.get("iqr_used") else "Kapalı",
            "Yöntem": (meta.get("iqr_mode") or "-").upper(),
            "Kayıt (sonra)": meta.get("rows_used_after_iqr", "-"),
        })

    df_items = pd.DataFrame(items)

    # ilk 5 göster (daha fazlası varsa kullanıcı aşağı kaydırıp bakabilir)
    st.dataframe(df_items.head(10), use_container_width=True, hide_index=True, height=220)

    st.markdown("---")
    # --- Profil seç + aksiyonlar (hizalı, zıplamasız) ---
    st.markdown("### ✅ Profil Seç ve Yönet")

    names = [p.get("name") for p in profiles]
    active = st.session_state.get("sp_active_ratio_profile_name")

    default_index = names.index(active) if active in names else 0

    # ✅ Mesajları layout bozmayacak placeholder'larda göstereceğiz
    msg_slot = st.empty()

    c_pick, c_act, c_del = st.columns([2.4, 1.0, 1.0], vertical_alignment="bottom")

    with c_pick:
        pick = st.selectbox(
            " ",  # boş label (başlık üstte)
            names,
            index=default_index,
            key="sp_pick_profile",
        )

    sel = next((p for p in profiles if p.get("name") == pick), None)
    if sel is None:
        st.error("Profil bulunamadı.")
        return

    meta = sel.get("meta", {}) or {}
    df = sel.get("profile_df")
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        st.error("Profil verisi bozuk/eksik.")
        return

    with c_act:
        if st.button("⭐ Aktif Yap", use_container_width=True, key="sp_btn_activate"):
            st.session_state["sp_active_ratio_profile_name"] = pick
            st.session_state["sp_active_ratio_profile_df"] = df.copy()
            msg_slot.success("✅ Aktif profil güncellendi.")

    with c_del:
        # ✅ Checkbox yok: Sil'e basınca popover içinde onay al
        pop = st.popover("🗑️ Sil", use_container_width=True)
        with pop:
            st.warning("Bu profil silinecek. Geri alınamaz.")
            if st.button("Evet, sil", use_container_width=True, key="sp_btn_delete_yes"):
                new_profiles = [p for p in profiles if p.get("name") != pick]
                st.session_state["sp_ratio_profiles"] = new_profiles

                if st.session_state.get("sp_active_ratio_profile_name") == pick:
                    st.session_state["sp_active_ratio_profile_name"] = None
                    st.session_state["sp_active_ratio_profile_df"] = None

                msg_slot.success("🗑️ Profil silindi.")
                st.rerun()
    
    st.markdown("---")

    # ----------------------------
    # KPI
    # ----------------------------
    _meta_kpi(meta, pick)

    st.markdown("")

    # ----------------------------
    # Görselleştirme alanı (sekme)
    # ----------------------------
    t1, t2, t3 = st.tabs(["📈 Çizgi (Gün Seç)", "🟧 Heatmap", "📋 Gün Tabloları"])

    with t1:
        _render_day_line(df, key_prefix="sp_registry")

    with t2:
        _render_heatmap(df)

    with t3:
        _render_day_tables(df)
# Mesai Plani / Kayit Secimi — bu ekranın / servisin uygulama kodu.
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
    st.markdown("---")

    profiles = st.session_state.get("sp_ratio_profiles", [])
    if not profiles:
        st.info("Henüz kayıt yok. Önce 'Oran Profili' ekranında profil üretip kaydet.")
        return
    from ortak.profil_yonetimi import manage_profiles
    import hashlib
    active=st.session_state.get('sp_active_ratio_profile_name')
    from html import escape
    selected=[];action=None;activate_name=None
    for offset in range(0,len(profiles),3):
        for column,p in zip(st.columns(3),profiles[offset:offset+3]):
            with column.container(border=True):
                name=p['name'];ident=hashlib.sha1(name.encode()).hexdigest()[:12]
                color='#158570' if name==active else '#487ca8'
                st.markdown(f'<div style="color:{color};font-weight:750;font-size:18px">{escape(name)}</div><div style="margin:10px 0;color:#64748b">{escape(str(p.get("meta",{}).get("week_start","Genel dağılım")))} · {"● Aktif" if name==active else "Kayıtlı"}</div>',unsafe_allow_html=True)
                if st.checkbox('Seç',key='profile_card_'+ident):selected.append(name)
                if st.button('Aktif Yap',key='profile_activate_'+ident,disabled=name==active,use_container_width=True):activate_name=name
    if st.button('Seçilenleri Sil',key='sp_btn_delete',disabled=not selected):action='delete'
    if activate_name is not None:selected=[activate_name];action='activate'
    if action:
        try:
            manage_profiles(st.session_state,selected,action)
            st.session_state['profile_notice']='Aktif profil güncellendi.' if action=='activate' else 'Seçilen profiller silindi.'
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    if st.session_state.get('profile_notice'):
        st.success(st.session_state.pop('profile_notice'))
    names=[p['name'] for p in profiles]
    pick=selected[0] if len(selected)==1 else active if active in names else names[0]
    sel=next(p for p in profiles if p['name']==pick)
    meta=sel.get('meta',{}) or {};df=sel.get('profile_df')
    if df is None or not isinstance(df,pd.DataFrame) or df.empty:
        st.error('Profil verisi bozuk veya eksik.');return
    st.divider()

    # ----------------------------
    # KPI
    # ----------------------------


    st.markdown("")

    # ----------------------------
    # Görselleştirme alanı (sekme)
    # ----------------------------
    from ortak.gezinme import sections
    sections('nav_ratio_registry',{'Gün Dağılımı':lambda:_render_day_line(df,key_prefix='sp_registry'),
                                  'Isı Haritası':lambda:_render_heatmap(df),'Gün Tabloları':lambda:_render_day_tables(df),'Çağrı Adetleri':lambda:__import__('ortak.dagilim_adetleri',fromlist=['render']).render(df,st.session_state,'profile_counts',expanded=True)})



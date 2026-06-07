import streamlit as st
import pandas as pd
from datetime import date, timedelta


def _week_range(d: date):
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start, end


def _clamp_range(start: date, end: date, min_date: date, max_date: date):
    s = max(start, min_date)
    e = min(end, max_date)
    if s > e:
        s, e = min_date, max_date
    return s, e


def _init_ctx(min_date: date):
    start, end = _week_range(min_date)
    st.session_state.setdefault("plan_ctx", {"start": start, "end": end})
    st.session_state.setdefault("plan_ctx_confirmed", False)


def _load_staffing_df():
    df_all = st.session_state.get("sp_staffing_result_df")
    if df_all is None or not isinstance(df_all, pd.DataFrame) or df_all.empty:
        return None
    df = df_all.copy()
    df["Tarih"] = pd.to_datetime(df["Tarih"]).dt.date
    return df


def render():
    st.subheader("1) Plan Dönem Seçimi")

    df = _load_staffing_df()
    if df is None:
        st.warning("Önce **📅 Mesai Planı → 4) Personel Hesap** adımında hesaplama yapmalısın.")
        return

    all_dates = sorted(df["Tarih"].unique().tolist())
    min_date, max_date = all_dates[0], all_dates[-1]

    _init_ctx(min_date)
    ctx = st.session_state["plan_ctx"]

    tab1, tab2 = st.tabs(["📅 Dönem Seçimi", "📌 Dönem İhtiyaç Özeti"])

    # ---------------- TAB 1: Dönem Seçimi ----------------
    with tab1:
        left, right = st.columns([1.2, 1.0], vertical_alignment="top")

        with left:
            with st.container(border=True):
                st.caption("Bu seçim, vardiya planı sürecinde kullanılacak dönemi belirler.")

                mode = st.radio(
                    "Seçim tipi",
                    ["Haftalık", "Özel Aralık"],
                    horizontal=True,
                    key="vp_period_mode",
                )

                if mode == "Haftalık":
                    anchor = st.selectbox(
                        "Hafta seç (hesaplanan tarihlerden bir gün)",
                        options=all_dates,
                        index=0,
                        format_func=lambda d: str(d),
                        key="vp_week_anchor",
                    )
                    start, end = _week_range(anchor)
                    start, end = _clamp_range(start, end, min_date, max_date)
                    ctx["start"], ctx["end"] = start, end
                    st.success(f"Seçilen hafta: **{start} → {end}**")

                else:
                    start0, end0 = _clamp_range(ctx["start"], ctx["end"], min_date, max_date)
                    d = st.date_input(
                        "Özel tarih aralığı",
                        value=(start0, end0),
                        min_value=min_date,
                        max_value=max_date,
                        key="vp_custom_range",
                    )
                    if isinstance(d, tuple) and len(d) == 2:
                        start, end = _clamp_range(d[0], d[1], min_date, max_date)
                        ctx["start"], ctx["end"] = start, end
                    st.success(f"Seçilen aralık: **{ctx['start']} → {ctx['end']}**")

                st.divider()
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ Dönemi Onayla", use_container_width=True):
                        st.session_state["plan_ctx_confirmed"] = True
                        st.toast("Dönem onaylandı")
                with c2:
                    if st.button("↩️ Onayı Kaldır", use_container_width=True):
                        st.session_state["plan_ctx_confirmed"] = False
                        st.toast("Onay kaldırıldı")

                st.session_state["plan_ctx"] = ctx

        with right:
            with st.container(border=True):
                st.markdown("### ✅ Seçili Context")
                st.write(f"**Hesaplanan aralık:** {min_date} → {max_date}")
                st.write(f"**Seçili dönem:** {ctx['start']} → {ctx['end']}")
                st.write(f"**Durum:** {'Onaylandı' if st.session_state.get('plan_ctx_confirmed') else 'Onay bekliyor'}")

    # ---------------- TAB 2: Dönem İhtiyaç Özeti (Demand) ----------------
    with tab2:
        if not st.session_state.get("plan_ctx_confirmed"):
            st.warning("Önce **📅 Dönem Seçimi** tabında dönemi seçip **✅ Dönemi Onayla** demelisin.")
            return

        start = ctx["start"]
        end = ctx["end"]

        base = df[df["Tarih"].between(start, end)].copy()
        if base.empty:
            st.info("Seçilen dönemde ihtiyaç verisi yok.")
            return

        # ---- Gün seçimi kontrol alanı ----
        period_days = sorted(base["Tarih"].unique().tolist())

        with st.container(border=True):
            st.markdown("### 🗓️ Görüntüleme Gün Seçimi")

            mode = st.radio(
                "Görüntüleme modu",
                ["Tümü (dönem)", "Tek Gün", "Çoklu Gün"],
                horizontal=True,
                key="vp_view_mode",
            )

            if mode == "Tümü (dönem)":
                picked_days = period_days

            elif mode == "Tek Gün":
                d1 = st.selectbox(
                    "Gün seç",
                    options=period_days,
                    index=0,
                    format_func=lambda d: str(d),
                    key="vp_single_day",
                )
                picked_days = [d1]

            else:
                d2 = st.multiselect(
                    "Günleri seç",
                    options=period_days,
                    default=period_days[: min(3, len(period_days))],
                    format_func=lambda d: str(d),
                    key="vp_multi_days",
                )
                picked_days = list(d2) if d2 else []

            if not picked_days:
                st.info("Devam etmek için en az 1 gün seçmelisin.")
                return

            st.caption(f"Seçili gün sayısı: **{len(picked_days)}**")

        # ---- Seçilen günlere göre filtre ----
        dff = base[base["Tarih"].isin(picked_days)].copy()
        dff = dff.sort_values(["Tarih", "Slot"]).copy()

        # KPI
        total_calls = float(dff["Tahmin Çağrı"].sum()) if "Tahmin Çağrı" in dff.columns else 0.0
        peak_agents = int(dff["Planlanan Agent"].max()) if "Planlanan Agent" in dff.columns else 0
        avg_agents = float(dff["Planlanan Agent"].mean()) if "Planlanan Agent" in dff.columns else 0.0

        top = st.columns(3)
        top[0].metric("Toplam Çağrı", f"{total_calls:,.0f}")
        top[1].metric("Peak Agent", f"{peak_agents}")
        top[2].metric("Ort. Agent", f"{avg_agents:.1f}")

        st.markdown("---")

        left, right = st.columns([1.4, 1.0], vertical_alignment="top")

        with right:
            with st.container(border=True):
                st.markdown("### 🔥 Peak Slotlar")
                top_n = st.slider("Top N", 3, 30, 10, 1, key="vp_peak_topn")
                peak_view = dff.sort_values("Planlanan Agent", ascending=False).head(int(top_n))

                peak_cols = ["Tarih", "Aralık", "Planlanan Agent", "Net Agent", "Tahmin Çağrı"]
                peak_cols = [c for c in peak_cols if c in peak_view.columns]
                st.dataframe(peak_view[peak_cols], use_container_width=True, hide_index=True, height=340)

            with st.container(border=True):
                st.markdown("### 📈 Mini Grafik")
                try:
                    import plotly.express as px

                    x = dff["Tarih"].astype(str) + " • " + dff["Aralık"].astype(str)
                    chart_df = pd.DataFrame({"Slot": x, "Planlanan Agent": dff["Planlanan Agent"].values})
                    fig = px.line(chart_df, x="Slot", y="Planlanan Agent", markers=True)
                    fig.update_layout(height=260, margin=dict(l=10, r=10, t=20, b=10))
                    st.plotly_chart(fig, use_container_width=True)
                except Exception:
                    tmp = dff.copy()
                    tmp["SlotLabel"] = tmp["Tarih"].astype(str) + " • " + tmp["Slot"].astype(str)
                    st.line_chart(tmp.set_index("SlotLabel")[["Planlanan Agent"]], height=260)

        with left:
            with st.container(border=True):
                st.markdown("### 📌 İhtiyaç Tablosu (30dk)")

                q = st.text_input(
                    "Ara",
                    value="",
                    placeholder="örn: 2026-03-02 veya 13:00",
                    key="vp_need_search",
                )
                view = dff.copy()
                if q.strip():
                    qq = q.strip().lower()
                    mask = view.astype(str).apply(lambda s: s.str.lower().str.contains(qq, na=False)).any(axis=1)
                    view = view[mask].copy()

                show_cols = [
                    "Tarih", "Gün", "Slot", "Aralık",
                    "Tahmin Çağrı",
                    "Net Agent", "Planlanan Agent",
                    "Doluluk (%)", "SL (model) (%)",
                ]
                show_cols = [c for c in show_cols if c in view.columns]
                st.dataframe(view[show_cols], use_container_width=True, hide_index=True, height=640)
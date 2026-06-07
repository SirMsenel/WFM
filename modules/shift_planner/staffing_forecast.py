import math
import pandas as pd
import streamlit as st


# ==========================================================
# Erlang C Fonksiyonları
# ==========================================================

def erlang_c_probability(a: float, m: int) -> float:
    if m <= 0:
        return 1.0
    if m <= a:
        return 1.0

    sum_terms = 0.0
    for k in range(m):
        sum_terms += (a ** k) / math.factorial(k)

    last_term = (a ** m) / (math.factorial(m) * (1 - (a / m)))
    return float(last_term / (sum_terms + last_term))


def erlang_c_metrics_for_m(
    calls: float,
    aht_sec: float,
    interval_sec: float,
    m: int,
    target_time_sec: float,
) -> tuple[float, float, float]:
    if calls <= 0 or aht_sec <= 0 or interval_sec <= 0:
        return (0.0, 1.0, 0.0)

    arrival_rate = calls / interval_sec
    a = arrival_rate * aht_sec

    if m <= 0:
        return (a, 0.0, 1.0)

    pw = erlang_c_probability(a, m)

    if aht_sec > 0:
        sl = 1 - pw * math.exp(-(m - a) * (target_time_sec / aht_sec))
    else:
        sl = 0.0

    occ = (a / m) if m > 0 else 1.0
    return (float(a), float(sl), float(occ))


def erlang_c_required_agents(
    calls: float,
    aht_sec: float,
    interval_sec: float,
    target_sl: float,
    target_time_sec: float,
    occ_target: float,
) -> dict:
    if calls <= 0:
        return {"m": 0, "traffic_a": 0.0, "sl": 1.0, "occupancy": 0.0}

    arrival_rate = calls / interval_sec
    a = arrival_rate * aht_sec

    m = max(1, int(math.ceil(a)))

    while True:
        traffic_a, sl, occ = erlang_c_metrics_for_m(
            calls=calls,
            aht_sec=aht_sec,
            interval_sec=interval_sec,
            m=m,
            target_time_sec=target_time_sec,
        )

        if (sl >= target_sl) and (occ <= occ_target):
            return {"m": m, "traffic_a": traffic_a, "sl": sl, "occupancy": occ}

        m += 1


# ==========================================================
# UI
# ==========================================================

def render():
    st.subheader("👥 Personel Tahmin (Erlang C)")
    st.caption("Günlük tahmini, 30 dk slot oranlarına dağıtıp Erlang C ile agent ihtiyacını hesaplar.")
    st.markdown("---")

    # Gerekli veriler
    if "cf_forecast_df" not in st.session_state:
        st.warning("Önce Çağrı Tahmini üretmelisin.")
        return

    if "sp_active_ratio_profile_df" not in st.session_state or st.session_state["sp_active_ratio_profile_df"] is None:
        st.warning("Önce aktif bir 30 dk oran profili seçmelisin (Kayıt Seçim ekranından).")
        return

    forecast_df = st.session_state["cf_forecast_df"].copy()
    ratio_df = st.session_state["sp_active_ratio_profile_df"].copy()

    if forecast_df.empty or ratio_df.empty:
        st.error("Tahmin veya oran profili boş.")
        return

    # ======================================================
    # Parametreler
    # ======================================================
    st.markdown("### ⚙️ Parametreler")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        aht = st.slider("AHT (sn)", 60, 600, 300, 10)
    with c2:
        sl_percent = st.slider("Service Level (%)", 50, 95, 80)
    with c3:
        target_time = st.slider("Hedef Süre (sn)", 5, 60, 20, 5)
    with c4:
        shrinkage_percent = st.slider("Shrinkage (%)", 0, 50, 30)

    occ_percent = st.slider("Doluluk / Occupancy Hedefi (%)", 50, 95, 85)
    st.caption("Doluluk = Trafik (Erlang) / Agent. Hedef %85 ise, sistem doluluk %85’i aşmayacak şekilde agent artırır.")

    st.markdown("---")

    # ======================================================
    # Hesap
    # ======================================================
    interval_sec = 1800
    target_sl = sl_percent / 100
    shrinkage = shrinkage_percent / 100
    occ_target = occ_percent / 100

    forecast_df["tarih"] = pd.to_datetime(forecast_df["tarih"])

    # Gün adı (TR)
    day_map = {
        "Monday": "Pazartesi",
        "Tuesday": "Salı",
        "Wednesday": "Çarşamba",
        "Thursday": "Perşembe",
        "Friday": "Cuma",
        "Saturday": "Cumartesi",
        "Sunday": "Pazar",
    }
    forecast_df["Gün"] = forecast_df["tarih"].dt.day_name().map(day_map)

    if st.button("🚀 Personel İhtiyacını Hesapla ve Kaydet", use_container_width=True):
        result_rows = []

        with st.spinner("Hesaplanıyor..."):
            for _, row in forecast_df.iterrows():
                daily_calls = float(row["y_pred"])
                gun = row["Gün"]
                tarih = row["tarih"]

                day_ratio = ratio_df[ratio_df["Gün"] == gun].copy()
                if day_ratio.empty:
                    continue

                for _, r in day_ratio.iterrows():
                    slot = int(r["Slot"])
                    oran = float(r["Oran(%)"]) / 100.0
                    aralik = str(r["Aralık"])

                    slot_calls = daily_calls * oran

                    met = erlang_c_required_agents(
                        calls=slot_calls,
                        aht_sec=float(aht),
                        interval_sec=float(interval_sec),
                        target_sl=float(target_sl),
                        target_time_sec=float(target_time),
                        occ_target=float(occ_target),
                    )

                    net_agents = int(met["m"])
                    planned_agents = math.ceil(net_agents / (1 - shrinkage)) if shrinkage < 1 else net_agents

                    result_rows.append(
                        {
                            "Tarih": pd.to_datetime(tarih).date(),
                            "Gün": gun,
                            "Slot": slot,
                            "Aralık": aralik,
                            "Tahmin Çağrı": round(slot_calls, 2),
                            "Trafik (Erlang)": round(float(met["traffic_a"]), 3),
                            "Doluluk (%)": round(float(met["occupancy"]) * 100, 1),
                            "SL (model) (%)": round(float(met["sl"]) * 100, 1),
                            "Net Agent": net_agents,
                            "Planlanan Agent": planned_agents,
                        }
                    )

        result_df = pd.DataFrame(result_rows)
        st.session_state["sp_staffing_result_df"] = result_df
        st.success("✅ Personel tahmini hesaplandı ve kaydedildi.")

    # ======================================================
    # Slot Bazlı Görünüm (Seçim + Özet + Grafik + Tablo)
    # ======================================================
    st.markdown("---")
    st.subheader("📈 Slot Bazlı Görünüm (Kısa Grafik + Tablo)")

    df_all = st.session_state.get("sp_staffing_result_df")
    if df_all is None or not isinstance(df_all, pd.DataFrame) or df_all.empty:
        st.info("Grafik ve tablo için önce hesaplama yapmalısın.")
        return

    df_all = df_all.copy()
    df_all["Tarih"] = pd.to_datetime(df_all["Tarih"])

    all_dates = sorted(df_all["Tarih"].dt.date.unique().tolist())
    if not all_dates:
        st.info("Tarih bulunamadı.")
        return

    # Tarih label
    date_labels, date_map2 = [], {}
    for d in all_dates:
        d_ts = pd.to_datetime(d)
        gun_tr = day_map.get(d_ts.day_name(), d_ts.day_name())
        label = f"{d} • {gun_tr}"
        date_labels.append(label)
        date_map2[label] = d

    left, right = st.columns([1.25, 2.75], vertical_alignment="top")

    # ---------------- SOL: Seçimler + Gün Özeti ----------------
    with left:
        with st.container(border=True):
            st.markdown("#### 🎛️ Seçimler")
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

            picked_label = st.selectbox(
                "Tarih seç",
                options=date_labels,
                index=0,
                key="sp_staff_pick_date",
            )
            picked_date = date_map2[picked_label]

            metric_choice = st.radio(
                "Grafik metriği",
                ["Planlanan Agent", "Net Agent", "Tahmin Çağrı"],
                index=0,
                horizontal=False,
                key="sp_staff_metric_choice",
            )

            show_calls_overlay = st.checkbox(
                "Çağrı overlay göster (ikincil eksen)",
                value=True,
                key="sp_staff_show_calls_overlay",
            )

        st.markdown("<div style='height:80px'></div>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("#### 📌 Seçilen Gün Özeti")
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

            dff_kpi = df_all[df_all["Tarih"].dt.date == picked_date].copy()

            if dff_kpi.empty:
                st.info("Seçilen tarihte veri yok.")
            else:
                total_calls = float(dff_kpi["Tahmin Çağrı"].sum())
                max_plan = int(dff_kpi["Planlanan Agent"].max())
                max_net = int(dff_kpi["Net Agent"].max())
                avg_occ = float(dff_kpi["Doluluk (%)"].mean())
                avg_sl = float(dff_kpi["SL (model) (%)"].mean())
                peak_slot = int(dff_kpi.sort_values("Planlanan Agent", ascending=False).iloc[0]["Slot"])

                r1c1, r1c2 = st.columns([2, 1])
                r1c1.metric("Toplam Tahmin Çağrı", f"{total_calls:,.0f}")
                r1c2.metric("Peak Slot", f"{peak_slot}")

                r2c1, r2c2 = st.columns([2, 1])
                r2c1.metric("Max Planlanan Agent", f"{max_plan}")
                r2c2.metric("Max Net Agent", f"{max_net}")

                r3c1, r3c2 = st.columns([2, 1])
                r3c1.metric("Ort. Doluluk (%)", f"{avg_occ:.1f}")
                r3c2.metric("Ort. SL (%)", f"{avg_sl:.1f}")

    # ---------------- SAĞ: Grafik + Detay Tablo ----------------
    with right:
        with st.container(border=True):
            st.markdown("#### 📋 Seçilen Gün Detayı")

            dff = df_all[df_all["Tarih"].dt.date == picked_date].copy().sort_values("Slot")

            if dff.empty:
                st.info("Seçilen tarihte veri yok.")
            else:
                dff["SlotLabel"] = (
                    dff["Slot"].astype(int).astype(str).str.zfill(2)
                    + " • "
                    + dff["Aralık"].astype(str)
                )

                # Grafik
                try:
                    import plotly.graph_objects as go
                    from plotly.subplots import make_subplots

                    fig = make_subplots(specs=[[{"secondary_y": True}]])

                    if metric_choice == "Planlanan Agent":
                        y_main = dff["Planlanan Agent"].values
                        y_name = "Planlanan Agent"
                    elif metric_choice == "Net Agent":
                        y_main = dff["Net Agent"].values
                        y_name = "Net Agent"
                    else:
                        y_main = dff["Tahmin Çağrı"].values
                        y_name = "Tahmin Çağrı"

                    fig.add_trace(
                        go.Scatter(
                            x=dff["SlotLabel"],
                            y=y_main,
                            mode="lines+markers",
                            name=y_name,
                        ),
                        secondary_y=False,
                    )

                    if show_calls_overlay and metric_choice != "Tahmin Çağrı":
                        fig.add_trace(
                            go.Bar(
                                x=dff["SlotLabel"],
                                y=dff["Tahmin Çağrı"].values,
                                name="Tahmin Çağrı",
                                opacity=0.35,
                            ),
                            secondary_y=True,
                        )

                    fig.update_layout(
                        height=340,
                        margin=dict(l=10, r=10, t=40, b=10),
                        title=f"{picked_label} — Slot Bazlı Görünüm",
                        xaxis_title="Slot / Aralık",
                    )
                    fig.update_yaxes(title_text=y_name, secondary_y=False)
                    fig.update_yaxes(title_text="Tahmin Çağrı", secondary_y=True)

                    st.plotly_chart(fig, use_container_width=True)

                except Exception:
                    fallback = dff[["Slot", "Planlanan Agent", "Net Agent", "Tahmin Çağrı"]].set_index("Slot")
                    st.line_chart(fallback, height=320)

                # Detay tablo
                show_cols = [
                    "Tarih", "Gün", "Slot", "Aralık",
                    "Tahmin Çağrı", "Trafik (Erlang)", "Doluluk (%)", "SL (model) (%)",
                    "Net Agent", "Planlanan Agent",
                ]
                st.dataframe(dff[show_cols], use_container_width=True, hide_index=True, height=360)

    # ======================================================
    # Tüm Sonuç Tablosu (Search + Sayfalama)
    # ======================================================
    st.markdown("---")
    st.subheader("📚 Tüm Sonuç Tablosu")

    toolbar1, toolbar2, toolbar3 = st.columns([2.2, 1.2, 1.2], vertical_alignment="center")
    with toolbar1:
        q = st.text_input("🔎 Ara (tüm kolonlarda)", value="", key="sp_staff_search")
    with toolbar2:
        page_size = st.selectbox("Satır", [24, 48, 72, 96, 144, 192], index=1, key="sp_staff_pagesize")
    with toolbar3:
        st.caption("")

    df_view = df_all.copy()

    if q.strip():
        qq = q.strip().lower()
        mask = df_view.astype(str).apply(lambda s: s.str.lower().str.contains(qq, na=False)).any(axis=1)
        df_view = df_view[mask].copy()

    total_rows = len(df_view)
    total_pages = max(1, int(math.ceil(total_rows / page_size)))

    bar1, bar2 = st.columns([1.2, 2.8], vertical_alignment="center")
    with bar1:
        page = st.number_input("Sayfa", min_value=1, max_value=total_pages, value=1, step=1, key="sp_staff_page")
    with bar2:
        start_i = (page - 1) * page_size
        end_i = min(start_i + page_size, total_rows)
        st.caption(f"Gösterilen: {start_i+1 if total_rows else 0}–{end_i} / {total_rows}")

    df_page = df_view.iloc[start_i:end_i].copy()

    st.dataframe(df_page, use_container_width=True, hide_index=True)
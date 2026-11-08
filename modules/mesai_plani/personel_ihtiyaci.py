# Mesai Plani / Personel Ihtiyaci — bu ekranın / servisin uygulama kodu.
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

    # Stable Erlang-B recurrence, then B -> C; avoids factorial overflow.
    b = 1.0
    for k in range(1, m+1):
        b = a*b/(k+a*b)
    rho = a/m
    return float(b/(1-rho+rho*b))


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

def calculate_staffing(forecast_df, ratio_df, aht=300, target_sl=.8,
                       target_time=20, shrinkage=.3, occ_target=.85):
    from ortak.cagri_tahmin_servisi import validate_forecast, DAY_NAMES
    forecast=validate_forecast(forecast_df)
    if not (0 < aht <= 3600 and 0 < target_sl < 1 and 0 <= shrinkage < 1 and 0 < occ_target < 1 and target_time>0):
        raise ValueError("Geçersiz personel hesaplama parametreleri.")
    if not {'Gün','Slot','Oran(%)'} <= set(ratio_df):
        raise ValueError("Oran profilinde Gün, Slot ve Oran(%) gerekli.")
    if ratio_df.duplicated(['Tarih','Slot'] if 'Tarih' in ratio_df else ['Gün','Slot']).any():
        raise ValueError("Oran profilinde aynı gün/slot birden fazla kez var.")
    rows=[]
    for row in forecast.itertuples(index=False):
        day=DAY_NAMES[row.tarih.weekday()]
        profile=ratio_df[ratio_df['Gün']==day]
        if 'Tarih' in ratio_df:
            profile=profile[pd.to_datetime(profile.Tarih).dt.normalize()==row.tarih.normalize()]
        if len(profile)!=48 or set(profile.Slot)!=set(range(1,49)):
            raise ValueError(f"{day} için 48 slotun tamamı gerekli.")
        ratios=pd.to_numeric(profile['Oran(%)'],errors='raise')
        if not math.isfinite(float(ratios.sum())) or ratios.isna().any() or (ratios<0).any() or abs(float(ratios.sum())-100)>.05:
            raise ValueError(f"{day} oranlarının toplamı %100 olmalı.")
        for (_,r),percent in zip(profile.iterrows(),ratios):
            calls=float(row.y_pred)*float(percent)/100
            met=erlang_c_required_agents(calls,aht,1800,target_sl,target_time,occ_target)
            slot=int(r['Slot'])
            label=r.get('Aralık',f'{(slot-1)//2:02d}:{((slot-1)%2)*30:02d}')
            rows.append({'Tarih':row.tarih.date(),'Gün':day,'Slot':slot,'Aralık':label,
                         'Tahmin Çağrı':round(calls,2),'Trafik (Erlang)':round(met['traffic_a'],3),
                         'Doluluk (%)':round(met['occupancy']*100,1),'SL (model) (%)':round(met['sl']*100,1),
                         'Net Agent':met['m'],'Planlanan Agent':math.ceil(met['m']/(1-shrinkage))})
    return pd.DataFrame(rows)

def render():
    st.subheader("👥 Personel Tahmin (Erlang C)")
    st.markdown("---")

    # Gerekli veriler
    if st.session_state.get("sp_forecast_df") is None:
        st.warning("Önce Tahmin Kaynağı ekranında bir model seçin veya elle tahmin girin.")
        return

    if "sp_active_ratio_profile_df" not in st.session_state or st.session_state["sp_active_ratio_profile_df"] is None:
        st.warning("Önce aktif bir 30 dk oran profili seçmelisin (Kayıt Seçim ekranından).")
        return

    forecast_df = st.session_state["sp_forecast_df"].copy()
    ratio_df=st.session_state['sp_active_ratio_profile_df'].copy()
    first=pd.to_datetime(forecast_df.tarih).min().date();last=pd.to_datetime(forecast_df.tarih).max().date()
    st.markdown('#### Interval profilinin uygulanacağı dönem')
    a,b=st.columns(2)
    start=a.date_input('Başlangıç',value=first,min_value=first,max_value=last,key=f'staffing_start_{first}_{last}',format='DD.MM.YYYY')
    end=b.date_input('Bitiş',value=last,min_value=first,max_value=last,key=f'staffing_end_{first}_{last}',format='DD.MM.YYYY')
    if end<start:st.error('Bitiş tarihi başlangıçtan önce olamaz.');return
    forecast_df=forecast_df[pd.to_datetime(forecast_df.tarih).dt.date.between(start,end)].copy()
    if 'Tarih' in ratio_df:ratio_df=ratio_df.sort_values('Tarih').drop(columns='Tarih').drop_duplicates(['Gün','Slot'],keep='last')

    if forecast_df.empty or ratio_df.empty:
        st.error("Tahmin veya oran profili boş.")
        return

    # ======================================================
    # Parametreler
    # ======================================================
    st.markdown("### ⚙️ Parametreler")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        aht = st.slider("AHT (sn)", 60, 600, 300, 5)
    with c2:
        sl_percent = st.slider("Service Level (%)", 50, 95, 80, 5)
    with c3:
        target_time = st.slider("Hedef Süre (sn)", 5, 60, 20, 5)
    with c4:
        shrinkage_percent = st.slider("Shrinkage (%)", 0, 50, 30, 5)

    occ_percent = st.slider("Doluluk / Occupancy Hedefi (%)", 50, 95, 85, 5)
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
        try:
            with st.spinner("Personel ihtiyacı hesaplanıyor..."):
                result_df=calculate_staffing(forecast_df,ratio_df,aht=float(aht),target_sl=target_sl,
                                            target_time=float(target_time),shrinkage=shrinkage,occ_target=occ_target)
            st.session_state["sp_staffing_result_df"] = result_df
            from ortak.interval_servisi import record_used_profile
            record_used_profile(st.session_state,forecast_df,ratio_df)
            from ortak.calisma_alani_deposu import save_keys
            save_keys(st.session_state)
        except ValueError as exc:
            st.error(str(exc))
            return
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
                from ortak.saat_etiketleri import slot_label
                r1c2.metric("En yoğun saat aralığı", slot_label(peak_slot))

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

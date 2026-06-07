# modules/shift_planner/forecast_view.py
import pandas as pd
import numpy as np
import streamlit as st
import calendar


TR_DAY_MAP = {
    "Monday": "Pazartesi",
    "Tuesday": "Salı",
    "Wednesday": "Çarşamba",
    "Thursday": "Perşembe",
    "Friday": "Cuma",
    "Saturday": "Cumartesi",
    "Sunday": "Pazar",
}


def _format_meta(meta: dict) -> dict:
    return {
        "model_name": meta.get("model_name", "-"),
        "horizon": meta.get("horizon", "-"),
        "start": meta.get("start", "-"),
        "end": meta.get("end", "-"),
        "created_at": meta.get("created_at", "-"),
    }


def _prep_df(df_fc: pd.DataFrame) -> pd.DataFrame:
    df = df_fc.copy()
    if "tarih" not in df.columns:
        raise ValueError("Tahmin verisinde 'tarih' kolonu yok.")
    if "y_pred" not in df.columns:
        raise ValueError("Tahmin verisinde 'y_pred' kolonu yok.")

    df["tarih"] = pd.to_datetime(df["tarih"], errors="coerce")
    df = df[df["tarih"].notna()].sort_values("tarih")
    df["y_pred"] = pd.to_numeric(df["y_pred"], errors="coerce").fillna(0.0)
    return df.reset_index(drop=True)


def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def _to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Tahmin") -> bytes:
    import io
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()


def _compute_ekstre_kesim_flag(dt: pd.Series) -> pd.Series:
    """
    FE’deki yaklaşımı basitleştirerek aynı kurala yakın tutuyoruz:
    - Kesim günleri: 9,16,24 ve bazı ay sonu edge-case’leri.
    """
    day = dt.dt.day
    ld = dt.dt.days_in_month

    is_kesim = day.isin([9, 16, 24])

    # ay 31 çekiyorsa 31 de kesim olabilsin
    is_kesim |= (day == 31) & (ld == 31)

    # FE’deki gibi: önceki gün ay sonu 30/28 ise ayın 1’i de kesim sayılabiliyordu
    prev = dt - pd.Timedelta(days=1)
    prev_ld = prev.dt.days_in_month
    is_kesim |= (day == 1) & prev_ld.isin([30, 28])

    # Şubat 29 özel
    is_kesim |= (day == 29) & (prev_ld == 29) & (prev.dt.month == 2)

    return is_kesim.astype(int)


def _compute_son_odeme_flag(dt: pd.Series) -> pd.Series:
    """
    FE’ye benzer mantık:
    - Kesim günleri (9,16,24 [+ ay sonu seçenekleri]) -> +9 gün
    - Eğer cumartesi/pazar ise pazartesiye ötelenir
    """
    year_min = int(dt.dt.year.min())
    year_max = int(dt.dt.year.max())

    all_son_odeme = set()

    for yy in range(year_min - 1, year_max + 2):
        for mm in range(1, 13):
            ld = calendar.monthrange(yy, mm)[1]
            kesimler = [9, 16, 24]

            if ld == 31:
                kesimler.append(31)
            elif ld == 29 and mm == 2:
                kesimler.append(29)
            elif ld in [28, 30]:
                next_month = pd.Timestamp(yy, mm, ld) + pd.Timedelta(days=1)
                kesimler.append(int(next_month.day))

            for k in kesimler:
                try:
                    kesim_tarihi = pd.Timestamp(yy, mm, k)
                except Exception:
                    continue

                son_odeme = kesim_tarihi + pd.Timedelta(days=9)

                if son_odeme.weekday() == 5:
                    son_odeme += pd.Timedelta(days=2)
                elif son_odeme.weekday() == 6:
                    son_odeme += pd.Timedelta(days=1)

                all_son_odeme.add(son_odeme.date())

    return dt.dt.date.isin(all_son_odeme).astype(int)


def _enrich_forecast_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    dt = out["tarih"]

    out["Gün"] = dt.dt.day
    out["Ay"] = dt.dt.month
    out["Yıl"] = dt.dt.year
    out["HaftaNo"] = dt.dt.isocalendar().week.astype(int)
    out["HaftanınGünü"] = (dt.dt.weekday + 1).astype(int)  # Pazartesi=1
    out["Gün İsmi"] = dt.dt.day_name().map(TR_DAY_MAP).fillna(dt.dt.day_name())

    out["EKSTRE_KESIM"] = _compute_ekstre_kesim_flag(dt)
    out["SON_ODEME"] = _compute_son_odeme_flag(dt)

    return out


def render():
    st.subheader("Tahmin Analizi")
    st.caption("Çağrı Tahmini ekranında üretilen tahminler burada görüntülenir ve planlamaya temel olur.")
    st.markdown("---")

    if not st.session_state.get("cf_forecast_ready"):
        st.info("Henüz tahmin yok. **Çağrı Tahmini > Tahmin** sekmesinden tahmin üret.")
        return

    meta = _format_meta(st.session_state.get("cf_forecast_meta", {}))
    df_fc = st.session_state.get("cf_forecast_df")

    if df_fc is None or not isinstance(df_fc, pd.DataFrame) or df_fc.empty:
        st.warning("Tahmin verisi bulunamadı veya boş. Tekrar tahmin üret.")
        return

    try:
        df = _prep_df(df_fc)
    except Exception as e:
        st.error(f"Tahmin verisi hazırlanamadı: {e}")
        return

    # ----------------------------
    # Modern KPI satırı
    # ----------------------------
    a1, a2 = st.columns(2)
    with a1:
        with st.container(border=True):
            st.markdown(
                f"""
                <div style="text-align:center;">
                    <div style="font-size:16px; font-weight:600;">🧠 Model</div>
                    <div style="font-size:26px; font-weight:800; margin-top:6px;">
                        {meta["model_name"]}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with a2:
        with st.container(border=True):
            st.markdown(
                f"""
                <div style="text-align:center;">
                    <div style="font-size:16px; font-weight:600;">🗓️ Bitiş</div>
                    <div style="font-size:26px; font-weight:800; margin-top:6px;">
                        {meta["horizon"]}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown(
                f"""
                <div style="text-align:center;">
                    <div style="font-size:16px; font-weight:600;">🗓️ Başlangıç</div>
                    <div style="font-size:26px; font-weight:800; margin-top:6px;">
                        {meta['start']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with c2:
        with st.container(border=True):
            st.markdown(
                f"""
                <div style="text-align:center;">
                    <div style="font-size:16px; font-weight:600;">🗓️ Bitiş</div>
                    <div style="font-size:26px; font-weight:800; margin-top:6px;">
                        {meta['end']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with c3:
        with st.container(border=True):
            st.markdown(
                f"""
                <div style="text-align:center;">
                    <div style="font-size:16px; font-weight:600;">📦 Gün</div>
                    <div style="font-size:26px; font-weight:800; margin-top:6px;">
                        {len(df):,}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ----------------------------
    # Kontroller
    # ----------------------------
    c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.2, 1.4], vertical_alignment="bottom")

    with c1:
        view_mode = st.selectbox(
            "Görünüm",
            ["Günlük", "Haftalık", "Aylık"],
            index=0,
            key="sp_fc_view_mode",
        )
    with c2:
        round_pred = st.toggle("Yuvarla", value=True, key="sp_fc_round")
    with c3:
        floor_zero = st.toggle("Negatifleri 0 yap", value=True, key="sp_fc_floor")
    with c4:
        show_table = st.toggle("Tabloyu göster", value=True, key="sp_fc_show_table")

    # işleme
    df_v = df.copy()
    if floor_zero:
        df_v["y_pred"] = np.maximum(df_v["y_pred"].values, 0.0)
    if round_pred:
        df_v["y_pred"] = np.round(df_v["y_pred"].values).astype(int)

    # enrich (gün ismi + banka flag)
    df_en = _enrich_forecast_table(df_v)

    # ----------------------------
    # Toplulaştırma
    # ----------------------------
    if view_mode == "Günlük":
        plot_df = df_v.set_index("tarih")[["y_pred"]]

    elif view_mode == "Haftalık":
        tmp = df_v.copy()
        tmp["week"] = tmp["tarih"].dt.to_period("W").apply(lambda r: r.start_time)
        plot_df = tmp.groupby("week", as_index=False)["y_pred"].sum()
        plot_df = plot_df.rename(columns={"week": "tarih"}).set_index("tarih")[["y_pred"]]

    else:  # Aylık
        tmp = df_v.copy()
        tmp["month"] = tmp["tarih"].dt.to_period("M").apply(lambda r: r.start_time)
        plot_df = tmp.groupby("month", as_index=False)["y_pred"].sum()
        plot_df = plot_df.rename(columns={"month": "tarih"}).set_index("tarih")[["y_pred"]]

    # ----------------------------
    # Özet KPI’lar
    # ----------------------------
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Toplam Tahmin", f"{int(plot_df['y_pred'].sum()):,}")
    s2.metric("Ortalama", f"{float(plot_df['y_pred'].mean()):,.2f}")
    s3.metric("Maksimum", f"{int(plot_df['y_pred'].max()):,}")
    s4.metric("Minimum", f"{int(plot_df['y_pred'].min()):,}")

    st.markdown("---")

    # ----------------------------
    # Grafik
    # ----------------------------
    st.markdown("### 📈 Tahmin Grafiği")
    st.line_chart(plot_df, height=340)

    # ----------------------------
    # (ÜSTTEKİ İNDİRME BUTONU KALDIRILDI)
    # ----------------------------
    st.caption("İpucu: Haftalık/Aylık görünüm planlama için daha okunur olabilir.")

    if show_table:
        st.markdown("### 🧾 Tahmin Tablosu (Detaylı)")

        table_df = df_en[["tarih", "Gün İsmi", "y_pred"]].copy()
        table_df["y_pred"] = pd.to_numeric(table_df["y_pred"], errors="coerce").fillna(0.0)

        table_df["-10%"] = np.round(table_df["y_pred"] * 0.90, 0).astype(int)
        table_df["+10%"] = np.round(table_df["y_pred"] * 1.10, 0).astype(int)
        table_df["-5%"] = np.round(table_df["y_pred"] * 0.95, 0).astype(int)
        table_df["+5%"] = np.round(table_df["y_pred"] * 1.05, 0).astype(int)

        table_df = table_df.rename(
            columns={
                "tarih": "Tarih",
                "Gün İsmi": "Gün",
                "y_pred": "Tahmin (Çağrı)",
            }
        )

        table_df["Tarih"] = pd.to_datetime(table_df["Tarih"]).dt.date.astype(str)
        table_df = table_df[["Tarih", "Gün", "Tahmin (Çağrı)", "-10%", "+10%", "-5%", "+5%"]]

        # ✅ ALTTAKİ TABLO İÇİN İNDİRME BUTONLARI (CSV + EXCEL)
        d1, d2, d3 = st.columns([1.2, 1.2, 2.6], vertical_alignment="bottom")
        with d1:
            st.download_button(
                "⬇️ Tablo CSV indir",
                data=_to_csv_bytes(table_df),
                file_name="tahmin_tablo_detay.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with d2:
            st.download_button(
                "⬇️ Tablo Excel indir",
                data=_to_excel_bytes(table_df, sheet_name="Detay"),
                file_name="tahmin_tablo_detay.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with d3:
            st.caption("Detay tabloyu CSV/Excel olarak indirebilirsin.")

        st.dataframe(table_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("### 🏦 Banka Etkilerine Göre Özet")

        left, right = st.columns(2)

        ekstre_df = df_en[df_en["EKSTRE_KESIM"] == 1].copy()
        ekstre_df["Tahmin (Çağrı)"] = np.round(pd.to_numeric(ekstre_df["y_pred"], errors="coerce").fillna(0.0), 0).astype(int)
        ekstre_df["Tarih"] = pd.to_datetime(ekstre_df["tarih"]).dt.date.astype(str)
        ekstre_df["Gün"] = ekstre_df["Gün İsmi"]
        ekstre_df = ekstre_df[["Tarih", "Gün", "Tahmin (Çağrı)"]]

        son_odeme_df = df_en[df_en["SON_ODEME"] == 1].copy()
        son_odeme_df["Tahmin (Çağrı)"] = np.round(pd.to_numeric(son_odeme_df["y_pred"], errors="coerce").fillna(0.0), 0).astype(int)
        son_odeme_df["Tarih"] = pd.to_datetime(son_odeme_df["tarih"]).dt.date.astype(str)
        son_odeme_df["Gün"] = son_odeme_df["Gün İsmi"]
        son_odeme_df = son_odeme_df[["Tarih", "Gün", "Tahmin (Çağrı)"]]

        with left:
            st.markdown("#### 📌 Ekstre Kesim Günleri (1 olanlar)")
            if ekstre_df.empty:
                st.info("Bu aralıkta ekstre kesim günü yok.")
            else:
                st.metric("Toplam Çağrı", f"{int(ekstre_df['Tahmin (Çağrı)'].sum()):,}")
                st.dataframe(ekstre_df, use_container_width=True, hide_index=True)

        with right:
            st.markdown("#### 📌 Son Ödeme Günleri (1 olanlar)")
            if son_odeme_df.empty:
                st.info("Bu aralıkta son ödeme günü yok.")
            else:
                st.metric("Toplam Çağrı", f"{int(son_odeme_df['Tahmin (Çağrı)'].sum()):,}")
                st.dataframe(son_odeme_df, use_container_width=True, hide_index=True)
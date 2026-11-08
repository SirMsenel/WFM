# Mesai Plani / Tahmin Kaynagi — bu ekranın / servisin uygulama kodu.
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


def _compute_ekstre_kesim_flag(dt):
    from ortak.odeme_takvimi import billing_flag
    return billing_flag(dt,'cut')


def _compute_son_odeme_flag(dt):
    from ortak.odeme_takvimi import billing_flag
    return billing_flag(dt,'due')


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


def _render_analysis():
    st.subheader("Tahmin Analizi")
    st.caption("Çağrı Tahmini ekranında üretilen tahminler burada görüntülenir ve planlamaya temel olur.")
    st.markdown("---")

    if st.session_state.get("sp_forecast_df") is None:
        st.info("Henüz tahmin yok. **Çağrı Tahmini > Tahmin** sekmesinden tahmin üret.")
        return

    meta = _format_meta(st.session_state.get("sp_forecast_meta", {}))
    df_fc = st.session_state.get("sp_forecast_df")

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
                    <div style="font-size:16px; font-weight:600;">🗓️ Tahmin aralığı</div>
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
    from ortak.grafikler import daily_chart
    daily_chart(plot_df.reset_index(),'tarih',list(plot_df.columns),height=340)

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


def render():
    from ortak.cagri_tahmin_servisi import activate_forecast
    from datetime import date, timedelta
    state = st.session_state
    st.subheader("Planlamada Kullanılacak Çağrı Tahmini")
    st.caption("Dört modelin tahminini karşılaştır, birini seç veya günlük çağrı sayılarını elle gir. Seçimi kaydetmeden aktif planlama kaynağı değişmez.")
    options = state.get("cf_forecast_options", [])
    mode = st.radio("Tahmin kaynağı", ["Model tahmini seç", "Elle günlük tahmin gir"], horizontal=True, key="sp_source_mode")
    if mode == "Model tahmini seç":
        if not options:
            st.info("Çağrı Tahmini → Tahmin ekranından dört modelin tahminini üretin. Elle giriş de kullanabilirsiniz.")
        else:
            st.dataframe(pd.DataFrame([{"Sıra":o['rank'],"Model":o['name'],**o['metrics'],"Başlangıç":o['meta']['start'],"Bitiş":o['meta']['end']} for o in options]),hide_index=True,use_container_width=True)
            combined = pd.concat([o['frame'].set_index('tarih').y_pred.rename(o['name']) for o in options],axis=1)
            from ortak.grafikler import daily_chart
            daily_chart(combined.reset_index(),'tarih',list(combined.columns))
            names = {o['id']:o for o in options}
            selected = st.selectbox("Kullanılacak model tahmini",list(names),key="sp_selected_model")
            if st.button("Bu Tahmini Planlamada Kullan",key="sp_activate_model"):
                try:
                    activate_forecast(state,names[selected]['frame'],names[selected]['meta'])
                    st.success("Planlama tahmini kaydedildi. Personel Hesap ekranında ihtiyacı yeniden hesaplayın.")
                except ValueError as exc:
                    st.error(str(exc))
    else:
        current = state.get("sp_forecast_df")
        initial_start = current.tarih.min().date() if isinstance(current,pd.DataFrame) and not current.empty else date.today()
        initial_end = current.tarih.max().date() if isinstance(current,pd.DataFrame) and not current.empty else initial_start+timedelta(days=6)
        dates = st.date_input("Elle tahmin tarih aralığı",value=(initial_start,initial_end),key="sp_manual_dates")
        if isinstance(dates,tuple) and len(dates)==2:
            if (dates[1]-dates[0]).days > 366:
                st.error("En fazla 367 gün seçin.")
                return
            grid = pd.DataFrame({'tarih':pd.date_range(dates[0],dates[1])})
            if isinstance(current,pd.DataFrame):
                grid = grid.merge(current[['tarih','y_pred']],how='left',on='tarih')
            else:
                grid['y_pred'] = np.nan
            st.caption("Her günün çağrı sayısını girin; boş veya negatif kayıt kabul edilmez. Var olan planlama tahmini başlangıç değeri olarak gösterilir.")
            edited = st.data_editor(grid,hide_index=True,use_container_width=True,disabled=['tarih'],
                                    column_config={'tarih':st.column_config.DateColumn('Tarih'),
                                                   'y_pred':st.column_config.NumberColumn('Çağrı sayısı',min_value=0,step=1,required=True)},
                                    key=f"sp_manual_editor_{dates[0]}_{dates[1]}")
            if st.button("Elle Girilen Tahmini Kullan",key="sp_activate_manual"):
                try:
                    activate_forecast(state,edited,{'model_name':'Elle girilen tahmin','horizon':f'{len(edited)} gün','start':str(dates[0]),'end':str(dates[1]),'created_at':pd.Timestamp.now().isoformat()})
                    st.success("Elle girilen tahmin planlamaya alındı. Personel ihtiyacını yeniden hesaplayın.")
                except ValueError as exc:
                    st.error(str(exc))
    active = state.get('sp_forecast_meta',{})
    st.info(f"Aktif planlama kaynağı: {active.get('model_name','Henüz seçilmedi')} · {active.get('start','—')} → {active.get('end','—')}")
    if state.get('sp_forecast_df') is not None:
        _render_analysis()

# modules/call_forecast/predict_ui.py
import datetime as dt
import numpy as np
import pandas as pd
import streamlit as st


# ----------------------------
# helpers
# ----------------------------
def _daterange(start: dt.date, end: dt.date):
    cur = start
    while cur <= end:
        yield cur
        cur = cur + dt.timedelta(days=1)


def _detect_date_col(df: pd.DataFrame) -> str | None:
    from core.forecast_service import date_column
    return date_column(df)


def _is_30min_series(dt_series: pd.Series) -> bool:
    td = dt_series.sort_values().diff().dropna()
    if td.empty:
        return False
    return float(td.dt.total_seconds().median()) == 1800.0


def _day_name_tr(dt_series) -> pd.Series:
    """
    dt_series hem Series hem de DatetimeIndex gelebilir.
    Hata: 'DatetimeIndex' object has no attribute 'dt' → bu yüzden Series'e çeviriyoruz.
    """
    if isinstance(dt_series, pd.DatetimeIndex):
        s = pd.Series(dt_series)
    else:
        s = pd.Series(dt_series) if not isinstance(dt_series, pd.Series) else dt_series

    s = pd.to_datetime(s, errors="coerce")

    return (
        s.dt.day_name()
        .replace(
            {
                "Monday": "Pazartesi",
                "Tuesday": "Salı",
                "Wednesday": "Çarşamba",
                "Thursday": "Perşembe",
                "Friday": "Cuma",
                "Saturday": "Cumartesi",
                "Sunday": "Pazar",
            }
        )
        .fillna("")
    )


def _ramadan_flag(dt_series: pd.Series) -> pd.Series:
    ramadan_periods = [
        ("2020-04-24", "2020-05-23"),
        ("2021-04-14", "2021-05-13"),
        ("2022-04-03", "2022-05-02"),
        ("2023-03-23", "2023-04-21"),
        ("2024-03-11", "2024-04-09"),
        ("2025-03-01", "2025-03-30"),
        ("2026-02-18", "2026-03-19"),
        ("2027-02-08", "2027-03-09"),
        ("2028-01-28", "2028-02-26"),
        ("2029-01-16", "2029-02-14"),
        ("2030-01-06", "2030-02-04"),
    ]
    dt_series = pd.to_datetime(dt_series, errors="coerce")
    is_ramadan = pd.Series(False, index=dt_series.index)
    for start, end in ramadan_periods:
        s = pd.to_datetime(start)
        e = pd.to_datetime(end)
        is_ramadan |= ((dt_series >= s) & (dt_series <= e))
    return is_ramadan.astype(int)


def _tr_holiday_flags(dt_series: pd.Series) -> pd.DataFrame:
    import datetime as dt2

    BAYRAMLAR = {
        2020: [dt2.date(2020, 5, 24), dt2.date(2020, 7, 31)],
        2021: [dt2.date(2021, 5, 13), dt2.date(2021, 7, 20)],
        2022: [dt2.date(2022, 5, 2),  dt2.date(2022, 7, 9)],
        2023: [dt2.date(2023, 4, 21), dt2.date(2023, 6, 28)],
        2024: [dt2.date(2024, 4, 10), dt2.date(2024, 6, 16)],
        2025: [dt2.date(2025, 3, 30), dt2.date(2025, 6, 6)],
        2026: [dt2.date(2026, 3, 20), dt2.date(2026, 5, 27)],
        2027: [dt2.date(2027, 3, 10), dt2.date(2027, 5, 17)],
        2028: [dt2.date(2028, 2, 27), dt2.date(2028, 5, 5)],
        2029: [dt2.date(2029, 2, 15), dt2.date(2029, 4, 24)],
        2030: [dt2.date(2030, 2, 5),  dt2.date(2030, 4, 13)],
    }
    FIXED = [(1, 1), (4, 23), (5, 1), (5, 19), (7, 15), (8, 30), (10, 29)]

    resmi, bayram, arife, bayram_sonrasi = set(), set(), set(), set()

    years = sorted(set(pd.to_datetime(dt_series).dt.year.dropna().astype(int).tolist()))
    if not years:
        return pd.DataFrame(index=dt_series.index)

    y_min, y_max = min(years), max(years)
    for year in range(max(2020, y_min - 1), min(2030, y_max + 1) + 1):
        for m, d in FIXED:
            resmi.add(dt2.date(year, m, d))

        if year in BAYRAMLAR:
            ramazan, kurban = BAYRAMLAR[year]
            for i in range(3):
                bayram.add(ramazan + dt2.timedelta(days=i))
            for i in range(4):
                bayram.add(kurban + dt2.timedelta(days=i))
            arife.add(ramazan - dt2.timedelta(days=1))
            arife.add(kurban - dt2.timedelta(days=1))

            for start in [ramazan + dt2.timedelta(days=3), kurban + dt2.timedelta(days=4)]:
                d_ = start
                while d_.weekday() >= 5:
                    d_ += dt2.timedelta(days=1)
                bayram_sonrasi.add(d_)

    dts = pd.to_datetime(dt_series).dt.date
    return pd.DataFrame(
        {
            "Resmi_Tatil": dts.isin(resmi).astype(int),
            "Bayram": dts.isin(bayram).astype(int),
            "Arife": dts.isin(arife).astype(int),
            "Bayram_Sonrasi": dts.isin(bayram_sonrasi).astype(int),
        },
        index=dt_series.index,
    )


def _son_odeme_flag(dt_series: pd.Series) -> pd.Series:
    # FE mantığı ile uyumlu (kesim +9 gün, wknd kaydırma)
    import calendar

    dt_series = pd.to_datetime(dt_series, errors="coerce")
    years = sorted(set(dt_series.dt.year.dropna().astype(int).tolist()))
    if not years:
        return pd.Series(0, index=dt_series.index)

    y_min, y_max = min(years), max(years)

    all_son_odeme = set()
    for yy in range(y_min - 1, y_max + 2):
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

    return dt_series.dt.date.isin(all_son_odeme).astype(int)


def _mtv_donem_etkisi(dt_series: pd.Series) -> pd.Series:
    d = pd.to_datetime(dt_series, errors="coerce")
    month = d.dt.month
    day = d.dt.day
    out = pd.Series(0, index=d.index)
    is_mtv_month = (month == 1) | (month == 7)
    out.loc[is_mtv_month & (day <= 10)] = 1
    out.loc[is_mtv_month & (day > 10) & (day <= 20)] = 2
    out.loc[is_mtv_month & (day > 20)] = 3
    return out.astype(int)


def _ekstre_kesim_flag(dt_series: pd.Series) -> pd.Series:
    d = pd.to_datetime(dt_series, errors="coerce")
    day = d.dt.day
    last_day_in_month = d.dt.days_in_month

    is_kesim = day.isin([9, 16, 24])
    is_kesim |= (day == 31) & (last_day_in_month == 31)

    prev = (d - pd.Timedelta(days=1))
    prev_last = prev.dt.days_in_month
    is_kesim |= (day == 1) & prev_last.isin([30, 28])

    is_kesim |= (day == 29) & (prev_last == 29) & (prev.dt.month == 2)
    return is_kesim.astype(int)


def _apply_date_bank_features(
    future_df: pd.DataFrame,
    date_col: str,
    required_cols: list[str],
    df_full: pd.DataFrame,
) -> pd.DataFrame:
    """
    future_df içinde gerekli FE kolonlarını üretir (lag/roll yok).
    Sadece modelin istediği (required_cols) kolonları üretmeye çalışır.
    """
    out = future_df.copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
    d = out[date_col]

    # 30 dk veri mi? (df_full’dan anlarız)
    is_30min = False
    try:
        if isinstance(df_full, pd.DataFrame) and date_col in df_full.columns:
            is_30min = _is_30min_series(pd.to_datetime(df_full[date_col], errors="coerce").dropna())
    except Exception:
        is_30min = False

    # ---- Tarih parçaları ----
    if "Gun" in required_cols:
        out["Gun"] = d.dt.day
    if "Ay" in required_cols:
        out["Ay"] = d.dt.month
    if "Yil" in required_cols:
        out["Yil"] = d.dt.year
    if "Hafta" in required_cols:
        out["Hafta"] = d.dt.isocalendar().week.astype(int)
    if "Haftanin_Gunu" in required_cols:
        out["Haftanin_Gunu"] = d.dt.weekday + 1
    if "Gun_Ismi" in required_cols:
        out["Gun_Ismi"] = _day_name_tr(d).values
    if "Hafta_Ici" in required_cols:
        out["Hafta_Ici"] = (d.dt.weekday < 5).astype(int)
    if "Hafta_Sonu" in required_cols:
        out["Hafta_Sonu"] = (d.dt.weekday >= 5).astype(int)
    if "Mevsim" in required_cols:
        out["Mevsim"] = (d.dt.month % 12 // 3 + 1).astype(int)
    if "Ay_Basi" in required_cols:
        out["Ay_Basi"] = (d.dt.day == 1).astype(int)
    if "Ay_Ortasi" in required_cols:
        out["Ay_Ortasi"] = (d.dt.day == 15).astype(int)
    if "Ay_Sonu" in required_cols:
        out["Ay_Sonu"] = d.dt.is_month_end.astype(int)

    # ---- Ramazan / Tatil ----
    if "Ramazan" in required_cols:
        out["Ramazan"] = _ramadan_flag(d)
    need_tr = any(c in required_cols for c in ["Resmi_Tatil", "Bayram", "Arife", "Bayram_Sonrasi"])
    if need_tr:
        tr = _tr_holiday_flags(d)
        for c in ["Resmi_Tatil", "Bayram", "Arife", "Bayram_Sonrasi"]:
            if c in required_cols and c in tr.columns:
                out[c] = tr[c].values

    # ---- Banka ----
    if "MTV_Donem_Etkisi" in required_cols:
        out["MTV_Donem_Etkisi"] = _mtv_donem_etkisi(d)
    if "EKSTRE_KESIM" in required_cols:
        out["EKSTRE_KESIM"] = _ekstre_kesim_flag(d)
    if "SON_ODEME" in required_cols:
        out["SON_ODEME"] = _son_odeme_flag(d)

    # ---- 30 dk slotlar ----
    if is_30min:
        hour = d.dt.hour
        minute = d.dt.minute
        slot = hour * 2 + (minute // 30) + 1

        if "Slot30" in required_cols:
            out["Slot30"] = slot.astype(int)
        for alias in ("slot", "Slot"):
            if alias in required_cols:
                out[alias] = slot.astype(int)

        if "Slot_Block" in required_cols:
            block = pd.cut(hour, bins=[-1, 6, 12, 17, 23], labels=[1, 2, 3, 4])
            out["Slot_Block"] = block.astype(int)

        if "Mesai_Ici" in required_cols:
            out["Mesai_Ici"] = ((hour >= 9) & (hour < 18)).astype(int)
        if "Ogle_Saati" in required_cols:
            out["Ogle_Saati"] = ((hour >= 12) & (hour < 13)).astype(int)
        if "Aksam_Yogun" in required_cols:
            out["Aksam_Yogun"] = ((hour >= 17) & (hour < 20)).astype(int)

    return out


def _manual_standard_scale(X: pd.DataFrame, mean_: np.ndarray, scale_: np.ndarray) -> np.ndarray:
    mean_ = np.asarray(mean_).reshape(-1)
    scale_ = np.asarray(scale_).reshape(-1)

    Xv = X.values.astype(float)
    scale_safe = np.where(scale_ == 0, 1.0, scale_)
    return (Xv - mean_) / scale_safe


def _build_future_X_like_training(
    df_full: pd.DataFrame,
    X_columns: list[str],
    raw_features_used: list[str],
    date_col: str | None,
    start: dt.date,
    end: dt.date,
):
    """
    - Eğitimde kullanılan HAM feature listesi (raw_features_used) üzerinden geleceği kur
    - Tarih/banka FE kolonlarını tarih üzerinden üret
    - Diğer kolonlar son satırdan taşınır
    - pd.get_dummies + reindex(X_columns) ile model inputu %100 hizalanır
    """
    if not isinstance(df_full, pd.DataFrame) or df_full.empty:
        raise ValueError("df_full boş")

    # date_col yoksa df_full’dan bulmaya çalış
    if not date_col:
        date_col = _detect_date_col(df_full)

    if not date_col:
        # date yoksa da çalışır ama FE üretimi sınırlı olur
        date_col = "__date__"

    # future base
    is_interval = date_col in df_full and _is_30min_series(pd.to_datetime(df_full[date_col]))
    future_dates = pd.date_range(start, pd.Timestamp(end)+pd.Timedelta(days=1),
                                 freq="30min" if is_interval else "D", inclusive="left")
    future_df = pd.DataFrame({date_col: pd.to_datetime(future_dates)})

    # son satır baz değerler
    base_row = df_full.iloc[-1:].copy()

    # ham feature kolonlarını future_df’ye koy
    for col in raw_features_used:
        if col == date_col:
            continue
        if col in future_df.columns:
            continue

        if col in base_row.columns:
            future_df[col] = base_row.iloc[0][col]
        else:
            future_df[col] = np.nan

    # date & banka FE kolonlarını tarih üzerinden üret (modelde isteniyorsa)
    future_df = _apply_date_bank_features(
        future_df=future_df,
        date_col=date_col,
        required_cols=raw_features_used,
        df_full=df_full,
    )

    # Modelde “direkt tarih kolonu” olmamalı; ama kaldıysa çıkar
    used = [c for c in raw_features_used if c != date_col]
    X_raw = future_df[used].copy()

    # one-hot
    X_dum = pd.get_dummies(X_raw, drop_first=False)

    # eğitim kolonlarına hizala
    X_future = X_dum.reindex(columns=X_columns, fill_value=0)

    return future_df, X_future, date_col


def render():
    from core.forecast_service import ranked_candidates, forecast_candidates, reference_models, daily_history
    from core.workspace_store import save_keys
    st.subheader("Dört Model ile Çağrı Tahmini")
    st.caption("Aynı test döneminde RMSE'si en düşük dört model için aynı tarih aralığında ayrı tahmin üretilir.")
    candidates = ranked_candidates(st.session_state)
    if len(candidates) < 4:
        st.info("Model Kur ekranında modelleri karşılaştırın veya günlük geçmişten hızlı karşılaştırma başlatın.")
        if st.button("Günlük Geçmişten Modelleri Karşılaştır", key="cf_quick_compare"):
            try:
                raw = st.session_state.get("cf_raw_df")
                if raw is None:
                    raise ValueError("Önce veri kaynağından çağrı geçmişini yükleyin.")
                target = st.session_state.get("cf_target_name")
                with st.spinner("Modeller eğitiliyor..."):
                    reference_models(st.session_state, daily_history(raw, target=target))
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    if candidates:
        st.dataframe(pd.DataFrame([{"Sıra": i, "Model": b["name"], **b["metrics"]} for i,b in enumerate(candidates,1)]), hide_index=True, use_container_width=True)
    today = dt.date.today()
    c1,c2 = st.columns(2)
    start = c1.date_input("Tahmin başlangıcı", value=today, key="cf_four_start")
    end = c2.date_input("Tahmin bitişi", value=today+dt.timedelta(days=13), key="cf_four_end")
    if st.button("En İyi 4 Modelin Tahminini Üret", disabled=len(candidates)<4, key="cf_forecast_four"):
        try:
            with st.spinner("Dört model için tahminler üretiliyor..."):
                forecast_candidates(st.session_state,start,end)
                save_keys(st.session_state)
            st.success("Dört tahmin Mesai Planı → Tahmin Kaynağı ekranına aktarıldı. Kullanılacak kaynağı oradan seçin.")
        except Exception as exc:
            st.error(f"Tahmin üretilemedi: {exc}")
    options = st.session_state.get("cf_forecast_options", [])
    if options:
        st.markdown("### Üretilen Tahminler")
        combined = pd.concat([o["frame"].set_index("tarih").y_pred.rename(o["name"]) for o in options],axis=1)
        st.line_chart(combined)
        st.dataframe(combined.reset_index(),hide_index=True,use_container_width=True)
        st.download_button("Dört Tahmini CSV İndir",combined.to_csv().encode("utf-8-sig"),"dort_model_tahmin.csv","text/csv")

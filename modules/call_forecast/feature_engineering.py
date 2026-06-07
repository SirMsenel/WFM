# modules/call_forecast/feature_engineering.py
import calendar
import datetime as dt2
import pandas as pd
import streamlit as st


# ----------------------------
# CONSTANTS
# ----------------------------
RAMADAN_PERIODS = [
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


# ----------------------------
# STATE
# ----------------------------
def _ensure_state():
    # data_source burayı dolduruyor:
    st.session_state.setdefault("cf_full_df", None)

    # ham veriyi saklamak için (raw'a dön için)
    st.session_state.setdefault("cf_raw_df", None)

    # FE çıktısı
    st.session_state.setdefault("cf_fe_df", None)

    # FE meta (tahmin ekranı için çok kritik)
    st.session_state.setdefault("cf_fe_meta", None)

    # ✅ reset nonce: checkboxları %100 sıfırlamak için
    st.session_state.setdefault("cf_reset_nonce", 0)

    # seçim listeleri (mutlaka LIST olmalı)
    if not isinstance(st.session_state.get("cf_selected_features"), list):
        st.session_state["cf_selected_features"] = []
    if not isinstance(st.session_state.get("cf_bank_features"), list):
        st.session_state["cf_bank_features"] = []
    if not isinstance(st.session_state.get("cf_daily_features"), list):
        st.session_state["cf_daily_features"] = []
    if not isinstance(st.session_state.get("cf_slot_features"), list):
        st.session_state["cf_slot_features"] = []


def _reset_fe_state():
    st.session_state["cf_selected_features"] = []
    st.session_state["cf_bank_features"] = []
    st.session_state["cf_daily_features"] = []
    st.session_state["cf_slot_features"] = []

    if "base_df" in st.session_state:
        st.session_state.pop("base_df", None)

    # ✅ EN GARANTİ: nonce artır → tüm checkbox key’leri değişir → UI sıfırlanır
    st.session_state["cf_reset_nonce"] = st.session_state.get("cf_reset_nonce", 0) + 1

    # FE meta da sıfırlansın
    st.session_state["cf_fe_meta"] = None


# ----------------------------
# DETECTION HELPERS
# ----------------------------
def _detect_date_col(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        parsed = pd.to_datetime(df[col], errors="coerce")
        if parsed.notna().mean() > 0.8:
            return col
    return None


def _detect_target_col(df: pd.DataFrame, date_col: str) -> str | None:
    numeric_cols = df.select_dtypes(include=["int64", "float64", "int32", "float32"]).columns.tolist()
    if date_col in numeric_cols:
        numeric_cols.remove(date_col)
    if not numeric_cols:
        return None
    return max(numeric_cols, key=lambda c: df[c].notna().sum())


def _is_30min_series(dt: pd.Series) -> bool:
    td = dt.sort_values().diff().dropna()
    if td.empty:
        return False
    return td.dt.total_seconds().median() == 1800


# ----------------------------
# PURE FEATURE PIPELINE (TRAIN + PREDICT ORTAK)
# ----------------------------
def apply_feature_pipeline(
    df: pd.DataFrame,
    date_col: str,
    selected_date_features: list[str] | None = None,
    selected_bank_features: list[str] | None = None,
    selected_daily_features: list[str] | None = None,
    selected_slot_features: list[str] | None = None,
    include_lag_roll: bool = False,
    target_col_for_lag: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    UI’dan bağımsız feature üretimi (TRAIN & PREDICT aynı fonksiyonu kullanır).

    - include_lag_roll=False -> lag/roll üretmez (senin mevcut kuralın)
    - include_lag_roll=True  -> istersen analiz için üretir (target_col_for_lag gerekir)
    """
    selected_date_features = selected_date_features or []
    selected_bank_features = selected_bank_features or []
    selected_daily_features = selected_daily_features or []
    selected_slot_features = selected_slot_features or []

    fe_df = df.copy()

    # tarih parse
    fe_df[date_col] = pd.to_datetime(fe_df[date_col], errors="coerce")
    dt = fe_df[date_col]

    is_30min = _is_30min_series(dt)

    meta = {
        "date_col": date_col,
        "is_30min_data": bool(is_30min),
        "selected_date_features": list(selected_date_features),
        "selected_bank_features": list(selected_bank_features),
        "selected_daily_features": list(selected_daily_features),
        "selected_slot_features": list(selected_slot_features),
        "include_lag_roll": bool(include_lag_roll),
        "target_col_for_lag": target_col_for_lag,
    }

    # ----------------------------
    # Tarih parçaları
    # ----------------------------
    if "Gun" in selected_date_features:
        fe_df["Gun"] = dt.dt.day
    if "Ay" in selected_date_features:
        fe_df["Ay"] = dt.dt.month
    if "Yil" in selected_date_features:
        fe_df["Yil"] = dt.dt.year
    if "Hafta" in selected_date_features:
        fe_df["Hafta"] = dt.dt.isocalendar().week.astype(int)
    if "Haftanin_Gunu" in selected_date_features:
        fe_df["Haftanin_Gunu"] = dt.dt.weekday + 1
    if "Gun_Ismi" in selected_date_features:
        fe_df["Gun_Ismi"] = dt.dt.day_name()
    if "Hafta_Ici" in selected_date_features:
        fe_df["Hafta_Ici"] = (dt.dt.weekday < 5).astype(int)
    if "Hafta_Sonu" in selected_date_features:
        fe_df["Hafta_Sonu"] = (dt.dt.weekday >= 5).astype(int)
    if "Mevsim" in selected_date_features:
        fe_df["Mevsim"] = dt.dt.month % 12 // 3 + 1
    if "Ay_Basi" in selected_date_features:
        fe_df["Ay_Basi"] = (dt.dt.day == 1).astype(int)
    if "Ay_Ortasi" in selected_date_features:
        fe_df["Ay_Ortasi"] = (dt.dt.day == 15).astype(int)
    if "Ay_Sonu" in selected_date_features:
        fe_df["Ay_Sonu"] = dt.dt.is_month_end.astype(int)

    # ----------------------------
    # 30 dk slot feature
    # ----------------------------
    if is_30min:
        hour = dt.dt.hour
        minute = dt.dt.minute
        slot = hour * 2 + (minute // 30) + 1

        if "Slot30" in selected_date_features:
            fe_df["Slot30"] = slot

        # NOTE: Slot30_Aralik UI’da hoş bir label ama modele sokmayabilirsin.
        # İstersen seçiliyse üret:
        if "Slot30" in selected_date_features:
            start_minute = (slot - 1) * 30
            start_hour = (start_minute // 60).astype(int)
            start_min = (start_minute % 60).astype(int)
            end_minute = start_minute + 30
            end_hour = (end_minute // 60).astype(int)
            end_min = (end_minute % 60).astype(int)
            fe_df["Slot30_Aralik"] = (
                start_hour.astype(str).str.zfill(2) + ":" +
                start_min.astype(str).str.zfill(2) + " - " +
                end_hour.astype(str).str.zfill(2) + ":" +
                end_min.astype(str).str.zfill(2)
            )

        if "Slot_Block" in selected_date_features:
            block = pd.cut(hour, bins=[-1, 6, 12, 17, 23], labels=[1, 2, 3, 4])
            fe_df["Slot_Block"] = block.astype(int)
        if "Slot_WorkHour" in selected_date_features:
            fe_df["Mesai_Ici"] = ((hour >= 9) & (hour < 18)).astype(int)
        if "Slot_Lunch" in selected_date_features:
            fe_df["Ogle_Saati"] = ((hour >= 12) & (hour < 13)).astype(int)
        if "Slot_Evening" in selected_date_features:
            fe_df["Aksam_Yogun"] = ((hour >= 17) & (hour < 20)).astype(int)

    # ----------------------------
    # Ramazan
    # ----------------------------
    if "Ramazan" in selected_date_features:
        is_ramadan = pd.Series(False, index=fe_df.index)
        for start, end in RAMADAN_PERIODS:
            start_dt = pd.to_datetime(start)
            end_dt = pd.to_datetime(end)
            is_ramadan |= ((dt >= start_dt) & (dt <= end_dt))
        fe_df["Ramazan"] = is_ramadan.astype(int)

    # ----------------------------
    # TR_Holiday (Resmi + Bayram)
    # ----------------------------
    if "TR_Holiday" in selected_date_features:
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
        for year in range(2020, 2031):
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
                    d = start
                    while d.weekday() >= 5:
                        d += dt2.timedelta(days=1)
                    bayram_sonrasi.add(d)

        dts = fe_df[date_col].dt.date
        fe_df["Resmi_Tatil"] = dts.isin(resmi).astype(int)
        fe_df["Bayram"] = dts.isin(bayram).astype(int)
        fe_df["Arife"] = dts.isin(arife).astype(int)
        fe_df["Bayram_Sonrasi"] = dts.isin(bayram_sonrasi).astype(int)

    # ----------------------------
    # Banka Etkileri
    # ----------------------------
    month = dt.dt.month
    day = dt.dt.day

    if "MTV" in selected_bank_features:
        fe_df["MTV_Donem_Etkisi"] = 0
        is_mtv_month = (month == 1) | (month == 7)
        fe_df.loc[is_mtv_month & (day <= 10), "MTV_Donem_Etkisi"] = 1
        fe_df.loc[is_mtv_month & (day > 10) & (day <= 20), "MTV_Donem_Etkisi"] = 2
        fe_df.loc[is_mtv_month & (day > 20), "MTV_Donem_Etkisi"] = 3
    else:
        fe_df.drop(columns=["MTV_Donem_Etkisi"], inplace=True, errors="ignore")

    if "EKSTRE_KESIM" in selected_bank_features:
        day = dt.dt.day
        last_day_in_month = dt.dt.days_in_month

        is_kesim = day.isin([9, 16, 24])

        # 31 çeken aylarda 31'inde kesim
        is_kesim |= (day == 31) & (last_day_in_month == 31)

        # 1 Mart kuralı: Şubat 28/29'un ertesi günüyse kesim
        prev = dt - pd.Timedelta(days=1)
        prev_last = prev.dt.days_in_month

        is_kesim |= (
            (day == 1) &
            (prev.dt.month == 2) &          # bir önceki ay Şubat
            (prev.dt.day == prev_last)      # bir önceki gün Şubat'ın son günü (28 veya 29)
        )

        fe_df["EKSTRE_KESIM"] = is_kesim.astype(int)
    else:
        fe_df.drop(columns=["EKSTRE_KESIM"], inplace=True, errors="ignore")

    if "SON_ODEME" in selected_bank_features:
        all_son_odeme = set()
        year_min = int(dt.dt.year.min())
        year_max = int(dt.dt.year.max())

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

        fe_df["SON_ODEME"] = dt.dt.date.isin(all_son_odeme).astype(int)
    else:
        fe_df.drop(columns=["SON_ODEME"], inplace=True, errors="ignore")

    # ----------------------------
    # Lag / Roll (opsiyonel)
    # ----------------------------
    if not include_lag_roll:
        return fe_df, meta

    # include_lag_roll=True ise target şart
    if target_col_for_lag is None or target_col_for_lag not in fe_df.columns:
        # güvenli davran: üretmeden dön
        return fe_df, meta

    # sırala
    fe_df = fe_df.sort_values(date_col)

    diffs_min = fe_df[date_col].diff().dropna().dt.total_seconds() / 60
    median_diff = diffs_min.median() if not diffs_min.empty else None

    is_intraday = (median_diff is not None and median_diff < 60)
    is_daily = (median_diff is not None and median_diff >= 60 * 20)

    # günlük
    if is_daily:
        for f in selected_daily_features:
            if f == "lag_1":
                fe_df["lag_1"] = fe_df[target_col_for_lag].shift(1)
            elif f == "lag_7":
                fe_df["lag_7"] = fe_df[target_col_for_lag].shift(7)
            elif f == "lag_30":
                fe_df["lag_30"] = fe_df[target_col_for_lag].shift(30)
            elif f == "roll_7d":
                fe_df["roll_7d"] = fe_df[target_col_for_lag].rolling(7).mean()
            elif f == "roll_30d":
                fe_df["roll_30d"] = fe_df[target_col_for_lag].rolling(30).mean()

    # intraday
    if is_intraday:
        for f in selected_slot_features:
            if f == "roll_6h":
                fe_df["roll_6h"] = fe_df[target_col_for_lag].rolling(12).mean()
            elif f == "roll_12h":
                fe_df["roll_12h"] = fe_df[target_col_for_lag].rolling(24).mean()
            elif f == "roll_24h":
                fe_df["roll_24h"] = fe_df[target_col_for_lag].rolling(48).mean()
            elif f == "lag_48":
                fe_df["lag_48"] = fe_df[target_col_for_lag].shift(48)
            elif f == "lag_336":
                fe_df["lag_336"] = fe_df[target_col_for_lag].shift(336)

    return fe_df, meta


# ----------------------------
# UI
# ----------------------------
def render():
    _ensure_state()
    nonce = st.session_state.get("cf_reset_nonce", 0)

    st.subheader("Feature Engineering")

    source_df = st.session_state.get("cf_full_df")
    raw_df = st.session_state.get("cf_raw_df")

    if source_df is None or source_df.empty:
        st.info("Önce Veri Kaynağı ekranından veri yükle.")
        return

    # raw df hiç set edilmediyse yakala (fallback)
    if raw_df is None:
        st.session_state["cf_raw_df"] = source_df.copy()
        raw_df = st.session_state["cf_raw_df"]

    # ----------------------------
    # RAW'a dön
    # ----------------------------
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Raw'a dön (seçimleri sıfırla)"):
            _reset_fe_state()
            st.session_state["cf_full_df"] = raw_df.copy()
            st.session_state["cf_fe_df"] = None
            st.success("Raw'a dönüldü, seçimler sıfırlandı.")
            st.rerun()

    # FE her render'da source_df üzerinden yeniden üretilir
    base_df = source_df.copy()

    # ----------------------------
    # Tarih kolonunu bul
    # ----------------------------
    st.markdown("---")
    st.header("📅 Tarih Bazlı Etkenler")

    date_col = _detect_date_col(base_df)
    if date_col is None:
        st.error("❌ Tarih kolonu bulunamadı (parse oranı %80 üstü kolon yok).")
        return

    st.success(f"📅 Tarih kolonu: {date_col}")

    base_df[date_col] = pd.to_datetime(base_df[date_col], errors="coerce")
    dt = base_df[date_col]
    is_30min_data = _is_30min_series(dt)

    # ----------------------------
    # TARİHSEL FEATURE SEÇİMİ
    # ----------------------------
    features = {
        "Gün": "Gun",
        "Ay": "Ay",
        "Yıl": "Yil",
        "Hafta": "Hafta",
        "Haftanın Günü": "Haftanin_Gunu",
        "Gün İsmi": "Gun_Ismi",
        "Hafta içi": "Hafta_Ici",
        "Hafta Sonu": "Hafta_Sonu",
        "Mevsim": "Mevsim",
        "Ayın 1'i": "Ay_Basi",
        "Ayın 15'i": "Ay_Ortasi",
        "Ayın Son Günü": "Ay_Sonu",
        "Resmi & Dini Günler": "TR_Holiday",
        "Ramazan Günleri": "Ramazan",
    }

    selected = st.session_state["cf_selected_features"]

    cols = st.columns(3)
    for i, (label, key) in enumerate(features.items()):
        checked = key in selected
        val = cols[i % 3].checkbox(label, value=checked, key=f"cf_chk_{key}_{nonce}")
        if val and key not in selected:
            selected.append(key)
        if (not val) and key in selected:
            selected.remove(key)

    # ----------------------------
    # 30 DK FEATURE ALANI
    # ----------------------------
    st.markdown("---")
    if is_30min_data:
        st.subheader("🕒 30 Dakikalık Dilim Etiketleri")

        slot_features = {
            "30 dk Dilimi (1–48)": "Slot30",
            "Saat Bloku (Gece/Sabah/Öğle/Akşam)": "Slot_Block",
            "Mesai İçi (09–18)": "Slot_WorkHour",
            "Öğle Saati (12–13)": "Slot_Lunch",
            "Akşam Yoğunluğu (17–20)": "Slot_Evening",
        }

        cols = st.columns(3)
        for i, (label, key) in enumerate(slot_features.items()):
            checked = key in selected
            val = cols[i % 3].checkbox(label, value=checked, key=f"cf_slot_{key}_{nonce}")
            if val and key not in selected:
                selected.append(key)
            if (not val) and key in selected:
                selected.remove(key)

    st.success(f"✅ {len(selected)} adet tarih/slot feature aktif")

    # ---------------------------------------------------------------------------------------------------
    # BANKA ETKENLERİ
    # ---------------------------------------------------------------------------------------------------
    st.markdown("---")
    st.header("🏦 Banka Etkileri")

    bank_feature_map = {
        "MTV Dönemi": "MTV",
        "Ekstre Kesim Günü": "EKSTRE_KESIM",
        "Son Ödeme": "SON_ODEME",
    }

    bank_selected = st.session_state["cf_bank_features"]
    cols = st.columns(3)
    for i, (label, key) in enumerate(bank_feature_map.items()):
        checked = key in bank_selected
        val = cols[i].checkbox(label, value=checked, key=f"cf_bank_{key}_{nonce}")
        if val and key not in bank_selected:
            bank_selected.append(key)
        if (not val) and key in bank_selected:
            bank_selected.remove(key)

    st.success(f"🏦 {len(bank_selected)} banka etkisi aktif")

    # ---------------------------------------------------------------------------------------------------
    # Hareketli Ortalama / Lag (UI’da var, ama modele sokmayacaksın)
    # ---------------------------------------------------------------------------------------------------
    st.markdown("---")
    st.header("📈 Hareketli Ortalamalar (Analiz Amaçlı)")

    tmp_sorted = base_df.sort_values(date_col)
    diffs_min = tmp_sorted[date_col].diff().dropna().dt.total_seconds() / 60
    median_diff = diffs_min.median() if not diffs_min.empty else None

    is_intraday = (median_diff is not None and median_diff < 60)
    is_daily = (median_diff is not None and median_diff >= 60 * 20)

    if is_intraday:
        st.success("🕒 30 dk'lık (Intraday) zaman serisi algılandı")
    elif is_daily:
        st.info("📅 Günlük zaman serisi algılandı")
    else:
        st.warning("⚠️ Zaman frekansı net değil (düzensiz veri olabilir)")

    # UI’da sadece göstereceğiz (istersen üretiriz ama modele almayacağız)
    target = _detect_target_col(base_df, date_col)
    if target is None:
        st.info("Target otomatik bulunamadı (lag/roll için gerekli). Bu bölüm sadece analiz amaçlı.")
        target = None
    else:
        st.caption(f"📞 Otomatik seçilen çağrı kolonu: **{target}**")

    daily_map = {
        "Dün (lag 1)": "lag_1",
        "Geçen Hafta (lag 7)": "lag_7",
        "Geçen Ay (lag 30)": "lag_30",
        "7 Günlük Ortalama": "roll_7d",
        "30 Günlük Ortalama": "roll_30d",
    }
    slot_map = {
        "Son 6 Saat Ortalaması": "roll_6h",
        "Son 12 Saat Ortalaması": "roll_12h",
        "Son 24 Saat Ortalaması": "roll_24h",
        "Aynı Saat – Dün": "lag_48",
        "Aynı Saat – Geçen Hafta": "lag_336",
    }

    if is_daily:
        cols = st.columns(3)
        for i, (label, key) in enumerate(daily_map.items()):
            checked = key in st.session_state["cf_daily_features"]
            val = cols[i % 3].checkbox(label, value=checked, key=f"cf_daily_{key}_{nonce}")
            if val and key not in st.session_state["cf_daily_features"]:
                st.session_state["cf_daily_features"].append(key)
            if (not val) and key in st.session_state["cf_daily_features"]:
                st.session_state["cf_daily_features"].remove(key)

    if is_intraday:
        cols = st.columns(3)
        for i, (label, key) in enumerate(slot_map.items()):
            checked = key in st.session_state["cf_slot_features"]
            val = cols[i % 3].checkbox(label, value=checked, key=f"cf_intr_{key}_{nonce}")
            if val and key not in st.session_state["cf_slot_features"]:
                st.session_state["cf_slot_features"].append(key)
            if (not val) and key in st.session_state["cf_slot_features"]:
                st.session_state["cf_slot_features"].remove(key)

    st.caption("Not: Lag/Roll seçimleri analiz içindir. Model ekranında bu kolonları seçmezsen modele girmez.")

    # ----------------------------
    # PREVIEW: Seçimlere göre FE üret (pipeline)
    # ----------------------------
    fe_df, fe_meta = apply_feature_pipeline(
        df=base_df,
        date_col=date_col,
        selected_date_features=st.session_state["cf_selected_features"],
        selected_bank_features=st.session_state["cf_bank_features"],
        selected_daily_features=st.session_state["cf_daily_features"],
        selected_slot_features=st.session_state["cf_slot_features"],
        include_lag_roll=False,          # ✅ senin kuralın: modele giden FE’de lag/roll yok
        target_col_for_lag=target,       # include_lag_roll=False olduğu için zaten kullanılmayacak
    )

    # ----------------------------
    # APPLY (veri ekranına yansıt)
    # ----------------------------
    st.markdown("---")
    if st.button("✅ Uygula (Veri ekranına yansıt)"):
        st.session_state["cf_fe_df"] = fe_df
        st.session_state["cf_full_df"] = fe_df

        # ✅ Tahmin ekranı için meta kaydet
        st.session_state["cf_fe_meta"] = fe_meta

        st.success("Güncellemeler veri ekranına yansıtıldı.")
        st.rerun()

    st.markdown("---")
    st.subheader("🔎 Feature Sonrası Önizleme")
    st.dataframe(fe_df.head(50), use_container_width=True, hide_index=True)
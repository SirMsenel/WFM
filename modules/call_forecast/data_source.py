# modules/call_forecast/data_source.py
import pandas as pd
import requests
import streamlit as st

from .components import card_html

BACKEND = "http://127.0.0.1:8001"


def _ensure_state():
    st.session_state.setdefault("cf_meta", None)
    st.session_state.setdefault("cf_all_df", None)     # TAM veri (değişmez)
    st.session_state.setdefault("cf_full_df", None)    # AKTİF / işlenecek veri (scope + işlemler)
    st.session_state.setdefault("cf_raw_df", None)     # RAW veri (scope uygulanmış, FE öncesi)
    st.session_state.setdefault("cf_last_filename", None)
    st.session_state.setdefault("cf_source", "Excel/CSV (Yükle)")

    # ✅ scope state (ek; mimari bozmaz)
    st.session_state.setdefault("cf_scope_enabled", False)
    st.session_state.setdefault("cf_scope_date_col", None)
    st.session_state.setdefault("cf_scope_start", None)
    st.session_state.setdefault("cf_scope_end", None)
    st.session_state.setdefault("cf_scope_sig", ("ALL",))  # son uygulanan kapsam


def _backend_health_ok() -> bool:
    try:
        r = requests.get(f"{BACKEND}/health", timeout=5)
        return (r.status_code == 200 and r.json().get("ok") is True)
    except Exception:
        return False


def _upload_and_load_all(file_obj):
    files = {"file": (file_obj.name, file_obj.getvalue())}

    r = requests.post(f"{BACKEND}/data/upload", files=files, timeout=120)
    r.raise_for_status()
    meta = r.json()

    ra = requests.get(f"{BACKEND}/data/all", timeout=300)
    ra.raise_for_status()
    j = ra.json()
    full_df = pd.DataFrame(j.get("data", []))

    return meta, full_df


def _reset_all_call_forecast_state():
    # Veri anahtarlarına dokunma: cf_meta, cf_full_df, cf_raw_df, cf_last_filename, cf_source
    keys_to_clear = [
        # FE
        "cf_selected_features",
        "cf_bank_features",
        "cf_daily_features",
        "cf_slot_features",
        "cf_fe_df",

        # Outlier
        "cf_backup_df_outlier",
        "cf_changed_rows_outlier_old",

        # Monitoring (ileride)
        "cf_monitor_filters",

        # Alt ekran
        "cf_sub_page",

        # Missing data (data_quality)
        "cf_backup_df_missing",
        "cf_changed_rows_missing",
    ]
    for k in keys_to_clear:
        st.session_state.pop(k, None)

    # Checkbox widget key'leri temizle
    prefixes = ("cf_chk_", "cf_slot_", "cf_bank_", "cf_daily_", "cf_intr_")
    for k in list(st.session_state.keys()):
        if k.startswith(prefixes):
            st.session_state.pop(k, None)


def render():
    _ensure_state()

    st.subheader("Veri Yükleme ve Önizleme")

    # ----------------------------
    # Sidebar: backend kontrol + kaynak
    # ----------------------------
    with st.sidebar:
        st.subheader("Bağlantı")
        st.write("Backend:", BACKEND)

        backend_ok = _backend_health_ok()
        st.success("Backend OK ✅" if backend_ok else "Backend sorunlu ❌")

        st.divider()
        st.subheader("Veri Kaynağı")

        options = ["Excel/CSV (Yükle)", "DB (sonra)", "Genesys API (sonra)"]
        current = st.session_state.get("cf_source", options[0])
        idx = options.index(current) if current in options else 0

        source = st.radio("Seç", options, index=idx)
        st.session_state["cf_source"] = source

    if not backend_ok:
        st.warning("Önce backend çalışmalı (uvicorn).")
        st.stop()

    if source != "Excel/CSV (Yükle)":
        st.info("Şimdilik sadece Excel/CSV yükleme var. DB ve Genesys API sonraki adım.")
        st.stop()

    # ----------------------------
    # Upload
    # ----------------------------
    uploaded = st.file_uploader("CSV veya Excel yükle", type=["csv", "xlsx", "xls"])

    # Dosya seçilince otomatik yükle
    if uploaded is not None and uploaded.name != st.session_state.get("cf_last_filename"):
        try:
            _reset_all_call_forecast_state()

            meta, full_df = _upload_and_load_all(uploaded)

            st.session_state["cf_meta"] = meta
            st.session_state["cf_all_df"] = full_df
            st.session_state["cf_raw_df"] = full_df.copy()   # raw başlangıç
            st.session_state["cf_full_df"] = full_df.copy()  # aktif başlangıç
            st.session_state["cf_last_filename"] = uploaded.name

            # scope reset
            st.session_state["cf_scope_enabled"] = False
            st.session_state["cf_scope_date_col"] = None
            st.session_state["cf_scope_start"] = None
            st.session_state["cf_scope_end"] = None
            st.session_state["cf_scope_sig"] = ("ALL",)

            st.success("Dosya yüklendi ✅ (tüm veri yüklendi)")
            st.rerun()

        except Exception as e:
            st.error(f"Yükleme hatası: {e}")
            st.stop()

    # ⚠️ BU SATIRLAR DEĞİŞMEYECEK (isteğin buydu)
    meta = st.session_state.get("cf_meta")
    df_all = st.session_state.get("cf_all_df")
    df = st.session_state.get("cf_full_df")

    if meta is None or df is None or df_all is None:
        st.info("Bir dosya seçtiğinde otomatik yüklenip tüm veri alınacak.")
        st.stop()

    # ✅ aktif işlenecek veri
    active_df = st.session_state.get("cf_full_df")
    if not isinstance(active_df, pd.DataFrame) or active_df is None:
        active_df = df.copy()
        st.session_state["cf_full_df"] = active_df

    # ---------------------------------------------------------------------------------------------------
    # ✅ Tarihsel Kapsam (cf_raw_df günceller)
    # ---------------------------------------------------------------------------------------------------
    st.markdown("---")
    st.header("🗓️ İşlenecek Tarih Aralığı")

    # aday tarih kolonları
    candidate_cols = []
    for c in df.columns:
        cname = str(c).lower()
        if ("date" in cname) or ("tarih" in cname) or ("time" in cname) or ("zaman" in cname):
            candidate_cols.append(c)

    dt_like_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    for c in dt_like_cols:
        if c not in candidate_cols:
            candidate_cols.insert(0, c)

    colA, colB, colC, colD, colE = st.columns([2, 2, 2, 2, 2])

    with colA:
        scope_enabled = st.toggle(
            "Tarih aralığıyla sınırla",
            value=bool(st.session_state.get("cf_scope_enabled", False)),
            key="cf_scope_enabled",
        )

    if not scope_enabled:
        # Toggle kapalıysa -> ALL (sadece gerekiyorsa)
        if st.session_state.get("cf_scope_sig") != ("ALL",):
            _reset_all_call_forecast_state()
            st.session_state["cf_raw_df"] = df_all.copy()
            st.session_state["cf_full_df"] = df_all.copy()
            st.session_state["cf_scope_sig"] = ("ALL",)
            st.rerun()
        st.caption("Kapsam kapalı: tüm veri işlenecek.")
    else:
        if not candidate_cols:
            st.warning("Tarih kolonu bulunamadı. Tüm veriyle devam edilecek.")
        else:
            saved_col = st.session_state.get("cf_scope_date_col")
            if (saved_col is None) or (saved_col not in candidate_cols):
                saved_col = candidate_cols[0]
                st.session_state["cf_scope_date_col"] = saved_col

            with colB:
                date_col = st.selectbox(
                    "Tarih kolonu",
                    options=candidate_cols,
                    index=candidate_cols.index(saved_col) if saved_col in candidate_cols else 0,
                    key="cf_scope_date_col",
                )

            if (date_col is None) or (date_col not in df.columns):
                date_col = candidate_cols[0]
                st.session_state["cf_scope_date_col"] = date_col

            # kapsam her zaman tam veriye (df_all) göre hesaplanır
            dt_series = pd.to_datetime(df_all[date_col], errors="coerce")
            valid_dt = dt_series.dropna()

            if valid_dt.empty:
                st.warning("Seçilen tarih kolonunda parse edilebilir tarih bulunamadı. Tüm veriyle devam.")
            else:
                min_dt = valid_dt.min().date()
                max_dt = valid_dt.max().date()

                default_start = st.session_state.get("cf_scope_start") or min_dt
                default_end = st.session_state.get("cf_scope_end") or max_dt
                if default_start < min_dt:
                    default_start = min_dt
                if default_end > max_dt:
                    default_end = max_dt
                if default_end < default_start:
                    default_end = default_start

                with colC:
                    start_date = st.date_input(
                        "Başlangıç",
                        value=default_start,
                        min_value=min_dt,
                        max_value=max_dt,
                        key="cf_scope_start",
                    )
                with colD:
                    end_date = st.date_input(
                        "Bitiş",
                        value=default_end,
                        min_value=min_dt,
                        max_value=max_dt,
                        key="cf_scope_end",
                    )

                with colE:
                    apply = st.button("✅ Uygula", use_container_width=True)

                st.caption(f"Veri aralığı: **{min_dt} → {max_dt}**")

                if apply:
                    if end_date < start_date:
                        end_date = start_date
                        st.session_state["cf_scope_end"] = end_date

                    new_sig = ("RANGE", str(date_col), str(start_date), str(end_date))
                    if st.session_state.get("cf_scope_sig") != new_sig:
                        _reset_all_call_forecast_state()

                        dt_full = pd.to_datetime(df_all[date_col], errors="coerce")
                        start_ts = pd.Timestamp(start_date)
                        end_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)

                        mask = dt_full.between(start_ts, end_ts, inclusive="both")
                        filtered_df = df_all.loc[mask].copy()

                        st.session_state["cf_raw_df"] = filtered_df
                        st.session_state["cf_full_df"] = filtered_df.copy()
                        st.session_state["cf_scope_sig"] = new_sig

                    st.rerun()

    # ✅ rerun sonrası aktif_df’yi tekrar al
    active_df = st.session_state.get("cf_full_df")
    if not isinstance(active_df, pd.DataFrame) or active_df is None:
        active_df = df.copy()
        st.session_state["cf_full_df"] = active_df

    # küçük bilgi: full vs active
    st.info(f"Tam veri satır: **{len(df_all):,}** | İşlenecek satır: **{len(active_df):,}**")

    # ---------------------------------------------------------------------------------------------------
    # Temel Bilgiler ve Önizleme  (ARTIK active_df ÜZERİNDEN)
    # ---------------------------------------------------------------------------------------------------
    st.markdown("---")
    st.header("📋 Temel Bilgiler")

    rows = int(active_df.shape[0])
    cols = int(active_df.shape[1])
    total_cells = rows * cols

    total_cells_real = rows * cols if not active_df.empty else 0
    missing_count = int(active_df.isnull().sum().sum()) if total_cells_real else 0
    missing_percent = round((missing_count / total_cells_real) * 100, 2) if total_cells_real else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(card_html("#E5F8E0", "🧩 Toplam Veri (Hücre)", f"{total_cells:,}"), unsafe_allow_html=True)
    c2.markdown(card_html("#E8F0FE", "📄 Satır Sayısı", f"{rows:,}"), unsafe_allow_html=True)
    c3.markdown(card_html("#FFF4E5", "📊 Sütun Sayısı", f"{cols:,}"), unsafe_allow_html=True)
    c4.markdown(card_html("#FEE5E5", "⚠️ Eksik Hücre (%)", f"{missing_percent}%"), unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("🔢 Sütun Tipleri ve Benzersiz Değer Sayısı")

    column_summary = pd.DataFrame({
        "Toplam Değer": len(active_df),
        "Benzersiz Değer": active_df.nunique(),
        "Veri Tipi": active_df.dtypes.astype(str),
    }).reset_index().rename(columns={"index": "Sütun Adı"})

    def categorize_dtype(dtype, nunique):
        if pd.api.types.is_numeric_dtype(dtype):
            return "Sayısal"
        elif pd.api.types.is_string_dtype(dtype) or nunique < 20:
            return "Kategorik"
        else:
            return "Diğer"

    column_summary["Tür"] = column_summary.apply(
        lambda x: categorize_dtype(active_df[x["Sütun Adı"]].dtype, x["Benzersiz Değer"]),
        axis=1
    )
    st.dataframe(column_summary, use_container_width=True)

    st.markdown("---")
    st.subheader("🔍 Önizleme")

    search = st.text_input("🔎 İşlenecek veride ara (tüm kolonlarda)")
    view_df = active_df
    if search:
        s = search.lower()
        view_df = view_df[
            view_df.astype(str)
            .apply(lambda x: x.str.lower().str.contains(s, na=False))
            .any(axis=1)
        ]

    max_rows = len(view_df) if len(view_df) >= 1 else 1
    row_count = st.slider(
        "Kaç satır görmek istersiniz?",
        min_value=1,
        max_value=max_rows,
        value=min(10, max_rows),
    )

    st.caption(f"Filtreli kayıt sayısı: {len(view_df):,}")
    st.dataframe(view_df.head(int(row_count)), use_container_width=True, hide_index=True)
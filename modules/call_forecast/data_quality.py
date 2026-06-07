# modules/call_forecast/data_quality.py
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO


# ----------------------------
# Helpers
# ----------------------------
def _get_active_df() -> pd.DataFrame | None:
    df = st.session_state.get("cf_full_df")
    if df is None or not isinstance(df, pd.DataFrame):
        return None
    return df


def _highlight_missing(val):
    if pd.isnull(val):
        return "background-color: #ff8080; color: black;"
    return ""


def _guess_date_columns(df: pd.DataFrame) -> list[str]:
    cols: list[str] = []

    # 1) dtype datetime olanlar
    for c in df.columns:
        try:
            if np.issubdtype(df[c].dtype, np.datetime64):
                cols.append(c)
        except Exception:
            pass

    # 2) isimden tahmin
    name_hits = [
        c for c in df.columns
        if any(k in str(c).lower() for k in ["date", "tarih", "datetime", "timestamp", "zaman"])
    ]
    for c in name_hits:
        if c not in cols:
            cols.append(c)

    return cols


def _ensure_datetime_series(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")


def _build_expected_range(start_dt: pd.Timestamp, end_dt: pd.Timestamp, freq: str) -> pd.DatetimeIndex:
    # end dahil
    return pd.date_range(start=start_dt, end=end_dt, freq=freq)


def _missing_datetimes_for_df(df: pd.DataFrame, dt_col: str, start_dt: pd.Timestamp, end_dt: pd.Timestamp, freq: str) -> pd.DatetimeIndex:
    expected = _build_expected_range(start_dt, end_dt, freq)
    present = pd.DatetimeIndex(df[dt_col].dropna().unique())
    missing = expected.difference(present)
    return missing


def _append_missing_rows(
    df: pd.DataFrame,
    dt_col: str,
    missing_idx: pd.DatetimeIndex,
    group_vals: dict | None = None
) -> pd.DataFrame:
    if len(missing_idx) == 0:
        return df

    new_rows = pd.DataFrame({dt_col: missing_idx})
    if group_vals:
        for k, v in group_vals.items():
            new_rows[k] = v

    # diğer kolonlar NaN
    for c in df.columns:
        if c not in new_rows.columns:
            new_rows[c] = np.nan

    out = pd.concat([df, new_rows], ignore_index=True)
    return out


def _safe_sort(df: pd.DataFrame, sort_cols: list[str]) -> pd.DataFrame:
    # sort_cols içinde olmayanlar varsa ele
    cols = [c for c in sort_cols if c in df.columns]
    if not cols:
        return df
    return df.sort_values(cols)


# ----------------------------
# UI
# ----------------------------
def render():
    st.subheader("Eksik Veri İşleme")
    st.markdown("---")

    df = _get_active_df()
    if df is None:
        st.warning("⚠️ Önce veri yükleyin! (Veri Kaynağı ekranı)")
        return
    if df.empty:
        st.info("Veri boş görünüyor.")
        return

    df = df.copy()

    # =========================================================
    # 🗓️ Eksik Tarih / Timestamp Kontrolü (FORM + STATE)
    # =========================================================
    st.subheader("🗓️ Eksik Tarih / Timestamp Kontrolü")
    st.caption(
        "Seçtiğiniz tarih aralığında beklenen frekansta (günlük/saatlik/30dk vb.) eksik tarih var mı kontrol eder. "
        "İsterseniz eksik tarihleri satır olarak ekleyip opsiyonel doldurma uygular."
    )

    # sonuçları saklayacağımız state
    if "dq_missing_results" not in st.session_state:
        st.session_state["dq_missing_results"] = None
    if "dq_missing_meta" not in st.session_state:
        st.session_state["dq_missing_meta"] = None

    date_candidates = _guess_date_columns(df)
    if not date_candidates:
        st.info("Tarih/timestamp gibi görünen bir sütun otomatik bulunamadı. Yine de aşağıdan herhangi bir sütunu seçebilirsiniz.")
        date_candidates = list(df.columns)

    # >>> FORM BAŞI
    with st.form("dq_missing_date_form", clear_on_submit=False):
        cdt1, cdt2, cdt3 = st.columns([2, 1, 2])

        with cdt1:
            dt_col = st.selectbox("Tarih sütunu", date_candidates, index=0, key="dq_dt_col")

        # geçici datetime serisi
        tmp_dt = _ensure_datetime_series(df[dt_col])

        with cdt2:
            freq_label = st.selectbox(
                "Frekans",
                ["Günlük", "Saatlik", "30 Dakika", "15 Dakika"],
                index=0,
                key="dq_freq",
            )
            freq_map = {"Günlük": "D", "Saatlik": "H", "30 Dakika": "30min", "15 Dakika": "15min"}
            freq = freq_map[freq_label]

        min_dt = tmp_dt.min()
        max_dt = tmp_dt.max()

        with cdt3:
            if pd.isna(min_dt) or pd.isna(max_dt):
                st.warning("Seçilen sütun datetime'a çevrilemedi (tamamı boş/format bozuk olabilir).")
                start_date = None
                end_date = None
            else:
                start_date, end_date = st.date_input(
                    "Kontrol aralığı (başlangıç / bitiş)",
                    value=(min_dt.date(), max_dt.date()),
                    min_value=min_dt.date(),
                    max_value=max_dt.date(),
                    key="dq_date_range",
                )

        use_group = st.checkbox("Grup bazlı kontrol (örn. kuyruk/kanal/şube gibi)", value=False, key="dq_use_group")
        group_cols = []
        if use_group:
            group_cols = st.multiselect(
                "Grup sütunları",
                options=[c for c in df.columns if c != dt_col],
                default=[],
                key="dq_group_cols",
            )

        submit_check = st.form_submit_button("🔎 Eksik tarihleri kontrol et")

    # >>> FORM SONU

    # Kontrol işlemi sadece submit'e basınca çalışır
    if submit_check:
        if start_date is None or end_date is None:
            st.error("Kontrol aralığı seçilemedi. Tarih sütununu ve veriyi kontrol edin.")
            st.session_state["dq_missing_results"] = None
            st.session_state["dq_missing_meta"] = None
        else:
            start_dt = pd.Timestamp(start_date)
            end_dt = pd.Timestamp(end_date)

            if freq != "D":
                start_dt = start_dt.floor("D")
                end_dt = (pd.Timestamp(end_date) + pd.Timedelta(days=1)).floor("D") - pd.Timedelta(minutes=1)

            tmp = df.copy()
            tmp[dt_col] = tmp_dt

            results = []
            if not group_cols:
                missing = _missing_datetimes_for_df(tmp, dt_col, start_dt, end_dt, freq)
                results.append({"__group__": "Tümü", "missing": missing, "__gvals__": None})
            else:
                gb = tmp.groupby(group_cols, dropna=False)
                for gkey, gdf in gb:
                    missing = _missing_datetimes_for_df(gdf, dt_col, start_dt, end_dt, freq)
                    if not isinstance(gkey, tuple):
                        gkey = (gkey,)
                    group_name = " | ".join([f"{col}={val}" for col, val in zip(group_cols, gkey)])
                    results.append({"__group__": group_name, "missing": missing, "__gvals__": dict(zip(group_cols, gkey))})

            st.session_state["dq_missing_results"] = results
            st.session_state["dq_missing_meta"] = {
                "dt_col": dt_col,
                "group_cols": group_cols,
                "freq": freq,
                "start_dt": start_dt,
                "end_dt": end_dt,
            }

    # Sonuçlar state'den çizilir -> rerun olsa da kaybolmaz
    results = st.session_state.get("dq_missing_results")
    meta = st.session_state.get("dq_missing_meta")

    if results and meta:
        total_missing = int(sum(len(r["missing"]) for r in results))
        if total_missing == 0:
            st.success("✅ Seçilen aralıkta eksik tarih/timestamp yok.")
        else:
            st.warning(f"⚠️ Eksik tarih/timestamp bulundu: {total_missing:,}")

            rows = []
            for r in results:
                for m in r["missing"]:
                    rows.append({"Grup": r["__group__"], "Eksik_Tarih": m})
            miss_df = pd.DataFrame(rows).sort_values(["Grup", "Eksik_Tarih"])
            st.dataframe(miss_df, use_container_width=True, height=300)

            st.markdown("#### ➕ Eksik tarihleri satır olarak ekle")
            fill_mode = st.selectbox(
                "Eklenen satırlardaki diğer sütunlar nasıl dolsun?",
                [
                    "Boş bırak (NaN)",
                    "0 ile doldur (sayısal sütunlar)",
                    "Güne göre ortalama ile doldur (aynı haftanın günü)",
                ],
                index=0,
                key="dq_fill_mode",
            )

            if st.button("🚀 Eksik tarihleri ekle ve uygula", key="dq_apply_add_missing"):
                dt_col = meta["dt_col"]
                group_cols = meta["group_cols"]

                st.session_state["cf_backup_df_missing"] = df.copy()

                base = df.copy()
                base[dt_col] = _ensure_datetime_series(base[dt_col])

                out = base.copy()

                # eksik tarih satırlarını ekle
                if not group_cols:
                    out = _append_missing_rows(out, dt_col, results[0]["missing"], group_vals=None)
                else:
                    for r in results:
                        if len(r["missing"]) > 0:
                            out = _append_missing_rows(out, dt_col, r["missing"], group_vals=r.get("__gvals__"))

                sort_cols = (group_cols + [dt_col]) if group_cols else [dt_col]
                out = _safe_sort(out, sort_cols).reset_index(drop=True)

                # -------------------------
                # DOLDURMA STRATEJİLERİ
                # -------------------------
                if fill_mode == "0 ile doldur (sayısal sütunlar)":
                    num_cols = out.select_dtypes(include=[np.number]).columns.tolist()
                    if num_cols:
                        out[num_cols] = out[num_cols].fillna(0)

                elif fill_mode == "Güne göre ortalama ile doldur (aynı haftanın günü)":
                    # dt_col datetime garanti
                    out[dt_col] = pd.to_datetime(out[dt_col], errors="coerce")

                    # haftanın günü (0=Pzt, ..., 6=Paz)
                    out["_dq_dow_"] = out[dt_col].dt.dayofweek

                    # grup anahtarı
                    key_cols = (group_cols + ["_dq_dow_"]) if group_cols else ["_dq_dow_"]

                    # sayısal kolonları aynı gün/grup ortalaması ile doldur
                    num_cols = out.select_dtypes(include=[np.number]).columns.tolist()
                    for c in num_cols:
                        mean_by_day = out.groupby(key_cols, dropna=False)[c].transform("mean")
                        out[c] = out[c].fillna(mean_by_day)

                    # opsiyonel: kategorik kolonları aynı gün/grup MODE ile doldur
                    obj_cols = [
                        c for c in out.columns
                        if c not in num_cols and c not in key_cols and c != dt_col
                    ]

                    def _mode_or_nan(x: pd.Series):
                        m = x.mode(dropna=True)
                        return m.iloc[0] if not m.empty else np.nan

                    for c in obj_cols:
                        mode_by_day = out.groupby(key_cols, dropna=False)[c].transform(_mode_or_nan)
                        out[c] = out[c].fillna(mode_by_day)

                    out.drop(columns=["_dq_dow_"], inplace=True, errors="ignore")

                st.session_state["cf_full_df"] = out
                st.success("✅ Eksik tarihler eklendi ve veri güncellendi.")
                st.rerun()

            st.markdown("---")

            # tmp temizle (render akışını bozmasın)
            df.drop(columns=["_tmp_dt_"], inplace=True, errors="ignore")
    # =========================================================
    # Mevcut: Eksik Veri (Hücre Bazlı) Özeti
    # =========================================================
    missing_summary = df.isnull().sum()
    missing_summary = missing_summary[missing_summary > 0]

    # Eğer eksik veri yoksa: Undo yine görünsün
    if missing_summary.empty:
        st.success("✅ Veri setinde eksik değer bulunmamaktadır. İşleme gerek yok.")

        # Undo
        if "cf_backup_df_missing" in st.session_state:
            if st.button("↩️ İşlemi Geri Al", key="dq_undo_when_no_missing"):
                backup = st.session_state.get("cf_backup_df_missing")
                if isinstance(backup, pd.DataFrame):
                    st.session_state["cf_full_df"] = backup
                st.session_state.pop("cf_backup_df_missing", None)
                st.session_state.pop("cf_changed_rows_missing", None)
                st.success("✅ İşlem geri alındı, veri seti önceki haline döndü.")
                st.rerun()
        return

    summary_df = pd.DataFrame({
        "Sütun": missing_summary.index,
        "Eksik Sayısı": missing_summary.values,
        "Oran (%)": np.round((missing_summary.values / len(df)) * 100, 2),
        "Veri Tipi": [df[col].dtype for col in missing_summary.index],
    })

    # --- Özet tablo
    st.subheader("📊 Eksik Veri Özeti")
    st.dataframe(summary_df, use_container_width=True)
    st.markdown("---")

    # --- Eksik içeren satırlar
    st.subheader("🔍 Eksik Veri İçeren Satırlar")
    missing_rows = df[df.isnull().any(axis=1)]
    if not missing_rows.empty:
        st.dataframe(
            missing_rows.style.applymap(_highlight_missing),
            use_container_width=True,
            height=400,
        )
        st.caption(f"🧩 Toplam {len(missing_rows):,} satırda eksik veri var.")
    else:
        st.success("✅ Veri setinde eksik değer bulunmamaktadır.")

    st.markdown("---")

    # --- Görseller (seaborn yok, matplotlib)
    st.subheader("⚠️ Eksik Veri Durumu")
    missing_per_column = df.isnull().sum()
    missing_per_column = missing_per_column[missing_per_column > 0]

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📊 Sütun Bazlı Eksik Veri")
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.bar(missing_per_column.index.astype(str), missing_per_column.values)
        ax.set_ylabel("Eksik Hücre Sayısı")
        ax.set_xlabel("Sütunlar")
        ax.tick_params(axis="x", rotation=45)
        for i, v in enumerate(missing_per_column.values):
            ax.text(i, v, str(int(v)), ha="center", va="bottom")
        st.pyplot(fig)

    with col2:
        st.markdown("### 🥧 Genel Eksik / Dolu Hücre Oranı")
        total_cells = int(df.shape[0] * df.shape[1])
        missing_count = int(df.isnull().sum().sum())
        filled_count = total_cells - missing_count

        if missing_count == 0:
            st.info("✅ Veri setinde eksik hücre yok.")
        else:
            fig2, ax2 = plt.subplots(figsize=(10, 5.1))
            ax2.pie(
                [filled_count, missing_count],
                labels=["Dolu Hücre", "Eksik Hücre"],
                autopct=lambda p: f"{p:.1f}%\n({int(p * total_cells / 100)})",
                startangle=90,
                textprops={"color": "black", "fontsize": 12},
            )
            ax2.axis("equal")
            st.pyplot(fig2)

    st.markdown("---")

    # --- İşlem seçimi
    st.subheader("⚙️ İşlem Türü Seçimi")
    islem = st.radio(
        "Ne yapmak istersiniz?",
        ["Eksik Veriyi Doldur", "Eksik Veriyi Sil"],
        horizontal=True,
    )
    st.markdown("---")

    # ---------------------- #
    # --- DOLDURMA BLOĞU --- #
    # ---------------------- #
    if islem == "Eksik Veriyi Doldur":
        st.subheader("🧠 Eksik Veriyi Doldurma")
        st.info("Gerekmedikçe 'Tümü' seçeneğini kullanmayın")

        c1, c2 = st.columns(2)
        with c1:
            secilen_sutun = st.selectbox("Sütun Seçin", ["Tümü"] + list(missing_summary.index))

        if secilen_sutun == "Tümü":
            yontem_options = ["Mod (mode)", "Sabit Değer Gir", "Ortalama (mean)", "Medyan (median)"]
        else:
            dtype = df[secilen_sutun].dtype
            if np.issubdtype(dtype, np.number):
                yontem_options = ["Ortalama (mean)", "Medyan (median)", "Mod (mode)", "Sabit Değer Gir"]
            else:
                yontem_options = ["Mod (mode)", "Sabit Değer Gir"]

        with c2:
            yontem = st.selectbox("Doldurma Yöntemi", yontem_options)

        sabit_deger = None
        if yontem == "Sabit Değer Gir":
            sabit_deger = st.text_input("Sabit değeri girin")

        if st.button("🚀 Doldurmayı Uygula"):
            st.session_state["cf_backup_df_missing"] = df.copy()

            df_filled = df.copy()
            target_cols = list(missing_summary.index) if secilen_sutun == "Tümü" else [secilen_sutun]

            doldurulan = 0
            changed_idx = set()

            for col in target_cols:
                if df_filled[col].isnull().sum() == 0:
                    continue

                missing_idx = df_filled[df_filled[col].isnull()].index
                if len(missing_idx) == 0:
                    continue

                is_numeric = np.issubdtype(df_filled[col].dtype, np.number)

                if yontem == "Ortalama (mean)" and is_numeric:
                    df_filled.loc[missing_idx, col] = pd.to_numeric(df_filled[col], errors="coerce").mean()

                elif yontem == "Medyan (median)" and is_numeric:
                    df_filled.loc[missing_idx, col] = pd.to_numeric(df_filled[col], errors="coerce").median()

                elif yontem == "Mod (mode)":
                    mode_val = df_filled[col].mode()
                    if not mode_val.empty:
                        df_filled.loc[missing_idx, col] = mode_val.iloc[0]

                elif yontem == "Sabit Değer Gir" and (sabit_deger is not None and sabit_deger != ""):
                    if is_numeric:
                        try:
                            sab = float(sabit_deger)
                        except Exception:
                            sab = np.nan
                        df_filled.loc[missing_idx, col] = sab
                    else:
                        df_filled.loc[missing_idx, col] = sabit_deger

                doldurulan += len(missing_idx)
                changed_idx.update(list(missing_idx))

            changed_old = df.loc[df.index.intersection(pd.Index(changed_idx))].copy()
            st.session_state["cf_changed_rows_missing"] = changed_old

            st.session_state["cf_full_df"] = df_filled

            st.success(f"✅ Doldurma tamamlandı. {doldurulan:,} hücre dolduruldu.")
            st.rerun()

    # -------------------- #
    # --- SİLME BLOĞU --- #
    # -------------------- #
    else:
        st.subheader("🗑️ Eksik Veriyi Silme")

        silme_turu = st.radio(
            "Silme yöntemi seçin:",
            [
                "Eksik değer içeren satırları sil",
                "Eksik değer içeren sütunları sil",
                "Seçili sütundaki eksik satırları sil",
            ],
        )

        secilen_sutun = None
        if silme_turu == "Seçili sütundaki eksik satırları sil":
            secilen_sutun = st.selectbox("Sütun seçin", list(missing_summary.index))

        if st.button("🚀 Silme İşlemini Uygula"):
            st.session_state["cf_backup_df_missing"] = df.copy()

            df_sil = df.copy()
            degisen_satirlar = pd.DataFrame()

            if silme_turu == "Eksik değer içeren satırları sil":
                missing_idx = df_sil[df_sil.isnull().any(axis=1)].index
                degisen_satirlar = df_sil.loc[missing_idx].copy()
                df_sil = df_sil.dropna()

            elif silme_turu == "Eksik değer içeren sütunları sil":
                cols_to_drop = df_sil.columns[df_sil.isnull().any()].tolist()
                degisen_satirlar = df_sil[cols_to_drop].copy()
                df_sil = df_sil.drop(columns=cols_to_drop)

            elif secilen_sutun:
                missing_idx = df_sil[df_sil[secilen_sutun].isnull()].index
                degisen_satirlar = df_sil.loc[missing_idx].copy()
                df_sil = df_sil[df_sil[secilen_sutun].notnull()].copy()

            st.session_state["cf_changed_rows_missing"] = degisen_satirlar
            st.session_state["cf_full_df"] = df_sil

            st.success("✅ Silme işlemi tamamlandı.")
            st.rerun()

    st.markdown("---")

    # --- Değişiklik göster (eski / yeni)
    if "cf_changed_rows_missing" in st.session_state:
        old_df = st.session_state.get("cf_changed_rows_missing")
        if isinstance(old_df, pd.DataFrame) and (not old_df.empty):
            st.subheader("🔍 Değişiklik Yapılan Satırlar (Eski / Yeni)")

            new_df = st.session_state["cf_full_df"].copy()

            common_idx = old_df.index.intersection(new_df.index)

            eski = old_df.loc[common_idx].copy()

            common_cols = [c for c in eski.columns if c in new_df.columns]
            yeni = new_df.loc[common_idx, common_cols].copy()
            eski = eski[common_cols].copy()

            degisen_full = pd.concat(
                [eski.add_prefix("Eski_"), yeni.add_prefix("Yeni_")],
                axis=1,
            )
            st.dataframe(degisen_full, use_container_width=True, height=300)

    # --- Undo
    if "cf_backup_df_missing" in st.session_state:
        if st.button("↩️ İşlemi Geri Al"):
            backup = st.session_state.get("cf_backup_df_missing")
            if isinstance(backup, pd.DataFrame):
                st.session_state["cf_full_df"] = backup
            st.session_state.pop("cf_backup_df_missing", None)
            st.session_state.pop("cf_changed_rows_missing", None)
            st.success("✅ İşlem geri alındı.")
            st.rerun()
# modules/call_forecast/outlier_iqr.py
import streamlit as st
import pandas as pd
import numpy as np


# ----------------------------
# Helpers
# ----------------------------
def _get_active_df() -> pd.DataFrame | None:
    df = st.session_state.get("cf_full_df")
    if df is None:
        return None
    if not isinstance(df, pd.DataFrame):
        return None
    if df.empty:
        return df
    return df


def _detect_outliers_iqr(series: pd.Series, factor_low: float = 1.5, factor_high: float = 1.5):
    """
    Alt/üst sınırlar için ayrı IQR çarpanları:
      lower = Q1 - factor_low * IQR
      upper = Q3 + factor_high * IQR
    """
    s = pd.to_numeric(series, errors="coerce")
    q1 = s.quantile(0.25)
    q3 = s.quantile(0.75)
    iqr = q3 - q1

    # iqr=0 ise sınırlar q1=q3 olur, outlier boş çıkar (doğru davranış)
    lower = q1 - factor_low * iqr
    upper = q3 + factor_high * iqr

    mask = (s < lower) | (s > upper)
    return mask.fillna(False), float(lower), float(upper)


def _build_group_key(df: pd.DataFrame, group_cols: list[str]) -> pd.Series:
    # Tuple key -> string key (stabil)
    if not group_cols:
        return pd.Series(["Tümü"] * len(df), index=df.index, dtype="object")

    # tek kolon ise direkt stringe çevir
    if len(group_cols) == 1:
        return df[group_cols[0]].astype(str)

    # çoklu kolon -> "a | b | c"
    return df[group_cols].astype(str).agg(" | ".join, axis=1)


def _compute_bounds(
    df: pd.DataFrame,
    value_col: str,
    group_cols: list[str],
    factor_low: float,
    factor_high: float,
):
    """
    returns:
      bounds_df: columns = ["Grup", "Alt Sınır", "Üst Sınır", "N"]
      bounds_map: dict[group_key_str] = (lower, upper)
    """
    bounds_rows = []
    bounds_map = {}

    if not group_cols:
        mask, lower, upper = _detect_outliers_iqr(df[value_col], factor_low=factor_low, factor_high=factor_high)
        bounds_rows.append(["Tümü", lower, upper, int(df[value_col].notna().sum())])
        bounds_map["Tümü"] = (lower, upper)
        return pd.DataFrame(bounds_rows, columns=["Grup", "Alt Sınır", "Üst Sınır", "N"]), bounds_map

    group_key = _build_group_key(df, group_cols)
    tmp = df.copy()
    tmp["_grp_key"] = group_key

    for g, gdf in tmp.groupby("_grp_key", dropna=False):
        mask, lower, upper = _detect_outliers_iqr(gdf[value_col], factor_low=factor_low, factor_high=factor_high)
        n = int(pd.to_numeric(gdf[value_col], errors="coerce").notna().sum())
        bounds_rows.append([str(g), lower, upper, n])
        bounds_map[str(g)] = (lower, upper)

    bounds_df = pd.DataFrame(bounds_rows, columns=["Grup", "Alt Sınır", "Üst Sınır", "N"])
    return bounds_df, bounds_map


def _compute_outlier_index(
    df: pd.DataFrame,
    value_col: str,
    group_cols: list[str],
    bounds_map: dict,
):
    if df.empty:
        return pd.Index([])

    s = pd.to_numeric(df[value_col], errors="coerce")
    if not group_cols:
        lower, upper = bounds_map["Tümü"]
        mask = (s < lower) | (s > upper)
        return df.index[mask.fillna(False)]

    grp = _build_group_key(df, group_cols)
    lowers = grp.map(lambda g: bounds_map.get(str(g), (np.nan, np.nan))[0]).astype(float)
    uppers = grp.map(lambda g: bounds_map.get(str(g), (np.nan, np.nan))[1]).astype(float)
    mask = (s < lowers) | (s > uppers)
    return df.index[mask.fillna(False)]


def _apply_action(
    df: pd.DataFrame,
    value_col: str,
    group_cols: list[str],
    action: str,
    outlier_idx: pd.Index,
    bounds_map: dict,
):
    df_updated = df.copy()

    if outlier_idx.empty:
        return df_updated

    # yardımcı: grup anahtarı
    grp = _build_group_key(df_updated, group_cols) if group_cols else pd.Series(["Tümü"] * len(df_updated), index=df_updated.index)

    s = pd.to_numeric(df_updated[value_col], errors="coerce")

    if action == "Alt/Üst sınıra eşitle":
        if not group_cols:
            lower, upper = bounds_map["Tümü"]
            df_updated.loc[outlier_idx, value_col] = s.loc[outlier_idx].clip(lower, upper)
        else:
            # grup bazlı clip
            lowers = grp.map(lambda g: bounds_map.get(str(g), (np.nan, np.nan))[0]).astype(float)
            uppers = grp.map(lambda g: bounds_map.get(str(g), (np.nan, np.nan))[1]).astype(float)
            df_updated.loc[outlier_idx, value_col] = s.loc[outlier_idx].clip(lowers.loc[outlier_idx], uppers.loc[outlier_idx])

    elif action == "Satırı Sil":
        df_updated = df_updated.drop(index=outlier_idx, errors="ignore")

    elif action in ("Ortalama ile doldur", "Medyan ile doldur", "Mod ile doldur"):
        # daha iyi: grup varsa grup istatistiği, yoksa global
        if not group_cols:
            if action == "Ortalama ile doldur":
                fill_val = float(pd.to_numeric(df[value_col], errors="coerce").mean())
                df_updated.loc[outlier_idx, value_col] = fill_val
            elif action == "Medyan ile doldur":
                fill_val = float(pd.to_numeric(df[value_col], errors="coerce").median())
                df_updated.loc[outlier_idx, value_col] = fill_val
            else:  # mod
                m = pd.to_numeric(df[value_col], errors="coerce").mode()
                fill_val = float(m.iloc[0]) if not m.empty else np.nan
                df_updated.loc[outlier_idx, value_col] = fill_val
        else:
            df_updated["_grp_key"] = grp.astype(str)

            if action == "Ortalama ile doldur":
                stats = df_updated.groupby("_grp_key")[value_col].apply(lambda x: pd.to_numeric(x, errors="coerce").mean())
            elif action == "Medyan ile doldur":
                stats = df_updated.groupby("_grp_key")[value_col].apply(lambda x: pd.to_numeric(x, errors="coerce").median())
            else:
                def _mode_one(x):
                    m = pd.to_numeric(x, errors="coerce").mode()
                    return m.iloc[0] if not m.empty else np.nan
                stats = df_updated.groupby("_grp_key")[value_col].apply(_mode_one)

            fill_series = df_updated.loc[outlier_idx, "_grp_key"].map(stats)
            df_updated.loc[outlier_idx, value_col] = fill_series.values
            df_updated.drop(columns=["_grp_key"], inplace=True, errors="ignore")

    elif action == "Aykırı değer sütunu ekle (0/1 işaretleme)":
        col_name = f"Aykiri_{value_col}"
        if col_name not in df_updated.columns:
            df_updated[col_name] = 0
        df_updated.loc[outlier_idx, col_name] = 1

    return df_updated


# ----------------------------
# UI
# ----------------------------
def render():
    st.subheader(" Aykırı Değer Tespiti ve İşleme")
    st.markdown("---")

    df = _get_active_df()
    if df is None:
        st.warning("⚠️ Önce veri yükleyin! (Veri Kaynağı ekranı)")
        return
    if df.empty:
        st.info("Veri boş görünüyor.")
        return

    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    if not numeric_cols:
        st.info("✅ Veri setinde sayısal sütun bulunmamaktadır.")
        return

    col1, col2 = st.columns(2)
    with col1:
        secilen_sutun = st.selectbox("Aykırı değer tespiti için sütun seçin", numeric_cols)
    with col2:
        grup_sutunlar = st.multiselect("Opsiyonel: Gruplama sütun(ları) seçin", df.columns.tolist())

    # ✅ Alt/Üst için ayrı IQR barları
    s1, s2 = st.columns(2)
    with s1:
        iqr_factor_low = st.slider(
            "Alt Sınır IQR Çarpanı (Q1 - k*IQR)",
            min_value=0.5,
            max_value=3.0,
            value=1.5,
            step=0.1,
        )
    with s2:
        iqr_factor_high = st.slider(
            "Üst Sınır IQR Çarpanı (Q3 + k*IQR)",
            min_value=0.5,
            max_value=3.0,
            value=1.5,
            step=0.1,
        )

    st.markdown("---")

    # bounds + outliers
    alt_ust_df, bounds_map = _compute_bounds(
        df=df,
        value_col=secilen_sutun,
        group_cols=grup_sutunlar,
        factor_low=iqr_factor_low,
        factor_high=iqr_factor_high,
    )
    outlier_idx = _compute_outlier_index(
        df=df,
        value_col=secilen_sutun,
        group_cols=grup_sutunlar,
        bounds_map=bounds_map,
    )
    aykiri_df = df.loc[outlier_idx].copy() if len(outlier_idx) else pd.DataFrame()

    st.subheader("📋 Alt/Üst Sınır Tablosu")
    st.dataframe(alt_ust_df, use_container_width=True)
    st.markdown("---")

    st.subheader("⚠️ Aykırı Değerler")
    if aykiri_df.empty:
        st.success("✅ Seçilen sütunda aykırı değer bulunmamaktadır.")
    else:
        st.dataframe(aykiri_df, use_container_width=True, height=400)
        st.info(f"Toplam {len(aykiri_df):,} aykırı değer bulundu.")

    st.markdown("---")
    st.subheader("🛠️ Aykırı Değer İşlemleri")

    action = st.radio(
        "Seçilen aykırı değerler için işlem seçin (tek seçim):",
        [
            "Alt/Üst sınıra eşitle",
            "Satırı Sil",
            "Ortalama ile doldur",
            "Medyan ile doldur",
            "Mod ile doldur",
            "Aykırı değer sütunu ekle (0/1 işaretleme)",
        ],
    )

    # Apply
    if st.button("🚀 İşlemi Uygula", disabled=aykiri_df.empty):
        # backup
        st.session_state["cf_backup_df_outlier"] = df.copy()
        st.session_state["cf_changed_rows_outlier_old"] = aykiri_df.copy()

        df_updated = _apply_action(
            df=df,
            value_col=secilen_sutun,
            group_cols=grup_sutunlar,
            action=action,
            outlier_idx=outlier_idx,
            bounds_map=bounds_map,
        )

        # ✅ tüm uygulamada veri güncellensin
        st.session_state["cf_full_df"] = df_updated
        st.session_state["cf_fe_df"] = df_updated  # varsa pipeline için de güncel kalsın

        st.success("✅ İşlem uygulandı ve veri güncellendi.")
        st.rerun()

    # Değişiklik tablosu
    if "cf_changed_rows_outlier_old" in st.session_state:
        old_df = st.session_state.get("cf_changed_rows_outlier_old")
        if isinstance(old_df, pd.DataFrame) and (not old_df.empty):
            st.markdown("---")
            st.subheader("🔍 Değişiklik Yapılan Satırlar (Eski / Yeni)")

            new_df = st.session_state["cf_full_df"].copy()

            # satırlar silinmiş olabilir -> intersection
            common_idx = old_df.index.intersection(new_df.index)

            if common_idx.empty:
                st.warning("Değişen satırlar yeni veride bulunamadı (satırlar silinmiş olabilir).")
            else:
                # ✅ kolonlar uyuşmayabilir -> intersection (KeyError fix)
                common_cols = [c for c in old_df.columns if c in new_df.columns]

                if not common_cols:
                    st.warning("Karşılaştırılacak ortak kolon bulunamadı (yeni veride kolonlar değişmiş olabilir).")
                else:
                    eski = old_df.loc[common_idx, common_cols].copy()
                    yeni = new_df.loc[common_idx, common_cols].copy()

                    degisen_full = pd.concat(
                        [eski.add_prefix("Eski_"), yeni.add_prefix("Yeni_")],
                        axis=1,
                    )
                    st.dataframe(degisen_full, use_container_width=True, height=300)

                    missing_cols = [c for c in old_df.columns if c not in new_df.columns]
                    if missing_cols:
                        st.caption(f"Not: {len(missing_cols)} kolon yeni veride olmadığı için karşılaştırmaya eklenmedi.")

    # Undo
    if "cf_backup_df_outlier" in st.session_state:
        st.markdown("---")
        if st.button("↩️ İşlemi Geri Al"):
            backup = st.session_state.get("cf_backup_df_outlier")
            if isinstance(backup, pd.DataFrame):
                st.session_state["cf_full_df"] = backup
                st.session_state["cf_fe_df"] = backup
            st.session_state.pop("cf_backup_df_outlier", None)
            st.session_state.pop("cf_changed_rows_outlier_old", None)
            st.success("✅ Geri alındı.")
            st.rerun()
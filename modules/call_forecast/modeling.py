# modules/call_forecast/modeling.py
import numpy as np
import pandas as pd
import streamlit as st

from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler

from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Opsiyonel paketler (yoksa uygulama çökmesin)
try:
    from xgboost import XGBRegressor
    _HAS_XGB = True
except Exception:
    XGBRegressor = None
    _HAS_XGB = False

try:
    from lightgbm import LGBMRegressor
    _HAS_LGBM = True
except Exception:
    LGBMRegressor = None
    _HAS_LGBM = False


# ----------------------------
# Helpers
# ----------------------------
def _get_active_df() -> pd.DataFrame | None:
    df = st.session_state.get("cf_full_df")
    if df is None or not isinstance(df, pd.DataFrame):
        return None
    return df


def _detect_date_col(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        parsed = pd.to_datetime(df[col], errors="coerce")
        if parsed.notna().mean() > 0.8:
            return col
    return None


def _candidate_numeric_cols(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include=["int64", "float64", "int32", "float32"]).columns.tolist()


def _safe_rmse(y_true, y_pred) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def _scale_if_needed(X_train, X_test, normalize: bool):
    if not normalize:
        st.session_state.pop("cf_scaler_mean_", None)
        st.session_state.pop("cf_scaler_scale_", None)
        return X_train, X_test, None

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # scaler paramlarını kaydet
    st.session_state["cf_scaler_mean_"] = getattr(scaler, "mean_", None)
    st.session_state["cf_scaler_scale_"] = getattr(scaler, "scale_", None)
    return X_train_scaled, X_test_scaled, scaler


def _is_lag_roll_col(col: str) -> bool:
    c = str(col).lower()
    return c.startswith("lag_") or c.startswith("roll_")


def _default_feature_selection(feature_candidates: list[str]) -> list[str]:
    # Senin kuralın: lag/roll modele girmesin (analizde kalsın)
    return [c for c in feature_candidates if not _is_lag_roll_col(c)]


# ----------------------------
# UI
# ----------------------------
def render():
    st.subheader("Model Kur & Değerlendir")
    st.markdown("---")

    df = _get_active_df()
    if df is None or df.empty:
        st.warning("Önce Veri Kaynağı ekranından veri yükleyin.")
        return

    df = df.copy()

    # ------------------ Target & Feature Seçimi ------------------
    numeric_cols = _candidate_numeric_cols(df)
    if not numeric_cols:
        st.error("Veride sayısal kolon yok. Model kurmak için en az 1 sayısal target gerekir.")
        return

    # --- TARGET ---
    st.markdown("##### 1️⃣ Tahmin Edilecek Değişken (Target)")
    target = st.selectbox(
        "Sayısal bir kolon seçin",
        options=[None] + numeric_cols,
        key="cf_model_target"
    )
    if target is None:
        st.info("Model kurmak için önce bir hedef değişken seçmelisiniz.")
        st.info("Çağrı Tahmini ise Çağrı Sayısını seçiniz.")
        return

    # --- FEATURE ---
    st.markdown("---")
    st.markdown("##### 2️⃣ Bağımsız Değişkenler (Features)")
    feature_candidates = [c for c in df.columns if c != target]

    default_feats = _default_feature_selection(feature_candidates)

    features = st.multiselect(
        "Modele dahil edilecek kolonlar",
        options=feature_candidates,
        default=default_feats,
        key="cf_model_features"
    )

    if not features:
        st.warning("En az 1 bağımsız değişken seçmelisiniz.")
        return

    st.caption(
        "ℹ️ Not: Kategorik değişkenler otomatik olarak dummy (one-hot) yapılır. "
        "Zaman serisi algılanırsa veri sırası korunarak train/test bölünür.\n\n"
        "⚠️ Not2: lag_ / roll_ kolonları (varsa) default olarak seçili gelmez (analiz için var)."
    )

    # ------------------ Zaman Serisi Tarih Kontrolü ------------------
    auto_date = _detect_date_col(df)
    is_time_series = auto_date is not None

    if is_time_series:
        st.info(f"⏱️ Zaman serisi algılandı → {auto_date}")

        if auto_date in features:
            st.error(
                f"""
❌ Tarih sütunu (**{auto_date}**) bağımsız değişken olarak seçildi.

Zaman serisi modellerinde tarih sütunu doğrudan modele verilmez.
Lütfen:
• Tarih kolonunu X listesinden çıkarın
• Feature Engineering ekranında üretilen yıl/ay/gün/saat gibi kolonları kullanın
"""
            )
            st.stop()

    # ------------------ Dummy Encoding ------------------
    # drop_first=False → SHAP uyumu
    X = pd.get_dummies(df[features], drop_first=False)
    y = df[target]

    # Eksik veri kontrolü
    if X.isnull().sum().sum() > 0 or y.isnull().sum() > 0:
        st.error("⚠️ Eksik veri bulundu → 'Eksik Veri İşleme' ekranında düzeltin.")
        return

    # ------------------ Train / Test Bölme ------------------
    st.markdown("---")
    st.subheader("🧩 Train / Test Bölme")

    # ✅ Pending slider sync: slider yaratılmadan önce state güncelle
    pending = st.session_state.get("cf_test_size_pct_pending")
    if pending is not None:
        try:
            pending_int = int(pending)
        except Exception:
            pending_int = None

        if pending_int is not None:
            pending_int = max(5, min(50, pending_int))
            st.session_state["cf_test_size_pct"] = pending_int

        st.session_state["cf_test_size_pct_pending"] = None

    # ✅ slider artık session_state ile senkronlanabilir
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        test_size_pct = st.slider(
            "Test oranı (%)",
            5, 50,
            int(st.session_state.get("cf_test_size_pct", 20)),
            key="cf_test_size_pct",
        )
        test_size = test_size_pct / 100
    with c2:
        normalize_data = st.checkbox("🔄 StandardScaler ile ölçekle", True)
    with c3:
        use_time_split = st.checkbox(
            "⏱️ Zaman serisi split (shuffle kapalı)",
            value=is_time_series,
            disabled=not is_time_series
        )

    if use_time_split:
        date_col = auto_date
        st.info(f"Zaman serisi split → **{date_col}** (veri sırası bozulmadan bölünecek)")

        df_sorted = df.copy()
        df_sorted[date_col] = pd.to_datetime(df_sorted[date_col], errors="coerce")
        df_sorted = df_sorted[df_sorted[date_col].notna()].sort_values(date_col)

        # ✅ Yeni: kullanıcı isterse tarih aralığı ile train/test ayırsın
        min_dt = df_sorted[date_col].min()
        max_dt = df_sorted[date_col].max()
        min_d = min_dt.date()
        max_d = max_dt.date()

        use_date_range_split = st.checkbox(
            "📅 Tarih aralığı seçerek ayır",
            value=False,
            help="Açıksa train/test aralıklarını sen seçersin. Kapalıysa yüzdelik orana göre bölünür.",
            key="cf_use_date_range_split",
        )

        if use_date_range_split:
            # Default: slider ile uyumlu kırılım
            split_index_default = int(len(df_sorted) * (1 - test_size))
            split_index_default = max(1, min(split_index_default, len(df_sorted) - 1))
            default_train_end = df_sorted.iloc[split_index_default - 1][date_col].date()
            default_test_start = df_sorted.iloc[split_index_default][date_col].date()

            cdt1, cdt2 = st.columns(2)
            with cdt1:
                train_range = st.date_input(
                    "Train tarih aralığı",
                    value=(min_d, default_train_end),
                    min_value=min_d,
                    max_value=max_d,
                    key="cf_train_date_range",
                )
            with cdt2:
                test_range = st.date_input(
                    "Test tarih aralığı",
                    value=(default_test_start, max_d),
                    min_value=min_d,
                    max_value=max_d,
                    key="cf_test_date_range",
                )

            # date_input tuple gelmeyebilir; güvenli parse
            if isinstance(train_range, (list, tuple)) and len(train_range) == 2:
                tr_start, tr_end = train_range
            else:
                tr_start, tr_end = min_d, default_train_end

            if isinstance(test_range, (list, tuple)) and len(test_range) == 2:
                te_start, te_end = test_range
            else:
                te_start, te_end = default_test_start, max_d

            # Validasyon
            if tr_start > tr_end:
                st.error("❌ Train aralığında başlangıç tarihi, bitiş tarihinden büyük olamaz.")
                st.stop()
            if te_start > te_end:
                st.error("❌ Test aralığında başlangıç tarihi, bitiş tarihinden büyük olamaz.")
                st.stop()

            tr_start_ts = pd.to_datetime(tr_start)
            tr_end_ts = pd.to_datetime(tr_end) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
            te_start_ts = pd.to_datetime(te_start)
            te_end_ts = pd.to_datetime(te_end) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)

            # Overlap kontrolü (ayrık olmalı)
            if not (tr_end_ts < te_start_ts or te_end_ts < tr_start_ts):
                st.error("❌ Train ve Test tarih aralıkları çakışıyor. Lütfen ayrık aralık seç.")
                st.stop()

            train_mask = (df_sorted[date_col] >= tr_start_ts) & (df_sorted[date_col] <= tr_end_ts)
            test_mask = (df_sorted[date_col] >= te_start_ts) & (df_sorted[date_col] <= te_end_ts)

            if train_mask.sum() < 2 or test_mask.sum() < 1:
                st.error("❌ Seçilen aralıklarda yeterli veri yok. Train>=2 ve Test>=1 kayıt olmalı.")
                st.stop()

            df_train = df_sorted.loc[train_mask].copy()
            df_test = df_sorted.loc[test_mask].copy()

            X_train = pd.get_dummies(df_train[features], drop_first=False)
            y_train = df_train[target]
            X_test = pd.get_dummies(df_test[features], drop_first=False)
            y_test = df_test[target]

            # Kullanıcıya yüzde karşılığını göster
            total_n = len(df_sorted)
            train_n = len(df_train)
            test_n = len(df_test)
            test_pct = (test_n / total_n) * 100.0

            # ✅ Slider'ı tarih aralığındaki gerçek test oranına senkronla (pending ile)
            test_pct_int = int(round(test_pct))
            test_pct_int = max(5, min(50, test_pct_int))  # slider limitleri

            sync_sig = (str(tr_start), str(tr_end), str(te_start), str(te_end), int(total_n), int(test_n))
            last_sig = st.session_state.get("cf_test_size_sync_sig")

            if last_sig != sync_sig:
                st.session_state["cf_test_size_pct_pending"] = test_pct_int
                st.session_state["cf_test_size_sync_sig"] = sync_sig
                st.rerun()

            st.caption(
                f"📊 Seçim Özeti → Train: {train_n:,} kayıt | Test: {test_n:,} kayıt | "
                f"Test oranı ≈ %{test_pct:.1f} (slider: %{test_size*100:.0f})"
            )

        else:
            X_sorted = pd.get_dummies(df_sorted[features], drop_first=False)
            y_sorted = df_sorted[target]

            split_index = int(len(X_sorted) * (1 - test_size))
            X_train, X_test = X_sorted.iloc[:split_index], X_sorted.iloc[split_index:]
            y_train, y_test = y_sorted.iloc[:split_index], y_sorted.iloc[split_index:]

    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, shuffle=True, random_state=42
        )

    # Kolon hizalama (çok önemli)
    X_train, X_test = X_train.align(X_test, join="left", axis=1, fill_value=0)

    # ------------------ Model seçimi ------------------
    st.markdown("---")
    st.subheader("🧠 Tek Model Eğitimi")

    model_options = [
        "Linear Regression",
        "Ridge Regression",
        "Lasso Regression",
        "Decision Tree",
        "Random Forest",
    ]
    if _HAS_LGBM:
        model_options.append("LightGBM")
    if _HAS_XGB:
        model_options.append("XGBoost")

    auto_params = st.checkbox(
        "✅ Oto Parametre (önerilen)",
        value=True,
        help="Açıkken seçtiğin preset seviyesine göre parametreler otomatik gelir.",
    )

    preset_level = st.selectbox(
        "🎛️ Preset Seviyesi",
        ["Hızlı", "Dengeli", "Güçlü"],
        index=1,
        disabled=not auto_params,
    )

    model_name = st.selectbox("Model Seçin", model_options)

    # ------------------ Preset Parametreler ------------------
    PRESETS = {
        "Ridge Regression": {
            "Hızlı":   {"alpha": 1.0},
            "Dengeli": {"alpha": 1.0},
            "Güçlü":   {"alpha": 2.0},
        },
        "Lasso Regression": {
            "Hızlı":   {"alpha": 0.1},
            "Dengeli": {"alpha": 0.05},
            "Güçlü":   {"alpha": 0.02},
        },
        "Decision Tree": {
            "Hızlı":   {"max_depth": 6, "min_samples_split": 2, "min_samples_leaf": 1},
            "Dengeli": {"max_depth": 10, "min_samples_split": 4, "min_samples_leaf": 2},
            "Güçlü":   {"max_depth": 16, "min_samples_split": 6, "min_samples_leaf": 2},
        },
        "Random Forest": {
            "Hızlı": {
                "n_estimators": 200, "max_depth": 10,
                "min_samples_split": 2, "min_samples_leaf": 1,
                "max_features": "sqrt", "bootstrap": True,
            },
            "Dengeli": {
                "n_estimators": 400, "max_depth": 14,
                "min_samples_split": 4, "min_samples_leaf": 2,
                "max_features": "sqrt", "bootstrap": True,
            },
            "Güçlü": {
                "n_estimators": 700, "max_depth": 18,
                "min_samples_split": 6, "min_samples_leaf": 2,
                "max_features": "sqrt", "bootstrap": True,
            },
        },
        "LightGBM": {
            "Hızlı": {
                "n_estimators": 300, "learning_rate": 0.08,
                "num_leaves": 31, "max_depth": -1,
                "subsample": 0.9, "colsample_bytree": 0.9,
                "reg_alpha": 0.0, "reg_lambda": 0.0,
                "min_child_samples": 20
            },
            "Dengeli": {
                "n_estimators": 600, "learning_rate": 0.06,
                "num_leaves": 63, "max_depth": -1,
                "subsample": 0.85, "colsample_bytree": 0.85,
                "reg_alpha": 0.0, "reg_lambda": 0.0,
                "min_child_samples": 20
            },
            "Güçlü": {
                "n_estimators": 900, "learning_rate": 0.05,
                "num_leaves": 127, "max_depth": -1,
                "subsample": 0.8, "colsample_bytree": 0.8,
                "reg_alpha": 0.0, "reg_lambda": 0.0,
                "min_child_samples": 15
            },
        },
        "XGBoost": {
            "Hızlı": {
                "n_estimators": 300, "learning_rate": 0.08,
                "max_depth": 6, "subsample": 0.9, "colsample_bytree": 0.9,
                "min_child_weight": 1.0, "reg_alpha": 0.0, "reg_lambda": 1.0,
                "gamma": 0.0
            },
            "Dengeli": {
                "n_estimators": 600, "learning_rate": 0.06,
                "max_depth": 7, "subsample": 0.85, "colsample_bytree": 0.85,
                "min_child_weight": 1.0, "reg_alpha": 0.0, "reg_lambda": 1.0,
                "gamma": 0.0
            },
            "Güçlü": {
                "n_estimators": 900, "learning_rate": 0.05,
                "max_depth": 8, "subsample": 0.8, "colsample_bytree": 0.8,
                "min_child_weight": 1.0, "reg_alpha": 0.0, "reg_lambda": 1.2,
                "gamma": 0.0
            },
        },
    }

    st.session_state.setdefault("cf_model_params", {})

    def _get_param(model_key: str, param_name: str, default):
        return st.session_state.get("cf_model_params", {}).get(model_key, {}).get(param_name, default)

    def _set_param(model_key: str, param_name: str, value):
        st.session_state.setdefault("cf_model_params", {})
        st.session_state["cf_model_params"].setdefault(model_key, {})
        st.session_state["cf_model_params"][model_key][param_name] = value

    # auto açıksa preset bas
    if auto_params and model_name in PRESETS and preset_level in PRESETS[model_name]:
        st.session_state["cf_model_params"][model_name] = PRESETS[model_name][preset_level].copy()

    # ------------------ Hyperparam UI ------------------
    if model_name == "Linear Regression":
        model = LinearRegression()

    elif model_name == "Ridge Regression":
        alpha = st.slider("Alpha", 0.01, 50.0, float(_get_param(model_name, "alpha", 1.0)), disabled=auto_params)
        _set_param(model_name, "alpha", float(alpha))
        model = Ridge(alpha=float(alpha))

    elif model_name == "Lasso Regression":
        alpha = st.slider("Alpha", 0.001, 10.0, float(_get_param(model_name, "alpha", 0.05)), disabled=auto_params)
        _set_param(model_name, "alpha", float(alpha))
        model = Lasso(alpha=float(alpha))

    elif model_name == "Decision Tree":
        max_depth = st.slider("Max Depth", 1, 40, int(_get_param(model_name, "max_depth", 10)), disabled=auto_params)
        min_samples_split = st.slider("Min Samples Split", 2, 20, int(_get_param(model_name, "min_samples_split", 4)), disabled=auto_params)
        min_samples_leaf = st.slider("Min Samples Leaf", 1, 20, int(_get_param(model_name, "min_samples_leaf", 2)), disabled=auto_params)

        _set_param(model_name, "max_depth", int(max_depth))
        _set_param(model_name, "min_samples_split", int(min_samples_split))
        _set_param(model_name, "min_samples_leaf", int(min_samples_leaf))

        model = DecisionTreeRegressor(
            max_depth=int(max_depth),
            min_samples_split=int(min_samples_split),
            min_samples_leaf=int(min_samples_leaf),
            random_state=42
        )

    elif model_name == "Random Forest":
        n_estimators = st.slider("Ağaç Sayısı", 50, 1200, int(_get_param(model_name, "n_estimators", 400)), 50, disabled=auto_params)
        max_depth = st.slider("Max Depth", 2, 40, int(_get_param(model_name, "max_depth", 14)), disabled=auto_params)
        min_samples_split = st.slider("Min Samples Split", 2, 20, int(_get_param(model_name, "min_samples_split", 4)), disabled=auto_params)
        min_samples_leaf = st.slider("Min Samples Leaf", 1, 20, int(_get_param(model_name, "min_samples_leaf", 2)), disabled=auto_params)

        max_feat_options = ["sqrt", "log2", "auto"]
        saved_max_feat = _get_param(model_name, "max_features", "sqrt")
        saved_max_feat = "auto" if saved_max_feat in [None, "None"] else str(saved_max_feat)
        if saved_max_feat not in max_feat_options:
            saved_max_feat = "sqrt"

        max_feat = st.selectbox(
            "Max Features",
            max_feat_options,
            index=max_feat_options.index(saved_max_feat),
            disabled=auto_params,
        )
        bootstrap = st.checkbox("Bootstrap", value=bool(_get_param(model_name, "bootstrap", True)), disabled=auto_params)

        _set_param(model_name, "n_estimators", int(n_estimators))
        _set_param(model_name, "max_depth", int(max_depth))
        _set_param(model_name, "min_samples_split", int(min_samples_split))
        _set_param(model_name, "min_samples_leaf", int(min_samples_leaf))
        _set_param(model_name, "max_features", str(max_feat))
        _set_param(model_name, "bootstrap", bool(bootstrap))

        model = RandomForestRegressor(
            n_estimators=int(n_estimators),
            max_depth=int(max_depth),
            min_samples_split=int(min_samples_split),
            min_samples_leaf=int(min_samples_leaf),
            max_features=None if max_feat == "auto" else max_feat,
            bootstrap=bool(bootstrap),
            random_state=42,
            n_jobs=-1
        )

    elif model_name == "LightGBM":
        n_estimators = st.slider("Ağaç Sayısı", 50, 2000, int(_get_param(model_name, "n_estimators", 600)), 50, disabled=auto_params)
        learning_rate = st.slider("Learning Rate", 0.005, 0.3, float(_get_param(model_name, "learning_rate", 0.06)), disabled=auto_params)

        num_leaves = st.slider("Num Leaves", 15, 255, int(_get_param(model_name, "num_leaves", 63)), disabled=auto_params)
        max_depth = st.slider("Max Depth (-1 = limitsiz)", -1, 30, int(_get_param(model_name, "max_depth", -1)), disabled=auto_params)

        subsample = st.slider("Subsample", 0.5, 1.0, float(_get_param(model_name, "subsample", 0.85)), 0.05, disabled=auto_params)
        colsample_bytree = st.slider("Colsample Bytree", 0.5, 1.0, float(_get_param(model_name, "colsample_bytree", 0.85)), 0.05, disabled=auto_params)

        reg_alpha = st.slider("Reg Alpha (L1)", 0.0, 5.0, float(_get_param(model_name, "reg_alpha", 0.0)), 0.1, disabled=auto_params)
        reg_lambda = st.slider("Reg Lambda (L2)", 0.0, 10.0, float(_get_param(model_name, "reg_lambda", 0.0)), 0.1, disabled=auto_params)
        min_child_samples = st.slider("Min Child Samples", 1, 100, int(_get_param(model_name, "min_child_samples", 20)), disabled=auto_params)

        _set_param(model_name, "n_estimators", int(n_estimators))
        _set_param(model_name, "learning_rate", float(learning_rate))
        _set_param(model_name, "num_leaves", int(num_leaves))
        _set_param(model_name, "max_depth", int(max_depth))
        _set_param(model_name, "subsample", float(subsample))
        _set_param(model_name, "colsample_bytree", float(colsample_bytree))
        _set_param(model_name, "reg_alpha", float(reg_alpha))
        _set_param(model_name, "reg_lambda", float(reg_lambda))
        _set_param(model_name, "min_child_samples", int(min_child_samples))

        model = LGBMRegressor(
            n_estimators=int(n_estimators),
            learning_rate=float(learning_rate),
            num_leaves=int(num_leaves),
            max_depth=int(max_depth),
            subsample=float(subsample),
            colsample_bytree=float(colsample_bytree),
            reg_alpha=float(reg_alpha),
            reg_lambda=float(reg_lambda),
            min_child_samples=int(min_child_samples),
            random_state=42,
        )

    elif model_name == "XGBoost":
        n_estimators = st.slider("Ağaç Sayısı", 50, 2000, int(_get_param(model_name, "n_estimators", 600)), 50, disabled=auto_params)
        learning_rate = st.slider("Learning Rate", 0.005, 0.3, float(_get_param(model_name, "learning_rate", 0.06)), disabled=auto_params)

        max_depth = st.slider("Max Depth", 2, 15, int(_get_param(model_name, "max_depth", 7)), disabled=auto_params)
        subsample = st.slider("Subsample", 0.5, 1.0, float(_get_param(model_name, "subsample", 0.85)), 0.05, disabled=auto_params)
        colsample_bytree = st.slider("Colsample Bytree", 0.5, 1.0, float(_get_param(model_name, "colsample_bytree", 0.85)), 0.05, disabled=auto_params)

        min_child_weight = st.slider("Min Child Weight", 0.0, 20.0, float(_get_param(model_name, "min_child_weight", 1.0)), 0.5, disabled=auto_params)
        gamma = st.slider("Gamma", 0.0, 10.0, float(_get_param(model_name, "gamma", 0.0)), 0.1, disabled=auto_params)
        reg_alpha = st.slider("Reg Alpha (L1)", 0.0, 5.0, float(_get_param(model_name, "reg_alpha", 0.0)), 0.1, disabled=auto_params)
        reg_lambda = st.slider("Reg Lambda (L2)", 0.0, 10.0, float(_get_param(model_name, "reg_lambda", 1.0)), 0.1, disabled=auto_params)

        _set_param(model_name, "n_estimators", int(n_estimators))
        _set_param(model_name, "learning_rate", float(learning_rate))
        _set_param(model_name, "max_depth", int(max_depth))
        _set_param(model_name, "subsample", float(subsample))
        _set_param(model_name, "colsample_bytree", float(colsample_bytree))
        _set_param(model_name, "min_child_weight", float(min_child_weight))
        _set_param(model_name, "gamma", float(gamma))
        _set_param(model_name, "reg_alpha", float(reg_alpha))
        _set_param(model_name, "reg_lambda", float(reg_lambda))

        model = XGBRegressor(
            n_estimators=int(n_estimators),
            learning_rate=float(learning_rate),
            max_depth=int(max_depth),
            subsample=float(subsample),
            colsample_bytree=float(colsample_bytree),
            min_child_weight=float(min_child_weight),
            gamma=float(gamma),
            reg_alpha=float(reg_alpha),
            reg_lambda=float(reg_lambda),
            random_state=42,
            n_jobs=-1,
        )

    if auto_params and model_name in PRESETS:
        st.caption(f"✅ Preset ({preset_level}) parametreleri: {st.session_state['cf_model_params'].get(model_name, {})}")

    # ------------------ Train ------------------
    if st.button("🚀 Modeli Eğit", use_container_width=True):
        X_train_use, X_test_use, scaler = _scale_if_needed(X_train, X_test, normalize_data)

        model.fit(X_train_use, y_train)
        preds = model.predict(X_test_use)

        r2 = float(r2_score(y_test, preds))
        mae = float(mean_absolute_error(y_test, preds))
        rmse = _safe_rmse(y_test, preds)

        # --- MODEL STATE ---
        st.session_state["cf_model"] = model
        st.session_state["cf_model_name"] = model_name
        st.session_state["cf_target_name"] = target

        # ✅ Eğitimde seçilen ham feature listesi (dummy öncesi) — tahmin ekranı bunu kullanacak
        st.session_state["cf_model_features_used"] = list(features)

        # ✅ Model input kolonları (dummy sonrası) — en kritik parça
        st.session_state["cf_X_columns"] = X_train.columns.tolist()

        # Train/Test sakla (debug/rapor için)
        st.session_state["cf_X_train"] = X_train
        st.session_state["cf_X_test"] = X_test
        st.session_state["cf_y_train"] = y_train
        st.session_state["cf_y_test"] = y_test
        st.session_state["cf_test_predictions"] = preds

        # Full dummy matrisi (rapor/dummy analiz)
        st.session_state["cf_X_full"] = X

        # FE’li df (şu an kullanılan veri)
        st.session_state["cf_full_df"] = df

        # scaler kaydı
        st.session_state["cf_X_train_scaled"] = X_train_use
        st.session_state["cf_X_test_scaled"] = X_test_use
        st.session_state["cf_scaler_used"] = bool(normalize_data)
        if scaler is not None:
            st.session_state["cf_scaler_mean_"] = getattr(scaler, "mean_", None)
            st.session_state["cf_scaler_scale_"] = getattr(scaler, "scale_", None)
        else:
            st.session_state["cf_scaler_mean_"] = None
            st.session_state["cf_scaler_scale_"] = None

        # time split meta
        st.session_state["cf_is_time_series_split"] = bool(use_time_split)
        st.session_state["cf_date_col_used"] = auto_date if use_time_split else None

        # ✅ FE meta varsa onu da sakla (tahmin ekranında aynı FE kuralı uygulanacak)
        if "cf_fe_meta" in st.session_state and st.session_state.get("cf_fe_meta") is not None:
            st.session_state["cf_model_fe_meta"] = st.session_state.get("cf_fe_meta")
        else:
            st.session_state["cf_model_fe_meta"] = None

        st.success(f"✅ Model Eğitildi → R²={r2:.3f} | MAE={mae:.3f} | RMSE={rmse:.3f}")

    # ------------------ Compare + Grid ------------------
    st.markdown("---")
    st.subheader("🧪 Modelleri Karşılaştır ve Optimize Et")

    multi_compare = st.checkbox("Modelleri karşılaştırmayı etkinleştir", False)
    if not multi_compare:
        return

    base_models = {
        "Linear Regression": LinearRegression(),
        "Ridge Regression": Ridge(),
        "Lasso Regression": Lasso(),
        "Decision Tree": DecisionTreeRegressor(max_depth=6, random_state=42),
        "Random Forest": RandomForestRegressor(n_estimators=200, max_depth=8, random_state=42),
    }
    if _HAS_LGBM:
        base_models["LightGBM"] = LGBMRegressor(n_estimators=200, learning_rate=0.1, random_state=42)
    if _HAS_XGB:
        base_models["XGBoost"] = XGBRegressor(n_estimators=200, learning_rate=0.1, random_state=42)

    X_train_use, X_test_use, scaler = _scale_if_needed(X_train, X_test, normalize_data)

    results = []
    trained_models = {}

    for name, mdl in base_models.items():
        mdl.fit(X_train_use, y_train)
        p = mdl.predict(X_test_use)
        trained_models[name] = mdl
        results.append([
            name,
            float(r2_score(y_test, p)),
            float(mean_absolute_error(y_test, p)),
            _safe_rmse(y_test, p),
        ])

    compare_df = pd.DataFrame(results, columns=["Model", "R²", "MAE", "RMSE"]).sort_values("R²", ascending=False)
    st.dataframe(compare_df, use_container_width=True)

    st.markdown("### 📌 Kaydedilecek model:")
    to_save = st.selectbox("Model seç:", compare_df["Model"].tolist(), key="cf_model_save_pick")

    if st.button("📌 Bu modeli kaydet", use_container_width=True):
        chosen = trained_models[to_save]
        preds_save = chosen.predict(X_test_use)

        st.session_state["cf_model"] = chosen
        st.session_state["cf_model_name"] = to_save

        st.session_state["cf_test_predictions"] = preds_save
        st.session_state["cf_y_test"] = y_test
        st.session_state["cf_y_train"] = y_train

        st.session_state["cf_X_columns"] = X_train.columns.tolist()
        st.session_state["cf_X_train"] = X_train
        st.session_state["cf_X_test"] = X_test

        st.session_state["cf_X_full"] = X
        st.session_state["cf_full_df"] = df

        st.session_state["cf_X_train_scaled"] = X_train_use
        st.session_state["cf_X_test_scaled"] = X_test_use

        st.session_state["cf_scaler_used"] = bool(normalize_data)
        if scaler is not None:
            st.session_state["cf_scaler_mean_"] = getattr(scaler, "mean_", None)
            st.session_state["cf_scaler_scale_"] = getattr(scaler, "scale_", None)
        else:
            st.session_state["cf_scaler_mean_"] = None
            st.session_state["cf_scaler_scale_"] = None

        st.session_state["cf_is_time_series_split"] = bool(use_time_split)
        st.session_state["cf_date_col_used"] = auto_date if use_time_split else None

        st.session_state["cf_target_name"] = target

        # ✅ en kritik: dummy öncesi feature listesi
        st.session_state["cf_model_features_used"] = list(features)

        # ✅ FE meta
        if "cf_fe_meta" in st.session_state and st.session_state.get("cf_fe_meta") is not None:
            st.session_state["cf_model_fe_meta"] = st.session_state.get("cf_fe_meta")
        else:
            st.session_state["cf_model_fe_meta"] = None

        st.success("✅ Model kaydedildi. Model Raporu sekmesine geçebilirsin.")
        st.rerun()

    # ------------------ GridSearch ------------------
    st.markdown("---")
    st.markdown("### ⚡ GridSearch ile Optimize Et")
    st.caption("Not: GridSearch kombinasyon sayısı büyüdükçe süre uzar.")

    grid_params = {
        "Ridge Regression": {
            "alpha": [0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10, 20],
            "fit_intercept": [True, False],
            "solver": ["auto", "svd", "cholesky", "lsqr", "sparse_cg", "sag", "saga"],
        },
        "Lasso Regression": {
            "alpha": [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 2],
            "fit_intercept": [True, False],
            "max_iter": [2000, 5000],
        },
        "Decision Tree": {
            "max_depth": [3, 5, 8, 12, 16, None],
            "min_samples_split": [2, 4, 8, 12],
            "min_samples_leaf": [1, 2, 4, 8],
            "max_features": [None, "sqrt", "log2"],
        },
        "Random Forest": {
            "n_estimators": [200, 400, 700],
            "max_depth": [8, 12, 16, None],
            "min_samples_split": [2, 4, 8],
            "min_samples_leaf": [1, 2, 4],
            "max_features": ["sqrt", "log2", None],
            "bootstrap": [True, False],
        },
    }

    if _HAS_LGBM:
        grid_params["LightGBM"] = {
            "n_estimators": [300, 600, 900],
            "learning_rate": [0.03, 0.05, 0.08, 0.12],
            "num_leaves": [31, 63, 127],
            "max_depth": [-1, 6, 10, 14],
            "subsample": [0.75, 0.85, 0.95],
            "colsample_bytree": [0.75, 0.85, 0.95],
            "min_child_samples": [10, 20, 30, 50],
            "reg_alpha": [0.0, 0.1, 0.5],
            "reg_lambda": [0.0, 0.5, 1.0],
        }

    if _HAS_XGB:
        grid_params["XGBoost"] = {
            "n_estimators": [300, 600, 900],
            "learning_rate": [0.03, 0.05, 0.08, 0.12],
            "max_depth": [4, 6, 8, 10],
            "subsample": [0.75, 0.85, 0.95],
            "colsample_bytree": [0.75, 0.85, 0.95],
            "min_child_weight": [1, 3, 5, 7],
            "gamma": [0.0, 0.5, 1.0],
            "reg_alpha": [0.0, 0.1, 0.5],
            "reg_lambda": [0.8, 1.0, 1.2],
        }

    available_for_tune = [m for m in compare_df["Model"].tolist() if m in grid_params]
    if not available_for_tune:
        st.info("GridSearch için uygun model yok.")
        return

    tune_choice = st.selectbox("Optimize edilecek model", available_for_tune, key="cf_tune_pick")
    cv_folds = st.slider("CV Fold", 2, 5, 3)

    def _count_grid_combos(param_grid: dict) -> int:
        n = 1
        for v in param_grid.values():
            n *= len(v)
        return int(n)

    combo_count = _count_grid_combos(grid_params[tune_choice])
    st.info(f"🔢 Tahmini kombinasyon: {combo_count:,} (CV={cv_folds} → toplam fit ≈ {combo_count * cv_folds:,})")

    if st.button("🔍 En iyi parametreleri bul", use_container_width=True):
        with st.spinner("⏳ GridSearch çalışıyor..."):
            grid = GridSearchCV(
                base_models[tune_choice],
                grid_params[tune_choice],
                cv=cv_folds,
                scoring="r2",
                n_jobs=-1,
            )
            grid.fit(X_train_use, y_train)

        tuned = grid.best_estimator_
        preds_tuned = tuned.predict(X_test_use)

        r2 = float(r2_score(y_test, preds_tuned))
        mae = float(mean_absolute_error(y_test, preds_tuned))
        rmse = _safe_rmse(y_test, preds_tuned)

        st.success(f"✅ Optimize Edilmiş → R²={r2:.3f} | MAE={mae:.3f} | RMSE={rmse:.3f}")
        st.info(f"🔧 En iyi parametreler: {grid.best_params_}")
        st.warning("💡 İstersen bu parametrelerle yukarıda 'Tek Model Eğit' kısmından tekrar eğitip kaydedebilirsin.")
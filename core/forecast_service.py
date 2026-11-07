"""Comparable model snapshots, four-model forecasts and planning source choice."""
from datetime import datetime
import hashlib
import json

import numpy as np
import pandas as pd

DAY_NAMES = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def date_column(df):
    for col in df:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            return col
    for col in df:
        if pd.api.types.is_numeric_dtype(df[col]):
            continue
        if pd.to_datetime(df[col], errors="coerce").notna().mean() > .9:
            return col
    return None


def daily_history(df, target=None, date_col=None):
    date_col = date_col or date_column(df)
    target = target or next((x for x in ("cagri_sayisi", "Çağrı", "calls", "Call_Count", "y") if x in df), None)
    if not date_col or not target:
        raise ValueError("Tarih ve çağrı sayısı sütunlarını seçin.")
    dates = pd.to_datetime(df[date_col], errors="coerce")
    values = pd.to_numeric(df[target], errors="coerce")
    if dates.isna().any() or values.isna().any() or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Çağrı geçmişinde geçersiz tarih veya çağrı sayısı var.")
    return pd.DataFrame({"tarih": dates.dt.normalize(), "cagri_sayisi": values}).groupby("tarih", as_index=False).sum().sort_values("tarih")


def signature(*frames, extra=None):
    digest = hashlib.sha256()
    for frame in frames:
        digest.update(pd.util.hash_pandas_object(frame, index=True).values.tobytes())
        digest.update(str(list(getattr(frame, "columns", []))).encode())
    digest.update(json.dumps(extra, sort_keys=True, default=str).encode())
    return digest.hexdigest()


def register_model(state, name, model, metrics, df, features, columns, date_col,
                   scaler=None, context=None):
    if not all(np.isfinite(float(metrics[k])) for k in ("RMSE", "MAE")):
        raise ValueError("Model hata ölçümleri geçerli değil.")
    if state.get("cf_candidate_context") != context:
        state["cf_model_candidates"] = {}
        state["cf_candidate_context"] = context
    candidates = dict(state.get("cf_model_candidates", {}))
    candidates[name] = {"name": name, "model": model, "metrics": dict(metrics), "history": df.copy(),
                        "features": list(features), "columns": list(columns), "date_col": date_col,
                        "scaler": scaler, "context": context}
    state["cf_model_candidates"] = candidates


def ranked_candidates(state, count=4):
    return sorted(state.get("cf_model_candidates", {}).values(), key=lambda b: (b["metrics"]["RMSE"], b["metrics"]["MAE"], b["name"]))[:count]


def forecast_candidates(state, start, end):
    from modules.call_forecast.predict_ui import _build_future_X_like_training
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if end < start or (end-start).days > 366:
        raise ValueError("Tahmin aralığı 1–367 gün olmalı.")
    candidates = ranked_candidates(state)
    if len(candidates) < 4:
        raise ValueError("Dört tahmin için Model Kur ekranında en az dört modeli aynı test döneminde karşılaştırın.")
    options = []
    for rank, bundle in enumerate(candidates, 1):
        _, X, used_date = _build_future_X_like_training(bundle["history"], bundle["columns"], bundle["features"],
                                                       bundle["date_col"], start.date(), end.date())
        if bundle.get("scaler") is not None:
            X = bundle["scaler"].transform(X)
        pred = np.asarray(bundle["model"].predict(X)).reshape(-1)
        if not np.isfinite(pred).all():
            raise ValueError(f"{bundle['name']}: model sonlu olmayan tahmin üretti.")
        # The feature builder uses half-hour rows for interval-trained models.
        is_interval = len(pred) != (end-start).days+1
        freq = "30min" if is_interval else "D"
        dates = pd.date_range(start, end+pd.Timedelta(days=1), freq=freq, inclusive="left")
        out = pd.DataFrame({"tarih": dates.normalize(), "y_pred": np.maximum(pred, 0)})
        out = out.groupby("tarih", as_index=False)["y_pred"].sum()
        out["Gun_Ismi"] = out.tarih.dt.weekday.map(dict(enumerate(DAY_NAMES)))
        options.append({"id": bundle["name"], "name": bundle["name"], "rank": rank, "frame": out,
                        "metrics": bundle["metrics"], "meta": {"model_name": bundle["name"], "start": str(start.date()),
                        "end": str(end.date()), "horizon": f"{len(out)} gün", "created_at": datetime.now().isoformat(timespec="seconds"),
                        "ranking_metric": "RMSE", "training_context": bundle["context"], "date_col_used": used_date}})
    state["cf_forecast_options"] = options
    state["cf_forecast_df"] = options[0]["frame"].copy()  # Legacy report compatibility.
    state["cf_forecast_meta"] = options[0]["meta"].copy()
    state["cf_forecast_ready"] = True
    return options


def validate_forecast(frame):
    if frame.empty or not {"tarih", "y_pred"} <= set(frame):
        raise ValueError("Her tarih için bir çağrı tahmini gerekli.")
    out = frame[["tarih", "y_pred"]].copy()
    out["tarih"] = pd.to_datetime(out.tarih, errors="coerce").dt.normalize()
    out["y_pred"] = pd.to_numeric(out.y_pred, errors="coerce")
    if out.isna().any().any() or not np.isfinite(out.y_pred).all() or (out.y_pred < 0).any():
        raise ValueError("Tarih ve çağrı sayıları dolu, geçerli ve negatif olmayan değerler olmalı.")
    if out.tarih.duplicated().any():
        raise ValueError("Aynı tarih birden fazla kez girilemez.")
    out = out.sort_values("tarih").reset_index(drop=True)
    expected = pd.date_range(out.tarih.min(), out.tarih.max())
    if len(out) != len(expected):
        raise ValueError("Tarih aralığında eksik gün var. Her gün için çağrı sayısı girin.")
    return out


def activate_forecast(state, frame, meta):
    frame = validate_forecast(frame)
    old = state.get("sp_forecast_df")
    if old is None or not frame.equals(old):
        state["sp_staffing_result_df"] = None
        state["plan_ctx_confirmed"] = False
    state["sp_forecast_df"] = frame
    state["sp_forecast_meta"] = dict(meta)
    from core.workspace_store import save_keys
    save_keys(state)


def reference_models(state, history):
    """Real chronological comparison for the ready-to-use demo, not fake scores."""
    from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, GradientBoostingRegressor
    from sklearn.linear_model import LinearRegression, Ridge
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from modules.call_forecast.predict_ui import _apply_date_bank_features
    history = daily_history(history)
    if len(history) < 42:
        raise ValueError("Karşılaştırma için en az 42 günlük geçmiş gerekli.")
    features = ["Gun", "Ay", "Yil", "Hafta", "Haftanin_Gunu", "Hafta_Ici", "EKSTRE_KESIM", "SON_ODEME"]
    frame = _apply_date_bank_features(history, "tarih", features, history)
    X, y = frame[features].astype(float), frame.cagri_sayisi
    split = len(frame)-min(56,max(14,len(frame)//5))
    context = signature(X.iloc[:split], X.iloc[split:], y, extra={"split": split, "source": "chronological-reference"})
    models = {"Linear Regression": LinearRegression(), "Ridge Regression": Ridge(alpha=5),
              "Random Forest": RandomForestRegressor(n_estimators=80,max_depth=10,random_state=42,n_jobs=1),
              "Extra Trees": ExtraTreesRegressor(n_estimators=80,max_depth=10,random_state=42,n_jobs=1),
              "Gradient Boosting": GradientBoostingRegressor(n_estimators=100,max_depth=3,random_state=42)}
    scores = []
    for name, model in models.items():
        model.fit(X.iloc[:split], y.iloc[:split])
        pred = model.predict(X.iloc[split:])
        metrics = {"RMSE": float(np.sqrt(mean_squared_error(y.iloc[split:], pred))),
                   "MAE": float(mean_absolute_error(y.iloc[split:], pred)), "R²": float(r2_score(y.iloc[split:], pred)),
                   "Test başlangıç": str(frame.tarih.iloc[split].date()), "Test bitiş": str(frame.tarih.iloc[-1].date())}
        register_model(state,name,model,metrics,frame,features,list(X.columns),"tarih",context=context)
        scores.append({"Model":name,**metrics})
    state["cf_reference_scores"] = pd.DataFrame(scores).sort_values("RMSE")
    best=ranked_candidates(state)[0]
    state.update(cf_model=best['model'],cf_model_name=best['name'],cf_target_name='cagri_sayisi',
                 cf_model_features_used=features,cf_X_columns=list(X),cf_X_full=X.copy(),
                 cf_X_train=X.iloc[:split].copy(),cf_X_test=X.iloc[split:].copy(),
                 cf_y_train=y.iloc[:split].copy(),cf_y_test=y.iloc[split:].copy(),
                 cf_test_predictions=best['model'].predict(X.iloc[split:]),
                 cf_X_train_scaled=X.iloc[:split].copy(),cf_X_test_scaled=X.iloc[split:].copy(),
                 cf_scaler_used=False,cf_date_col_used='tarih',cf_is_time_series_split=True)
    return state["cf_reference_scores"]


def weekday_comparison(history, start, days=7, as_of=None):
    history = daily_history(history)
    cutoff = pd.Timestamp(as_of).normalize() if as_of is not None else history.tarih.max()
    history = history[history.tarih <= cutoff].set_index("tarih").cagri_sayisi
    start = pd.Timestamp(start).normalize()
    if start <= cutoff:
        raise ValueError("Karşılaştırılacak günler geçmiş veri kesiminden sonra olmalı.")
    rows = []
    for day in pd.date_range(start, periods=days):
        last = history.get(day-pd.Timedelta(days=7), np.nan)
        two_dates = [day-pd.Timedelta(days=n) for n in (7,14)]
        two = history.reindex(two_dates).dropna()
        month = history[(history.index > cutoff-pd.Timedelta(days=30)) & (history.index.weekday == day.weekday())]
        rows.append({"Tarih":day,"Gün":DAY_NAMES[day.weekday()],"Geçen hafta aynı gün":last,
                     "Son 2 hafta aynı gün ort.":two.mean(),"Son 30 gün aynı gün ort.":month.mean(),
                     "2 hafta örnek sayısı":len(two),"30 gün örnek sayısı":len(month)})
    return pd.DataFrame(rows)

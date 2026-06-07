# modules/call_forecast/model_report.py
import numpy as np
import pandas as pd
import streamlit as st

from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error


# ----------------------------
# Helpers
# ----------------------------
def _rmse(y_true, y_pred) -> float:
    try:
        return float(mean_squared_error(y_true, y_pred, squared=False))
    except TypeError:
        return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def _safe_series(x):
    if isinstance(x, pd.Series):
        return x
    if isinstance(x, pd.DataFrame):
        if x.shape[1] == 1:
            return x.iloc[:, 0]
        return pd.Series(x.values.reshape(-1))
    return pd.Series(x)


def _has_all(keys: list[str]) -> tuple[bool, list[str]]:
    missing = [k for k in keys if k not in st.session_state]
    return (len(missing) == 0), missing


def _metric_color(r2: float) -> str:
    if r2 < 0.3:
        return "#ff4b4b"
    if r2 < 0.7:
        return "#ffa534"
    return "#4bb543"


def _render_metric_cards(r2: float, mae: float, rmse: float):
    color = _metric_color(r2)

    box_style = """
        background-color: #ffffff;
        padding: 12px;
        border-radius: 8px;
        border-left: 6px solid {color};
        text-align: center;
    """
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f"""
            <div style="{box_style.format(color=color)}">
                <p style="margin:0; font-size:14px; color:#000;">R²</p>
                <p style="margin:0; font-size:22px; font-weight:bold; color:#000;">{r2:.3f}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div style="{box_style.format(color='#6fa8dc')}">
                <p style="margin:0; font-size:14px; color:#000;">MAE</p>
                <p style="margin:0; font-size:22px; font-weight:bold; color:#000;">{mae:.3f}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f"""
            <div style="{box_style.format(color='#8e7cc3')}">
                <p style="margin:0; font-size:14px; color:#000;">RMSE</p>
                <p style="margin:0; font-size:22px; font-weight:bold; color:#000;">{rmse:.3f}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    if r2 < 0.3:
        st.error("📉 Model hedef değişkeni **zayıf açıklıyor**.")
    elif r2 < 0.7:
        st.warning("⚖️ Model **orta düzeyde açıklıyor**. Tuning yapılabilir.")
    else:
        st.success("🚀 Model **yüksek başarı gösteriyor!** ✅")


def _detect_date_col(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        parsed = pd.to_datetime(df[col], errors="coerce")
        if parsed.notna().mean() > 0.8:
            return col
    return None


def _risk_feature_warnings(feature_names: list[str]) -> list[str]:
    msgs = []
    for c in feature_names:
        cl = str(c).lower()
        if cl == "id" or cl.endswith("_id"):
            msgs.append(f"• **{c}**: ID benzeri → leakage riski olabilir.")
        if "agent" in cl or "musteri" in cl or "customer" in cl:
            msgs.append(f"• **{c}**: kimlik/personel bilgisi gibi → leakage / adil kullanım riski olabilir.")
        if "date" in cl or "tarih" in cl or "datetime" in cl:
            msgs.append(f"• **{c}**: tarih/datetime olabilir → leakage/hata üretebilir.")
        if "target" in cl or "label" in cl:
            msgs.append(f"• **{c}**: target/label benzeri → leakage olabilir.")
    return msgs


def _split_numeric_dummy_features(X_columns: list[str], df_full: pd.DataFrame) -> dict:
    """
    Dummy vs Sayısal ayrımı:
    - Sayısal: df_full içinde var + df_full[col] numeric dtype
    - Dummy: df_full içinde YOK (get_dummies ile üretilen kolonlar)
    """
    X_cols = [str(c) for c in X_columns]
    df_cols = set(df_full.columns) if isinstance(df_full, pd.DataFrame) else set()

    numeric_feats = []
    dummy_feats = []
    other_orig = []

    for c in X_cols:
        if c in df_cols:
            # df_full’da var → orijinal kolon
            if pd.api.types.is_numeric_dtype(df_full[c]):
                numeric_feats.append(c)
            else:
                # normalde get_dummies bunu bırakmaz ama yine de dursun
                other_orig.append(c)
        else:
            dummy_feats.append(c)

    # dummy base sayısı
    dummy_base = set()
    for d in dummy_feats:
        base = d.split("_")[0] if "_" in d else d
        dummy_base.add(base)

    return {
        "numeric": numeric_feats,
        "dummy": dummy_feats,
        "other_orig": other_orig,
        "dummy_base": sorted(dummy_base),
    }


def _get_feature_effect_df(model, feature_names: list[str]) -> pd.DataFrame:
    """
    columns:
      Feature, EffectRaw, ImportanceAbs, Direction
    """
    if hasattr(model, "coef_"):
        coef = np.asarray(model.coef_).reshape(-1)
        df_eff = pd.DataFrame({"Feature": feature_names, "EffectRaw": coef})
        df_eff["ImportanceAbs"] = df_eff["EffectRaw"].abs()
        df_eff["Direction"] = np.where(df_eff["EffectRaw"] >= 0, "Pozitif", "Negatif")
        return df_eff.sort_values("ImportanceAbs", ascending=False).reset_index(drop=True)

    if hasattr(model, "feature_importances_"):
        imp = np.asarray(model.feature_importances_).reshape(-1)
        df_eff = pd.DataFrame({"Feature": feature_names, "EffectRaw": imp})
        df_eff["ImportanceAbs"] = df_eff["EffectRaw"]  # zaten pozitif
        df_eff["Direction"] = "—"
        return df_eff.sort_values("ImportanceAbs", ascending=False).reset_index(drop=True)

    return pd.DataFrame({"Feature": feature_names, "EffectRaw": np.nan, "ImportanceAbs": np.nan, "Direction": "—"})


def _make_feature_quality_labels(
    feat_df: pd.DataFrame,
    df_full: pd.DataFrame,
    X_full: pd.DataFrame,
    test_idx,
    report_df: pd.DataFrame,
    top_for_quality: int = 30,
) -> pd.DataFrame:
    """
    Etiket mantığı: test setinde feature grupları arasında |Hata| ve |Hata%| yayılımı büyüdükçe "kötü".
    Hesaplanamayanlara None bırakmayacağız.
    """
    if feat_df.empty:
        return feat_df

    cand_feats = feat_df["Feature"].head(int(top_for_quality)).tolist()
    rows = []

    abs_err = np.abs(report_df["Hata"].values)
    abs_err_pct = np.abs(report_df["Hata (%)"].values)

    df_cols = set(df_full.columns) if isinstance(df_full, pd.DataFrame) else set()

    for f in cand_feats:
        try:
            # Orijinal kolonsa
            if f in df_cols:
                s = df_full.loc[test_idx, f]
                tmp = pd.DataFrame({"val": s.values, "ae": abs_err, "ap": abs_err_pct}).dropna(subset=["val"])
                if tmp.empty or tmp["val"].nunique() < 2:
                    continue

                if pd.api.types.is_numeric_dtype(s):
                    q = min(6, int(tmp["val"].nunique()))
                    if q < 2:
                        continue
                    tmp["bin"] = pd.qcut(tmp["val"], q=q, duplicates="drop")
                    g = tmp.groupby("bin", dropna=False).agg(e=("ae", "mean"), p=("ap", "mean")).reset_index()
                else:
                    topcats = tmp["val"].value_counts().head(20).index
                    tmp2 = tmp[tmp["val"].isin(topcats)].copy()
                    g = tmp2.groupby("val", dropna=False).agg(e=("ae", "mean"), p=("ap", "mean")).reset_index()

                if len(g) < 2:
                    continue

                spread_e = float(g["e"].max() - g["e"].min())
                spread_p = float(g["p"].max() - g["p"].min())
                score = spread_e + spread_p
                rows.append([f, score, spread_e, spread_p])

            # Dummy feature ise (0/1 veya one-hot)
            elif isinstance(X_full, pd.DataFrame) and (f in X_full.columns):
                x = X_full.loc[test_idx, f]
                tmp = pd.DataFrame({"val": x.values, "ae": abs_err, "ap": abs_err_pct})
                if tmp["val"].nunique() < 2:
                    continue
                g = tmp.groupby("val", dropna=False).agg(e=("ae", "mean"), p=("ap", "mean")).reset_index()
                if len(g) < 2:
                    continue

                spread_e = float(g["e"].max() - g["e"].min())
                spread_p = float(g["p"].max() - g["p"].min())
                score = spread_e + spread_p
                rows.append([f, score, spread_e, spread_p])

        except Exception:
            continue

    qual = pd.DataFrame(rows, columns=["Feature", "Skor", "Hata Yayılımı", "Hata% Yayılımı"])
    if qual.empty:
        # kimse hesaplanamadı → hepsine default ver
        feat_df["Etiket"] = "⚪ Hesaplanmadı"
        feat_df["Hata Yayılımı"] = np.nan
        feat_df["Hata% Yayılımı"] = np.nan
        return feat_df

    q1 = qual["Skor"].quantile(0.33)
    q2 = qual["Skor"].quantile(0.66)

    def _lab(x):
        if x <= q1:
            return "🟢 İyi"
        if x <= q2:
            return "🟡 Orta"
        return "🔴 Kötü"

    qual["Etiket"] = qual["Skor"].apply(_lab)

    feat_df2 = feat_df.merge(
        qual[["Feature", "Etiket", "Hata Yayılımı", "Hata% Yayılımı"]],
        on="Feature",
        how="left",
    )

    # ✅ None dönmesin
    feat_df2["Etiket"] = feat_df2["Etiket"].fillna("⚪ Hesaplanmadı")
    return feat_df2


def _plot_bar(df_plot: pd.DataFrame, x_col: str, y_col: str, color_col: str | None, title: str):
    import plotly.express as px

    plot_df = df_plot.copy()

    if color_col and color_col in plot_df.columns:
        fig = px.bar(
            plot_df,
            x=x_col,
            y=y_col,
            orientation="h",
            color=color_col,
            title=title,
            hover_data=[c for c in plot_df.columns if c not in [x_col, y_col]],
        )
    else:
        fig = px.bar(
            plot_df,
            x=x_col,
            y=y_col,
            orientation="h",
            title=title,
            hover_data=[c for c in plot_df.columns if c not in [x_col, y_col]],
        )

    fig.update_layout(height=520, yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)


def _build_total_view(df_eff: pd.DataFrame, numeric_feats: list[str], dummy_feats: list[str]) -> pd.DataFrame:
    """
    Toplam görünüm:
    - Sayısallar: tek tek
    - Dummy’ler: base’e göre toplanır (ilk '_' öncesi)
    """
    eff = df_eff.copy()
    eff["Feature"] = eff["Feature"].astype(str)

    # Sayısal tek tek
    num_part = eff[eff["Feature"].isin(numeric_feats)].copy()
    num_part["Group"] = num_part["Feature"]
    num_part["Type"] = "Sayısal"
    num_agg = num_part.groupby(["Group", "Type"], as_index=False).agg(Importance=("ImportanceAbs", "sum"))

    # Dummy base topla
    dum_part = eff[eff["Feature"].isin(dummy_feats)].copy()
    dum_part["Group"] = dum_part["Feature"].apply(lambda x: x.split("_")[0] if "_" in x else x)
    dum_part["Type"] = "Dummy"
    dum_agg = dum_part.groupby(["Group", "Type"], as_index=False).agg(Importance=("ImportanceAbs", "sum"))

    out = pd.concat([num_agg, dum_agg], ignore_index=True)
    out = out.sort_values("Importance", ascending=False).reset_index(drop=True)
    return out


# ----------------------------
# UI
# ----------------------------
def render():
    st.subheader("Model Performans Raporu")
    st.markdown("---")

    required = [
        "cf_model",
        "cf_model_name",
        "cf_test_predictions",
        "cf_y_test",
        "cf_X_columns",
        "cf_X_full",
        "cf_full_df",
        "cf_target_name",
    ]
    ok, missing = _has_all(required)
    if not ok:
        st.error(
            "Model raporu için bazı bilgiler eksik.\n\n"
            f"Eksikler: {', '.join(missing)}\n\n"
            "Lütfen **Model Kur** ekranından modeli tekrar eğit / kaydet."
        )
        return

    model = st.session_state["cf_model"]
    model_name = st.session_state.get("cf_model_name", model.__class__.__name__)
    preds = np.asarray(st.session_state["cf_test_predictions"]).reshape(-1)

    y_test = _safe_series(st.session_state["cf_y_test"]).copy()
    X_columns = list(st.session_state["cf_X_columns"])
    X_full = st.session_state["cf_X_full"]
    df_full = st.session_state["cf_full_df"]

    target_name = st.session_state.get("cf_target_name")
    date_col_used = st.session_state.get("cf_date_col_used", None)

    if len(y_test) != len(preds):
        st.error("Test truth ve tahmin boyutları uyuşmuyor. Modeli yeniden eğitmen gerekiyor.")
        return

    # tarih kolonu
    date_col = None
    if isinstance(df_full, pd.DataFrame):
        if date_col_used and date_col_used in df_full.columns:
            date_col = date_col_used
        else:
            date_col = _detect_date_col(df_full)

    test_idx = y_test.index if isinstance(y_test, pd.Series) else pd.RangeIndex(len(preds))

    # dummy/sayısal sayıları
    split = _split_numeric_dummy_features(X_columns, df_full if isinstance(df_full, pd.DataFrame) else pd.DataFrame())
    numeric_feats = split["numeric"]
    dummy_feats = split["dummy"]
    dummy_base = split["dummy_base"]

    # ------------------ Üst Özet + Performans (Modern / Expander yok) ------------------

    # --- KPI satırı (özet) ---
    k1, k2, k3, k4 = st.columns([2,2,1,1])
    k1.metric("🧠 Model", str(model_name))
    k2.metric("🎯 Target", str(target_name))
    k3.metric("🧩 Feature (Toplam)", f"{len(X_columns):,}")
    k4.metric("📦 Kayıt", f"{len(df_full):,}" if isinstance(df_full, pd.DataFrame) else f"{len(y_test):,}")

    st.markdown("")

    # --- Feature kırılım kartları ---
    a, b, c = st.columns(3)

    card_css = """
    <div style="
        background:#ffffff;
        border:1px solid rgba(0,0,0,0.08);
        border-radius:14px;
        padding:14px 16px;
        box-shadow:0 2px 10px rgba(0,0,0,0.04);
        height:100%;
    ">
        <div style="font-size:13px; opacity:0.75; margin-bottom:6px;">{title}</div>
        <div style="font-size:26px; font-weight:700; line-height:1;">{value}</div>
        <div style="font-size:12px; opacity:0.70; margin-top:8px;">{sub}</div>
    </div>
    """

    with a:
        st.markdown(
            card_css.format(
                title="Sayısal Feature",
                value=f"{len(numeric_feats):,}",
                sub="Orijinal veri içinde sayısal olanlar",
            ),
            unsafe_allow_html=True,
        )

    with b:
        st.markdown(
            card_css.format(
                title="Dummy Feature",
                value=f"{len(dummy_feats):,}",
                sub="One-hot ile oluşan kolonlar",
            ),
            unsafe_allow_html=True,
        )

    with c:
        st.markdown(
            card_css.format(
                title="Dummy Base",
                value=f"{len(dummy_base):,}",
                sub="Dummy’lerin base kolon sayısı",
            ),
            unsafe_allow_html=True,
        )

    st.markdown("")

    # --- Risk kontrolleri (expander yok) ---
    risk_msgs = _risk_feature_warnings(X_columns)
    if risk_msgs:
        st.warning("🚨 Riskli Feature Kontrolleri:\n\n" + "\n".join(risk_msgs))
    else:
        st.success("✅ Belirgin leakage/ID riski yakalanmadı (yine de kontrol etmek iyi olur).")

    st.caption("Not: Bu özet, Model Kur ekranında kaydedilen test split ve feature set üzerinden üretilir.")

    # ------------------ Performans ------------------
    st.markdown("---")
    r2 = float(r2_score(y_test, preds))
    mae = float(mean_absolute_error(y_test, preds))
    rmse = _rmse(y_test, preds)
    _render_metric_cards(r2, mae, rmse)
    st.markdown("---")
    # ------------------ Hata Analizi ------------------
    st.subheader("📦 Hata Analizi")

    y_vals = y_test.values if isinstance(y_test, pd.Series) else np.asarray(y_test)
    residuals = (y_vals - preds)

    y_safe = pd.Series(y_vals, index=test_idx).replace(0, np.nan)
    perc_err = (pd.Series(residuals, index=test_idx) / y_safe) * 100
    perc_err = perc_err.fillna(0)

    report_df = pd.DataFrame(
        {"Gerçek": y_vals, "Tahmin": preds, "Hata": residuals, "Hata (%)": np.round(perc_err.values, 2)},
        index=test_idx,
    )
    # ------------------ % Hata band analizi (±%5 / ±%10 / ±%20) ------------------

    valid_df = report_df[report_df["Gerçek"] != 0].copy()
    abs_pct = valid_df["Hata (%)"].abs()
    n_total = len(valid_df)

    if n_total > 0:
        mask_5 = abs_pct <= 5
        mask_10 = abs_pct <= 10
        mask_20 = abs_pct <= 20

        count_5 = int(mask_5.sum())
        count_10 = int(mask_10.sum())
        count_20 = int(mask_20.sum())

        within_5 = (count_5 / n_total) * 100
        within_10 = (count_10 / n_total) * 100
        within_20 = (count_20 / n_total) * 100
    else:
        count_5 = count_10 = count_20 = 0
        within_5 = within_10 = within_20 = 0.0


    st.markdown("### 🎯 Yüzde Hata Bandı (Test Seti)")
    st.caption("Hesaplama yalnızca Gerçek ≠ 0 olan kayıtlar üzerinden yapılır.")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("±%5 içinde", f"{within_5:.1f}%")
        st.markdown(
            f"<div style='font-size:13px; opacity:0.7;'>{count_5:,} / {n_total:,} kayıt</div>",
            unsafe_allow_html=True,
        )

    with col2:
        st.metric("±%10 içinde", f"{within_10:.1f}%")
        st.markdown(
            f"<div style='font-size:13px; opacity:0.7;'>{count_10:,} / {n_total:,} kayıt</div>",
            unsafe_allow_html=True,
        )

    with col3:
        st.metric("±%20 içinde", f"{within_20:.1f}%")
        st.markdown(
            f"<div style='font-size:13px; opacity:0.7;'>{count_20:,} / {n_total:,} kayıt</div>",
            unsafe_allow_html=True,
        )
    # Tarih & Gün kolonlarını report_df'e ekle (daily_agg için gerekli)
    if isinstance(df_full, pd.DataFrame) and date_col and (date_col in df_full.columns):
        dt_series = pd.to_datetime(df_full.loc[test_idx, date_col], errors="coerce")
        date_only = pd.to_datetime(dt_series).dt.normalize()

        day_map = {
            0: "Pazartesi",
            1: "Salı",
            2: "Çarşamba",
            3: "Perşembe",
            4: "Cuma",
            5: "Cumartesi",
            6: "Pazar",
        }
        day_name = date_only.dt.weekday.map(day_map)

        # aynı kolonları tekrar tekrar insert etmemek için güvenli davranalım
        if "Tarih" not in report_df.columns:
            report_df.insert(0, "Tarih", date_only.values)
        else:
            report_df["Tarih"] = date_only.values

        if "Gün" not in report_df.columns:
            report_df.insert(1, "Gün", day_name.values)
        else:
            report_df["Gün"] = day_name.values


    # ------------------ Günlük Bazda Ortalama Hata Özeti ------------------
    if "Tarih" in report_df.columns:
        st.markdown("---")
        st.subheader("📅 Günlük Bazda Ortalama Hata")

        daily_src = report_df.dropna(subset=["Tarih"]).copy()

        # Günlük toplulaştırma (istenen kolonlar)
        daily_agg = (
            daily_src.groupby("Tarih", dropna=True)
            .agg(
                Gercek=("Gerçek", "mean"),
                Tahmin=("Tahmin", "mean"),
                Ortalama_Hata=("Hata", "mean"),
                Ortalama_Hata_Yuzde=("Hata (%)", "mean"),
                Ortalama_Mutlak_Hata_Yuzde=("Hata (%)", lambda x: float(np.mean(np.abs(x)))),
            )
            .reset_index()
        )

        # Gün ismini ekle (report_df'den alınır)
        if "Gün" in daily_src.columns:
            day_lookup = daily_src[["Tarih", "Gün"]].drop_duplicates()
            daily_agg = daily_agg.merge(day_lookup, on="Tarih", how="left")

        # KPI'lar (opsiyonel kalsın)
        d1, d2, d3 = st.columns(3)
        d1.metric("Gün Sayısı", f"{daily_agg['Tarih'].nunique():,}")
        d2.metric("Ort. Hata (%)", f"{daily_agg['Ortalama_Hata_Yuzde'].mean():.2f}%")
        d3.metric("Ort. |Hata%|", f"{daily_agg['Ortalama_Mutlak_Hata_Yuzde'].mean():.2f}%")

        st.caption("Günlük özet: aynı tarihe düşen kayıtların ortalama değerleridir.")

        # Tablo kontrolü
        show_days = st.slider(
            "Günlük özet tabloda göster (son N gün)",
            5,
            max(5, len(daily_agg)),
            min(20, max(5, len(daily_agg))),
            key="cf_daily_n",
        )

        daily_view = daily_agg.sort_values("Tarih", ascending=False).head(int(show_days))

        cols = [
            "Tarih",
            "Gün",
            "Gercek",
            "Tahmin",
            "Ortalama_Hata",
            "Ortalama_Hata_Yuzde",
            "Ortalama_Mutlak_Hata_Yuzde",
        ]
        # Gün kolonu yoksa düşür (tarih bulunup gün bulunamazsa)
        cols = [c for c in cols if c in daily_view.columns]

        st.dataframe(daily_view[cols], use_container_width=True)

        # Trend grafik (Mutlak Hata%)
        st.markdown("#### 📈 Günlük Ortalama |Hata%| Trend")
        trend = daily_agg.sort_values("Tarih")[["Tarih", "Ortalama_Mutlak_Hata_Yuzde"]].set_index("Tarih")
        st.line_chart(trend, height=220)

        # En kötü / en iyi günler (Mutlak Hata% ile)
        worst = daily_agg.sort_values("Ortalama_Mutlak_Hata_Yuzde", ascending=False).head(10)
        best = daily_agg.sort_values("Ortalama_Mutlak_Hata_Yuzde", ascending=True).head(10)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 🔴 En Kötü 10 Gün (|Hata%|)")
            st.dataframe(worst[cols], use_container_width=True)
        with c2:
            st.markdown("#### 🟢 En İyi 10 Gün (|Hata%|)")
            st.dataframe(best[cols], use_container_width=True)

    else:
        st.info("Günlük özet için 'Tarih' kolonu bulunamadı.")

    # ------------------ Gerçek - Tahmin - Hata Grafiği ------------------
    st.markdown("### 📈 Gerçek - Tahmin - Hata Çizgi Grafiği")

    use_plotly = st.checkbox(
        "İnteraktif grafik (Plotly)",
        value=True,
        key="cf_rep_plotly",
    )

    if use_plotly:
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            fig = make_subplots(specs=[[{"secondary_y": True}]])

            # Gerçek
            fig.add_trace(
                go.Scatter(
                    y=report_df["Gerçek"],
                    mode="lines",
                    name="Gerçek",
                    line=dict(width=2),
                ),
                secondary_y=False,
            )

            # Tahmin
            fig.add_trace(
                go.Scatter(
                    y=report_df["Tahmin"],
                    mode="lines",
                    name="Tahmin",
                    line=dict(width=2, dash="dot"),
                ),
                secondary_y=False,
            )

            # Hata (secondary axis)
            fig.add_trace(
                go.Scatter(
                    y=report_df["Hata"],
                    mode="lines",
                    name="Hata (G-T)",
                    line=dict(width=1),
                    opacity=0.6,
                ),
                secondary_y=True,
            )

            fig.update_layout(
                height=380,
                xaxis_title="Gözlem",
                legend=dict(orientation="h", y=1.1),
            )

            fig.update_yaxes(title_text="Gerçek / Tahmin", secondary_y=False)
            fig.update_yaxes(title_text="Hata", secondary_y=True)

            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.info(f"Plotly çizilemedi: {e}")
            st.line_chart(report_df[["Gerçek", "Tahmin", "Hata"]], height=320)

    else:
        st.line_chart(report_df[["Gerçek", "Tahmin", "Hata"]], height=320)



    # ------------------ Feature Kalitesi ve Etiketi ------------------
    st.markdown("---")
    st.subheader("🧩 Feature Kalitesi ve Etiketi")

    df_eff = _get_feature_effect_df(model, X_columns)

    feat_df = df_eff.rename(
        columns={
            "EffectRaw": "Etki",
            "ImportanceAbs": "Önem (|Etki|)",
            "Direction": "Etki Yönü",
        }
    ).copy()

    run_quality = st.checkbox("Feature kalite etiketini hesapla (Top feature’larda)", value=True, key="cf_rep_quality")
    top_for_quality = st.slider("Analiz edilecek top feature sayısı", 10, min(80, len(feat_df)), min(30, len(feat_df)), key="cf_rep_qtop")

    if run_quality and isinstance(df_full, pd.DataFrame) and isinstance(X_full, pd.DataFrame):
        base_q = pd.DataFrame({"Feature": feat_df["Feature"].tolist()})
        base_q = _make_feature_quality_labels(
            feat_df=base_q,
            df_full=df_full,
            X_full=X_full,
            test_idx=test_idx,
            report_df=report_df,
            top_for_quality=int(top_for_quality),
        )
        feat_df = feat_df.merge(base_q[["Feature", "Etiket", "Hata Yayılımı", "Hata% Yayılımı"]], on="Feature", how="left")
        feat_df["Etiket"] = feat_df["Etiket"].fillna("⚪ Hesaplanmadı")
    else:
        feat_df["Etiket"] = "⚪ Hesaplanmadı"

    top_n_tab = st.slider("Tabloda göster (Top N)", 10, min(250, len(feat_df)), min(40, len(feat_df)), key="cf_rep_topn")
    st.dataframe(feat_df.head(int(top_n_tab)), use_container_width=True)

    # ------------------ Feature Etkisi (Görsel) ------------------
    st.markdown("---")
    st.subheader("🎯 Feature Etkisi (Görsel)")

    # 3 mod: toplam / dummy / sayısal
    view_mode = st.radio(
        "Görünüm",
        ["Toplam (Dummy + Sayısal)", "Sadece Dummy", "Sadece Sayısal"],
        horizontal=True,
        key="cf_rep_vis_mode",
    )

    top_n_vis = st.slider("Grafikte Top N", 5, 80, 25, key="cf_rep_vis_topn")

    if view_mode == "Toplam (Dummy + Sayısal)":
        total_df = _build_total_view(df_eff, numeric_feats=numeric_feats, dummy_feats=dummy_feats).head(int(top_n_vis))
        total_df = total_df.rename(columns={"Group": "Feature"})
        _plot_bar(
            total_df,
            x_col="Importance",
            y_col="Feature",
            color_col="Type",
            title="Toplam Feature Etkisi (Dummy base toplanır + Sayısal tek tek)",
        )
        st.caption("Toplam görünüm: Dummy kolonlar base’e göre toplanır (örn Kanal_* -> Kanal), sayısallar tek tek gösterilir.")

    elif view_mode == "Sadece Dummy":
        dum = df_eff[df_eff["Feature"].isin(dummy_feats)].copy()
        dum = dum.sort_values("ImportanceAbs", ascending=False).head(int(top_n_vis))
        dum["Type"] = "Dummy"
        _plot_bar(
            dum.rename(columns={"ImportanceAbs": "Importance"}),
            x_col="Importance",
            y_col="Feature",
            color_col=None,
            title="Sadece Dummy Feature Etkisi (Detay)",
        )

    else:  # Sadece Sayısal
        num = df_eff[df_eff["Feature"].isin(numeric_feats)].copy()
        num = num.sort_values("ImportanceAbs", ascending=False).head(int(top_n_vis))
        num["Type"] = "Sayısal"
        _plot_bar(
            num.rename(columns={"ImportanceAbs": "Importance"}),
            x_col="Importance",
            y_col="Feature",
            color_col=None,
            title="Sadece Sayısal Feature Etkisi",
        )

    # ------------------ Scatter + Residual özeti ------------------
    st.markdown("---")
    st.subheader("🎯 Gerçek vs Tahmin Dağılımı")
    scatter_df = pd.DataFrame({"Gerçek": report_df["Gerçek"].values, "Tahmin": report_df["Tahmin"].values})
    st.scatter_chart(scatter_df, x="Gerçek", y="Tahmin")

    st.subheader("📉 Rezidü Özeti")
    st.write(
        f"Rezidü ortalaması: **{float(np.mean(residuals)):.3f}**, "
        f"rezidü std: **{float(np.std(residuals)):.3f}**"
    )
    if abs(float(np.mean(residuals))) < abs(float(np.std(residuals))) * 0.1:
        st.success("✅ Rezidülerin ortalaması 0'a yakın → Model yanlı değil.")
    else:
        st.warning("⚠️ Rezidülerde yanlılık var → Model sistematik hata yapıyor olabilir.")
    

    # ------------------ SHAP (opsiyonel) ------------------
    st.markdown("---")
    st.subheader("🧠 SHAP Açıklanabilirlik (Opsiyonel)")

    enable_shap = st.checkbox("SHAP analizi aç", value=False, key="cf_rep_shap")
    if not enable_shap:
        st.caption("SHAP ağır olabilir; ihtiyaç olursa aç.")
    else:
        if "cf_X_test_scaled" not in st.session_state:
            st.warning("SHAP için cf_X_test_scaled bulunamadı. Modeli tekrar eğit / kaydet.")
        else:
            try:
                import shap
                import matplotlib

                matplotlib.use("Agg")
                import matplotlib.pyplot as plt

                X_test_scaled = st.session_state["cf_X_test_scaled"]
                X_shap = pd.DataFrame(X_test_scaled, columns=X_columns)

                cls = model.__class__.__name__
                tree_like = {"RandomForestRegressor", "DecisionTreeRegressor", "LGBMRegressor", "XGBRegressor"}

                if cls in tree_like:
                    explainer = shap.TreeExplainer(model)
                    shap_values = explainer.shap_values(X_shap)
                else:
                    explainer = shap.LinearExplainer(model, X_shap)
                    shap_values = explainer.shap_values(X_shap)

                st.success("✅ SHAP değerleri hesaplandı!")

                # ------------------ SHAP SUMMARY ------------------
                st.write("### 🌍 Özelliklerin Tahmine Etki Dağılımı (Summary)")
                fig_summary = plt.figure(figsize=(8, 5))
                shap.summary_plot(shap_values, X_shap, feature_names=X_columns, show=False)
                st.pyplot(fig_summary)
                plt.clf()

                # ------------------ SHAP FORCE ------------------
                st.write("### 🎯 Tek Gözlem İçin SHAP (Force)")
                force_index = st.slider(
                    "İncelenecek gözlem",
                    0,
                    max(0, len(X_shap) - 1),
                    0,
                    key="cf_rep_force",
                )

                st.write(f"**Tahmin:** {float(preds[force_index]):.3f}")
                if isinstance(y_test, pd.Series):
                    st.write(f"**Gerçek:** {float(y_test.iloc[force_index]):.3f}")

                exp = shap.Explanation(
                    values=shap_values[force_index],
                    base_values=explainer.expected_value,
                    data=X_shap.iloc[force_index],
                    feature_names=X_columns,
                )

                shap.plots.force(
                    exp.base_values,
                    exp.values,
                    exp.data,
                    matplotlib=True,
                    show=False,
                )

                fig_force = plt.gcf()
                fig_force.set_size_inches(10, 2.6)
                st.pyplot(fig_force)
                plt.clf()

                st.caption("🔵 pozitif etki tahmini artırır, 🔴 negatif etki tahmini düşürür.")

            except Exception as e:
                st.error(f"SHAP çalıştırılamadı: {e}")
                st.info("SHAP için 'shap' kurulumu gerekebilir ve bazı modellerde uyumsuzluk çıkabilir.")
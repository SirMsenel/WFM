# modules/call_forecast/monitoring.py
import numpy as np
import pandas as pd
import streamlit as st


def _detect_date_col(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        parsed = pd.to_datetime(df[col], errors="coerce")
        if parsed.notna().mean() > 0.8:
            return col
    return None


def _detect_target_col(df: pd.DataFrame, date_col: str) -> str | None:
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if date_col in numeric_cols:
        numeric_cols.remove(date_col)
    if not numeric_cols:
        return None
    return max(numeric_cols, key=lambda c: df[c].notna().sum())


def _infer_frequency_minutes(dt: pd.Series) -> float | None:
    s = dt.dropna().sort_values()
    if len(s) < 3:
        return None
    diffs = s.diff().dropna().dt.total_seconds() / 60
    if diffs.empty:
        return None
    return float(diffs.median())


def _apply_date_filter(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    s = df[date_col].dropna()
    if s.empty:
        return df

    min_dt = s.min()
    max_dt = s.max()
    sig = (min_dt.date(), max_dt.date())

    # dataset değişince state reset
    if st.session_state.get("cf_monitor_date_sig") != sig:
        st.session_state["cf_monitor_date_sig"] = sig
        st.session_state["cf_monitor_date_preset"] = "Tümü"
        st.session_state["cf_monitor_date_range"] = (min_dt.date(), max_dt.date())

    preset_options = ["Tümü", "Son 7 gün", "Son 30 gün", "Son 90 gün"]

    def _preset_to_range(p: str):
        if p == "Tümü":
            return (min_dt.date(), max_dt.date())
        if p == "Son 7 gün":
            return ((max_dt - pd.Timedelta(days=6)).date(), max_dt.date())
        if p == "Son 30 gün":
            return ((max_dt - pd.Timedelta(days=29)).date(), max_dt.date())
        return ((max_dt - pd.Timedelta(days=89)).date(), max_dt.date())

    # ✅ preset değişince slider range'i güncelle
    def _on_preset_change():
        p = st.session_state["cf_monitor_date_preset"]
        st.session_state["cf_monitor_date_range"] = _preset_to_range(p)

    st.selectbox(
        "⏱️ Hızlı Tarih Seçimi",
        preset_options,
        index=preset_options.index(st.session_state.get("cf_monitor_date_preset", "Tümü")),
        key="cf_monitor_date_preset",
        on_change=_on_preset_change,
    )

    st.caption("📅 İstersen aralığı buradan manuel ayarlayabilirsin:")
    manual_start, manual_end = st.slider(
        "Tarih aralığı",
        min_value=min_dt.date(),
        max_value=max_dt.date(),
        value=st.session_state.get("cf_monitor_date_range", (min_dt.date(), max_dt.date())),
        key="cf_monitor_date_range",  # ✅ slider state tek yerde
    )

    start_ts = pd.Timestamp(manual_start)
    end_ts = pd.Timestamp(manual_end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    return df[(df[date_col] >= start_ts) & (df[date_col] <= end_ts)].copy()

def render():
    st.subheader("Grafik İzleme (Çağrı Sayıları)")

    df = st.session_state.get("cf_full_df")  # bizde ana veri buradan dönüyor
    if df is None or df.empty:
        st.info("Önce Veri Kaynağı ekranından veri yükle.")
        return

    df = df.copy()

    # --- otomatik kolon bul
    auto_date = _detect_date_col(df)
    if auto_date is None:
        st.error("❌ Tarih kolonu bulunamadı (parse oranı %80 üstü kolon yok).")
        return

    auto_target = _detect_target_col(df, auto_date)
    if auto_target is None:
        st.error("❌ Sayısal target (çağrı sayısı) bulunamadı.")
        return

    # --- seçimler
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        date_col = st.selectbox("Tarih kolonu", options=list(df.columns), index=list(df.columns).index(auto_date))
    with c2:
        target_col = st.selectbox(
            "Çağrı kolonu (target)",
            options=[auto_target] + [c for c in df.columns if c != auto_target],
        )
    with c3:
        agg = st.selectbox("Görüntüleme", ["Otomatik", "Günlük", "Saatlik", "30dk"], index=0)

    # --- parse / hazırlık
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df[df[date_col].notna()].copy()
    df = df.sort_values(date_col)

    if df.empty:
        st.warning("Tarih parse sonrası veri boş görünüyor.")
        return

    # ✅ Tarih filtresi (tüm grafikler buna göre)
    df = _apply_date_filter(df, date_col)
    df = df.sort_values(date_col)

    if df.empty:
        st.warning("Seçilen tarih aralığında veri yok.")
        return

    # --- frekans tahmini
    median_min = _infer_frequency_minutes(df[date_col])

    # otomatik agg seçimi
    if agg == "Otomatik":
        if median_min is None:
            agg_mode = "Günlük"
        elif median_min <= 30.1:
            agg_mode = "30dk"
        elif median_min <= 60.1:
            agg_mode = "Saatlik"
        else:
            agg_mode = "Günlük"
    else:
        agg_mode = agg

    # --- KPI
    x = pd.to_numeric(df[target_col], errors="coerce").fillna(0)
    total_calls = float(x.sum())
    max_calls = float(x.max()) if len(x) else 0.0
    min_calls = float(x.min()) if len(x) else 0.0

    daily_tmp = df.copy()
    daily_tmp["__day__"] = daily_tmp[date_col].dt.date
    daily_avg = float(pd.to_numeric(daily_tmp.groupby("__day__")[target_col].sum(), errors="coerce").mean())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Toplam Çağrı", f"{total_calls:,.0f}")
    k2.metric("Günlük Ortalama", f"{daily_avg:,.0f}")
    k3.metric("Maksimum", f"{max_calls:,.0f}")
    k4.metric("Minimum", f"{min_calls:,.0f}")

    st.markdown("---")

    # --- zaman serisi (agg)
    ts = df[[date_col, target_col]].copy()
    ts[target_col] = pd.to_numeric(ts[target_col], errors="coerce").fillna(0)

    if agg_mode == "Günlük":
        ts["bucket"] = ts[date_col].dt.floor("D")
    elif agg_mode == "Saatlik":
        ts["bucket"] = ts[date_col].dt.floor("H")
    else:  # 30dk
        ts["bucket"] = ts[date_col].dt.floor("30min")

    series = ts.groupby("bucket", as_index=False)[target_col].sum().rename(columns={"bucket": "Zaman"})
    series = series.sort_values("Zaman")

    st.subheader("📈 Zaman Serisi")
    st.line_chart(series.set_index("Zaman")[target_col], height=320)

    # --- ek kırılımlar
    st.markdown("---")
    st.subheader("🧭 Kırılımlar")

    colA, colB = st.columns(2)
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    with colA:
        st.caption("Haftanın günü dağılımı (toplam)")
        tmp = df.copy()
        tmp["weekday"] = tmp[date_col].dt.day_name()
        w = tmp.groupby("weekday", as_index=False)[target_col].sum()
        w["__o__"] = w["weekday"].apply(lambda x: order.index(x) if x in order else 99)
        w = w.sort_values("__o__").drop(columns="__o__")
        st.bar_chart(w.set_index("weekday")[target_col], height=320)

    with colB:
        if agg_mode in ["Saatlik", "30dk"]:
            st.caption("Saat dağılımı (toplam)")
            tmp = df.copy()
            tmp["hour"] = tmp[date_col].dt.hour
            h = tmp.groupby("hour", as_index=False)[target_col].sum().sort_values("hour")
            st.bar_chart(h.set_index("hour")[target_col], height=320)
        else:
            st.caption("Ay dağılımı (toplam)")
            tmp = df.copy()
            tmp["month"] = tmp[date_col].dt.month
            m = tmp.groupby("month", as_index=False)[target_col].sum().sort_values("month")
            st.bar_chart(m.set_index("month")[target_col], height=320)

    st.markdown("---")
    st.subheader("🔥 Isı Haritası (Pivot)")

    heatmap_mode = st.selectbox(
        "Isı Haritası Görünümü",
        [
            "Otomatik",
            "Weekday x Slot(30dk)",
            "Weekday x Hour (intraday)",
            "Month x Weekday (daily)",
            "Week x Weekday (daily)",
        ],
        index=0,
    )

    # otomatik seçim
    if heatmap_mode == "Otomatik":
        if agg_mode == "30dk":
            heatmap_mode = "Weekday x Slot(30dk)"
        elif agg_mode in ["Saatlik"]:
            heatmap_mode = "Weekday x Hour (intraday)"
        else:
            heatmap_mode = "Month x Weekday (daily)"

    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    def _slot_label(slot: int) -> str:
        # slot: 1..48
        start_min = (slot - 1) * 30
        end_min = start_min + 30
        sh, sm = divmod(start_min, 60)
        eh, em = divmod(end_min, 60)
        # 24:00 gösterimi
        if eh == 24:
            return f"{sh:02d}:{sm:02d}-{24:02d}:{0:02d}"
        return f"{sh:02d}:{sm:02d}-{eh:02d}:{em:02d}"

    if heatmap_mode == "Weekday x Slot(30dk)":
        tmp = df.copy()
        tmp["weekday"] = tmp[date_col].dt.day_name()

        hour = tmp[date_col].dt.hour
        minute = tmp[date_col].dt.minute
        tmp["slot30"] = hour * 2 + (minute // 30) + 1  # 1..48

        pivot = tmp.pivot_table(
            index="weekday",
            columns="slot30",
            values=target_col,
            aggfunc="sum",
            fill_value=0,
        )

        pivot = pivot.reindex([d for d in order if d in pivot.index])
        pivot = pivot.reindex(columns=range(1, 49), fill_value=0)

        # kolonları label'a çevir (00:00-00:30 gibi)
        pivot.columns = [_slot_label(int(c)) for c in pivot.columns]

        st.dataframe(pivot, use_container_width=True, height=320)
        st.caption("Satır: weekday, sütun: 30dk saat aralığı")

    elif heatmap_mode == "Weekday x Hour (intraday)":
        tmp = df.copy()
        tmp["weekday"] = tmp[date_col].dt.day_name()
        tmp["hour"] = tmp[date_col].dt.hour

        pivot = tmp.pivot_table(
            index="weekday",
            columns="hour",
            values=target_col,
            aggfunc="sum",
            fill_value=0,
        )

        pivot = pivot.reindex([d for d in order if d in pivot.index])
        pivot = pivot.reindex(columns=range(0, 24), fill_value=0)

        st.dataframe(pivot, use_container_width=True, height=320)
        st.caption("Satır: weekday, sütun: saat (0–23)")

    elif heatmap_mode == "Month x Weekday (daily)":
        tmp = df.copy()
        tmp["month"] = tmp[date_col].dt.month
        tmp["weekday"] = tmp[date_col].dt.day_name()

        pivot = tmp.pivot_table(
            index="month",
            columns="weekday",
            values=target_col,
            aggfunc="sum",
            fill_value=0,
        )

        pivot = pivot.reindex(columns=[d for d in order if d in pivot.columns])
        st.dataframe(pivot, use_container_width=True, height=320)

    else:  # Week x Weekday (daily)
        tmp = df.copy()
        tmp["week"] = tmp[date_col].dt.isocalendar().week.astype(int)
        tmp["weekday"] = tmp[date_col].dt.day_name()

        pivot = tmp.pivot_table(
            index="week",
            columns="weekday",
            values=target_col,
            aggfunc="sum",
            fill_value=0,
        )

        pivot = pivot.reindex(columns=[d for d in order if d in pivot.columns])
        st.dataframe(pivot, use_container_width=True, height=320)
        
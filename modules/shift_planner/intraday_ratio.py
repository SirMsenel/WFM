# modules/shift_planner/intraday_ratio.py
import numpy as np
import pandas as pd
import streamlit as st

# ----------------------------
# STATE
# ----------------------------
def _ensure_state():
    st.session_state.setdefault("sp_intraday_raw_df", None)

    # Kaydedilmiş profil listesi
    st.session_state.setdefault("sp_ratio_profiles", [])

    # aktif seçili profil
    st.session_state.setdefault("sp_active_ratio_profile_name", None)
    st.session_state.setdefault("sp_active_ratio_profile_df", None)

    # preview
    st.session_state.setdefault("sp_ratio_preview_df", None)
    st.session_state.setdefault("sp_ratio_preview_meta", None)


def _guess_datetime_col(df: pd.DataFrame) -> str | None:
    best = None
    best_rate = 0.0
    for c in df.columns:
        s = pd.to_datetime(df[c], errors="coerce")
        rate = float(s.notna().mean())
        if rate > best_rate and rate >= 0.70:
            best_rate = rate
            best = c
    return best


def _guess_calls_col(df: pd.DataFrame) -> str | None:
    num = df.select_dtypes(include=["int64", "int32", "float64", "float32"]).columns.tolist()
    if not num:
        return None
    return max(num, key=lambda c: df[c].notna().sum())


def _make_slot_48(dt_series: pd.Series) -> pd.Series:
    dt_series = pd.to_datetime(dt_series, errors="coerce")
    h = dt_series.dt.hour.fillna(0).astype(int)
    m = dt_series.dt.minute.fillna(0).astype(int)
    slot = h * 2 + (m // 30) + 1
    return slot.clip(lower=1, upper=48)


def _iqr_bounds(s: pd.Series, k: float) -> tuple[float, float]:
    x = pd.to_numeric(s, errors="coerce").dropna().astype(float)
    if x.empty:
        return (float("-inf"), float("inf"))
    q1 = float(x.quantile(0.25))
    q3 = float(x.quantile(0.75))
    iqr = q3 - q1
    lo = q1 - k * iqr
    hi = q3 + k * iqr
    return float(lo), float(hi)


def _apply_iqr(df: pd.DataFrame, value_col: str, k: float, mode: str) -> tuple[pd.DataFrame, dict]:
    """
    mode:
      - "drop": aykırıları sil
      - "cap":  aykırıları alt/üst sınıra eşitle (winsorize)
    """
    out = df.copy()
    out[value_col] = pd.to_numeric(out[value_col], errors="coerce")

    lo, hi = _iqr_bounds(out[value_col], k=k)

    before_n = int(len(out))
    before_na = int(out[value_col].isna().sum())

    if mode == "drop":
        out = out[out[value_col].notna()].copy()
        out = out[(out[value_col] >= lo) & (out[value_col] <= hi)].copy()
        after_n = int(len(out))
        changed = int(before_n - after_n)
        info = {
            "iqr_used": True,
            "iqr_mode": "drop",
            "iqr_k": float(k),
            "iqr_lo": float(lo),
            "iqr_hi": float(hi),
            "rows_before": before_n,
            "rows_after": after_n,
            "rows_removed": changed,
            "value_na_before": before_na,
        }
        return out, info

    # cap (winsorize)
    out = out[out[value_col].notna()].copy()
    x = out[value_col].astype(float)
    capped = x.clip(lower=lo, upper=hi)
    changed = int((capped != x).sum())
    out[value_col] = capped
    after_n = int(len(out))
    info = {
        "iqr_used": True,
        "iqr_mode": "cap",
        "iqr_k": float(k),
        "iqr_lo": float(lo),
        "iqr_hi": float(hi),
        "rows_before": before_n,
        "rows_after": after_n,
        "values_capped": changed,
        "value_na_before": before_na,
    }
    return out, info


def _build_ratio_profile(
    df: pd.DataFrame,
    dt_col: str,
    calls_col: str,
    use_iqr: bool,
    k: float,
    iqr_mode: str,
):
    tmp = df.copy()

    tmp[dt_col] = pd.to_datetime(tmp[dt_col], errors="coerce")
    tmp = tmp[tmp[dt_col].notna()].copy()

    tmp[calls_col] = pd.to_numeric(tmp[calls_col], errors="coerce")
    tmp = tmp[tmp[calls_col].notna()].copy()

    # slot ve gün
    tmp["__slot__"] = _make_slot_48(tmp[dt_col])
    tmp["__dow__"] = tmp[dt_col].dt.dayofweek  # 0=Mon
    dow_map = {
        0: "Pazartesi",
        1: "Salı",
        2: "Çarşamba",
        3: "Perşembe",
        4: "Cuma",
        5: "Cumartesi",
        6: "Pazar",
    }
    tmp["Gün"] = tmp["__dow__"].map(dow_map)

    base_before = int(len(tmp))
    iqr_info = {"iqr_used": False}

    if use_iqr:
        tmp, iqr_info = _apply_iqr(tmp, calls_col, k=float(k), mode=iqr_mode)
        iqr_info["iqr_used"] = True

    base_after = int(len(tmp))

    # Gün x Slot toplam
    grp = (
        tmp.groupby(["Gün", "__dow__", "__slot__"], as_index=False)[calls_col]
        .sum()
        .rename(columns={calls_col: "Çağrı"})
    )

    # her gün 48 slotu tamamla
    all_days = [
        (0, "Pazartesi"),
        (1, "Salı"),
        (2, "Çarşamba"),
        (3, "Perşembe"),
        (4, "Cuma"),
        (5, "Cumartesi"),
        (6, "Pazar"),
    ]
    full = []
    for d_i, d_name in all_days:
        base = pd.DataFrame({"__dow__": d_i, "Gün": d_name, "__slot__": np.arange(1, 49)})
        merged = base.merge(grp[grp["__dow__"] == d_i], on=["__dow__", "Gün", "__slot__"], how="left")
        merged["Çağrı"] = merged["Çağrı"].fillna(0.0)
        full.append(merged)
    full = pd.concat(full, ignore_index=True)

    # oran
    day_total = full.groupby("__dow__")["Çağrı"].transform("sum")
    full["Oran"] = np.where(day_total > 0, full["Çağrı"] / day_total, 0.0)
    full["Oran(%)"] = (full["Oran"] * 100).round(4)

    # aralık yazısı
    s = full["__slot__"].astype(int)
    start_min = (s - 1) * 30
    sh = (start_min // 60).astype(int)
    sm = (start_min % 60).astype(int)
    end_min = start_min + 30
    eh = (end_min // 60).astype(int)
    em = (end_min % 60).astype(int)
    full["Aralık"] = (
        sh.astype(str).str.zfill(2)
        + ":"
        + sm.astype(str).str.zfill(2)
        + " - "
        + eh.astype(str).str.zfill(2)
        + ":"
        + em.astype(str).str.zfill(2)
    )

    profile_df = full[["__dow__", "Gün", "__slot__", "Aralık", "Çağrı", "Oran(%)"]].copy()
    profile_df = profile_df.rename(columns={"__slot__": "Slot"})

    meta = {
        "dt_col": dt_col,
        "calls_col": calls_col,
        "rows_used_before_iqr": base_before,
        "rows_used_after_iqr": base_after,
        **iqr_info,
    }
    return profile_df, meta


def _render_day_tables(profile_df: pd.DataFrame):
    """
    Üstte 4 gün, altta 3 gün yan yana.
    Tablo kolonları: Gün, Aralık, Oran(%)
    """
    order = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    df = profile_df.copy()
    df["Gün"] = pd.Categorical(df["Gün"], categories=order, ordered=True)
    df = df.sort_values(["Gün", "Slot"])

    day_groups = {
        d: df[df["Gün"] == d][["Gün", "Aralık", "Oran(%)"]].reset_index(drop=True)
        for d in order
    }

    st.markdown("#### 📋 Gün Bazında Oran Tabloları")
    st.caption("Her gün için 48 slot toplamı ~%100 olacak şekilde normalize edilir.")

    top_days = order[:4]
    bot_days = order[4:]

    cols_top = st.columns(4)
    for i, d in enumerate(top_days):
        with cols_top[i]:
            st.markdown(f"**{d}**")
            st.dataframe(day_groups[d], use_container_width=True, hide_index=True, height=420)

    cols_bot = st.columns(3)
    for i, d in enumerate(bot_days):
        with cols_bot[i]:
            st.markdown(f"**{d}**")
            st.dataframe(day_groups[d], use_container_width=True, hide_index=True, height=420)


# ----------------------------
# UI
# ----------------------------
def render():
    _ensure_state()

    st.subheader("📊 30 dk Oran Profili (Gün × Slot)")
    st.caption("30 dakikalık veriden her gün için 48 slotun yüzde dağılımını üretip kaydediyoruz.")
    st.markdown("---")

    # ----------------------------
    # 1) Veri yükleme
    # ----------------------------
    st.markdown("### 1) Veri Yükleme")

    src = st.radio("Kaynak", ["Dosya (CSV/Excel)", "Database (yakında)"], horizontal=True, key="sp_ratio_src")

    if src == "Database (yakında)":
        st.info("DB bağlantısı henüz yok. Şimdilik dosya ile devam ediyoruz.")
    else:
        up = st.file_uploader("CSV / Excel yükle", type=["csv", "xlsx"], key="sp_ratio_upload")
        if up is not None:
            try:
                df = pd.read_csv(up) if up.name.lower().endswith(".csv") else pd.read_excel(up)
                st.session_state["sp_intraday_raw_df"] = df
                st.success(f"✅ Yüklendi: {df.shape[0]:,} satır × {df.shape[1]:,} kolon")
                with st.expander("Kolonlar", expanded=False):
                    st.write(list(df.columns))
            except Exception as e:
                st.error(f"Dosya okunamadı: {e}")
                return

    df_raw = st.session_state.get("sp_intraday_raw_df")
    if df_raw is None or not isinstance(df_raw, pd.DataFrame) or df_raw.empty:
        st.info("Devam etmek için veri yükle.")
        return

    st.markdown("---")

    # ----------------------------
    # 2) Kolon eşleme + IQR
    # ----------------------------
    st.markdown("### 2) Kolon Seçimi ve Temizleme")

    guess_dt = _guess_datetime_col(df_raw)
    guess_calls = _guess_calls_col(df_raw)

    left, right = st.columns([1.6, 1.4])

    with left:
        st.markdown("#### 🧩 Kolon Eşleme")
        st.caption("Oran hesabı için bir tarih/saat ve bir çağrı sayısı kolonu seçiyoruz.")

        dt_col = st.selectbox(
            "Tarih/Saat kolonu",
            options=df_raw.columns.tolist(),
            index=(df_raw.columns.get_loc(guess_dt) if guess_dt in df_raw.columns else 0),
            key="sp_ratio_dtcol",
        )
        calls_col = st.selectbox(
            "Çağrı sayısı kolonu",
            options=df_raw.columns.tolist(),
            index=(df_raw.columns.get_loc(guess_calls) if guess_calls in df_raw.columns else 0),
            key="sp_ratio_callcol",
        )

        parsed_rate = float(pd.to_datetime(df_raw[dt_col], errors="coerce").notna().mean())
        num_rate = float(pd.to_numeric(df_raw[calls_col], errors="coerce").notna().mean())
        m1, m2 = st.columns(2)
        m1.metric("Tarih parse oranı", f"{parsed_rate*100:.1f}%")
        m2.metric("Sayısal oran", f"{num_rate*100:.1f}%")

    with right:
        st.markdown("#### 🧼 IQR Temizleme")
        st.caption("Aykırıları **sil** veya **alt/üst sınıra eşitle** (winsorize).")

        use_iqr = st.checkbox("IQR aktif", value=False, key="sp_ratio_iqr")

        iqr_mode = st.selectbox(
            "Yöntem",
            ["Sil (drop)", "Sınıra Eşitle (cap)"],
            index=0,
            disabled=not use_iqr,
            key="sp_ratio_iqr_mode",
        )

        k = st.slider("IQR çarpanı (k)", 0.5, 3.5, 1.5, 0.1, disabled=not use_iqr, key="sp_ratio_iqr_k")
        st.info("DROP: satır siler • CAP: değeri kırpar", icon="ℹ️")

    iqr_mode_key = "drop" if iqr_mode.startswith("Sil") else "cap"

    st.markdown("---")

    # ----------------------------
    # 3) Profil üret + tablo görünümü
    # ----------------------------
    st.markdown("### 3) Oran Profili Üret")

    calc = st.button("⚙️ Profili Hesapla", use_container_width=True, key="sp_ratio_calc")

    if calc:
        try:
            prof, meta = _build_ratio_profile(
                df_raw,
                dt_col=dt_col,
                calls_col=calls_col,
                use_iqr=bool(use_iqr),
                k=float(k),
                iqr_mode=iqr_mode_key,
            )
            st.session_state["sp_ratio_preview_df"] = prof
            st.session_state["sp_ratio_preview_meta"] = meta
            st.success("✅ Profil hesaplandı.")
        except Exception as e:
            st.error(f"Profil hesaplanamadı: {e}")
            return

    prof = st.session_state.get("sp_ratio_preview_df")
    meta = st.session_state.get("sp_ratio_preview_meta")

    if prof is None or not isinstance(prof, pd.DataFrame):
        st.info("Önce profili hesapla.")
        return


    # ----------------------------
    # KPI (Öncesi / Sonrası)
    # ----------------------------
    if isinstance(meta, dict):
        st.markdown("#### 🧾 Özet (Öncesi / Sonrası)")

        b1, b2, b3, b4,b5= st.columns(5)

        before_n = int(meta.get("rows_used_before_iqr", 0))
        after_n = int(meta.get("rows_used_after_iqr", 0))
        iqr_used = bool(meta.get("iqr_used", False))
        iqr_mode = str(meta.get("iqr_mode", "-"))
        k_val = meta.get("iqr_k", None)

        # drop ise satır silinmiş olur, cap ise satır aynı kalır ama kırpılan değer sayısı olur
        removed = meta.get("rows_removed", 0)
        capped = meta.get("values_capped", 0)

        with b1:
            st.metric("📥 Satır (Önce)", f"{before_n:,}")
        with b2:
            st.metric("📤 Satır (Sonra)", f"{after_n:,}")
        with b3:
            st.metric("🧼 IQR", "Açık" if iqr_used else "Kapalı")
        with b4:
            if iqr_used and iqr_mode == "drop":
                st.metric("🗑️ Silinen Satır", f"{int(removed):,}")
            else:
                st.metric("🗑️ Silinen Satır", "0")
        with b5:
            if iqr_used and iqr_mode == "cap":
                st.metric("✂️ Kırpılan Değer", f"{int(capped):,}")
            else:
                st.metric("✂️ Kırpılan Değer", "0")

        st.markdown("---")
    # ✅ SADECE TABLOLAR (heatmap/line kaldırıldı)
    _render_day_tables(prof)

    st.markdown("---")

    # ----------------------------
    # 4) Kaydet
    # ----------------------------
    st.markdown("### 4) Kaydet")
    default_name = f"Profil_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}"
    name = st.text_input("Profil adı", value=default_name, key="sp_ratio_profile_name")

    if st.button("💾 Profili Kaydet", use_container_width=True, key="sp_ratio_save"):
        if not name.strip():
            st.error("Profil adı boş olamaz.")
            return

        profiles = st.session_state.get("sp_ratio_profiles", [])
        if any(p.get("name") == name.strip() for p in profiles):
            st.error("Bu isimde profil zaten var. Başka isim ver.")
            return

        profiles.append(
            {
                "name": name.strip(),
                "created_at": pd.Timestamp.now().isoformat(timespec="seconds"),
                "meta": meta,
                "profile_df": prof.copy(),
            }
        )
        st.session_state["sp_ratio_profiles"] = profiles

        # aktif yap
        st.session_state["sp_active_ratio_profile_name"] = name.strip()
        st.session_state["sp_active_ratio_profile_df"] = prof.copy()

        st.success("✅ Profil kaydedildi ve aktif edildi. (Kayıt Seçim ekranından yönetebilirsin)")
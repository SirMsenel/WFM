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
    from core.forecast_service import date_column
    return date_column(df)

def _guess_calls_col(df: pd.DataFrame) -> str | None:
    for name in ('cagri_sayisi','Çağrı','calls','Call_Count'):
        if name in df:
            return name
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

@st.cache_data(show_spinner=False,max_entries=8)
def _weekly_model(raw,week,dt_col,calls_col,previous,used):
    from core.interval_service import build_weekly_distribution
    return build_weekly_distribution(raw,week,dt_col,calls_col,previous,used)


def render():
    from core.data_cache import cached_calls
    from core.workspace_store import DEFAULT_DB,save_keys
    from core.interval_service import prepare_intervals,calendar_flags
    from core.charts import slot_heatmap
    from core.forecast_service import signature
    state=st.session_state
    st.subheader('Haftalık İnterval Dağılımı')
    st.caption('Altı geçmiş pencere, son tamamlanmış haftada karşılaştırılır. Başarı ağırlıkları ve yakın tarihe daha fazla ağırlık veren logaritmik hesapla 7 × 48 dağılım oluşturulur.')
    source=st.radio('30 dakikalık veri kaynağı',['Hazır Veritabanı','Dosya (CSV/Excel)'],horizontal=True,key='interval_source')
    if source=='Hazır Veritabanı':
        raw=cached_calls(str(state.get('workspace_db_path',DEFAULT_DB)),True)
        st.caption(f'Veritabanından otomatik alındı: {len(raw):,} kayıt.')
        if st.button('Veritabanını Yenile',key='interval_refresh'):
            cached_calls.clear()
            _weekly_model.clear()
            st.rerun()
    else:
        upload=st.file_uploader('30 dk çağrı verisi yükle',type=['csv','xlsx'],key='interval_upload')
        if upload is None:
            st.info('Dosya seçin veya hazır veritabanını kullanın.')
            return
        try:
            raw=pd.read_csv(upload) if upload.name.lower().endswith('.csv') else pd.read_excel(upload)
        except Exception as exc:
            st.error(f'Dosya okunamadı: {exc}')
            return
    a,b=st.columns(2)
    guess_dt=_guess_datetime_col(raw);guess_calls=_guess_calls_col(raw)
    date_col=a.selectbox('Tarih / saat sütunu',list(raw),index=list(raw).index(guess_dt) if guess_dt in raw else 0,key='interval_date_column')
    count_col=b.selectbox('Çağrı sütunu',list(raw),index=list(raw).index(guess_calls) if guess_calls in raw else 0,key='interval_calls_column')
    try:
        dates,_,_,quality=prepare_intervals(raw,date_col,count_col)
        next_monday=dates.max().date()+pd.Timedelta(days=7-dates.max().weekday())
        chosen=st.date_input('Dağılımın kullanılacağı hafta',value=next_monday,key='interval_target_week')
        week=pd.Timestamp(chosen)-pd.Timedelta(days=chosen.weekday())
        st.caption(f'Hafta: {week:%d.%m.%Y} → {week+pd.Timedelta(days=6):%d.%m.%Y}. Yakınlık ağırlığı: 1 / (1 + log(1 + yaş / 7)).')
        previous=state.get('interval_last_used_profile')
        result=_weekly_model(raw,str(week.date()),date_col,count_col,previous,state.get('interval_used_profiles',{}))
    except (ValueError,TypeError,KeyError) as exc:
        st.error(str(exc))
        return
    meta=result['meta']; profile=result['profile']
    c1,c2,c3=st.columns(3)
    c1.metric('Tam geçmiş gün',quality['Tam gün'])
    c2.metric('Dışlanan eksik/sıfır gün',quality['Eksik veya sıfır gün'])
    c3.metric('Matris','7 × 48')
    st.markdown('### Önerilen Haftalık Dağılım')
    slot_heatmap(profile)
    from core.navigation import sections
    def show_day():
        selected=st.selectbox('Gün',profile['Gün'].unique(),key='interval_plot_day')
        chart=profile[profile.Gün==selected].copy()
        chart['Saat']=chart.Slot.map(lambda n:f'{(n-1)//2:02d}:{((n-1)%2)*30:02d}')
        st.line_chart(chart.set_index('Saat')[['Oran(%)']])
        st.dataframe(chart[['Aralık','Oran(%)']],hide_index=True,use_container_width=True)
    def show_success():
        st.caption(f"Doğrulama: {meta['validation_start']} → {meta['validation_end']}. Bu haftanın verileri adayların eğitimine alınmaz; ağırlıklar bu haftadaki hata ile kalibre edilir.")
        st.dataframe(result['scores'],hide_index=True,use_container_width=True)
        st.bar_chart(result['scores'].set_index('Pencere')[['Başarı ağırlığı (%)']])
        st.caption(meta['baseline_name']+(' · MAE '+f"{meta['baseline_mae']:.4f} yüzde puan" if meta['baseline_mae'] is not None else ' · Yeterli kayıt yok'))
        day=st.selectbox('Doğrulama günü',profile.Gün.unique(),key='interval_validation_day')
        actual=result['actual_validation']; pred=result['predicted_validation']
        comparison=actual[actual.Gün==day][['Slot','Oran(%)']].merge(pred[pred.Gün==day][['Slot','Oran(%)']],on='Slot',suffixes=(' gerçek',' birleşim'))
        comparison['Saat']=comparison.Slot.map(lambda n:f'{(n-1)//2:02d}:{((n-1)%2)*30:02d}')
        st.line_chart(comparison.set_index('Saat')[['Oran(%) gerçek','Oran(%) birleşim']])
        st.caption('Birleşim aynı doğrulama haftasıyla kalibre edilmiştir; bu eğri bağımsız bir gelecek başarı garantisi değildir.')
    def show_effects():
        st.dataframe(calendar_flags(pd.date_range(week,periods=7)).reset_index(),hide_index=True,use_container_width=True)
        st.caption('Tarih etkileri çağrı tahminiyle aynı takvimden alınır. En az iki benzer gün varsa dağılıma katılır; örnek azsa temel dağılım korunur.')
        for note in meta['calendar_notes']:
            st.write('• '+note)
    sections('nav_interval_detail',{'Gün Dağılımı':show_day,'Başarı ve Ağırlıklar':show_success,'Takvim Etkileri':show_effects})
    st.download_button('7 × 48 Dağılım CSV İndir',profile.to_csv(index=False).encode('utf-8-sig'),'haftalik_interval.csv','text/csv')
    name=st.text_input('Profil adı',value=f'Hafta {week:%d.%m.%Y} · Ağırlıklı',key='interval_profile_label')
    if st.button('Dağılımı Kaydet ve Aktif Et',key='interval_save'):
        if not name.strip():
            st.error('Profil adı boş olamaz.')
            return
        snapshot={'name':name.strip(),'profile_df':profile.copy(),'created_at':pd.Timestamp.now().isoformat(),'meta':meta,
                  'scores':result['scores']}
        profiles=[p for p in state.get('sp_ratio_profiles',[]) if p.get('name')!=name.strip()]+[snapshot]
        state.update(sp_ratio_profiles=profiles,sp_active_ratio_profile_df=profile.copy(),
                     sp_active_ratio_profile_name=name.strip(),sp_active_ratio_profile_meta=meta,
                     sp_staffing_result_df=None,plan_ctx_confirmed=False)
        save_keys(state)
        st.success('Haftalık dağılım kaydedildi. Personel ihtiyacını bu hafta için yeniden hesaplayın.')

# Mesai Plani / Interval Dagilimi — bu ekranın / servisin uygulama kodu.
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
    from ortak.cagri_tahmin_servisi import date_column
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
def _weekly_model(raw,week,dt_col,calls_col,previous,used,use_iqr=False,iqr_k=1.5,iqr_mode="cap"):
    from ortak.interval_servisi import build_weekly_distribution
    return build_weekly_distribution(raw,week,dt_col,calls_col,previous,used,use_iqr,iqr_k,iqr_mode)



def matrix_table(profile):
    from ortak.cagri_tahmin_servisi import DAY_NAMES
    table=profile.pivot(index='Slot',columns='Gün',values='Oran(%)').reindex(index=range(1,49),columns=DAY_NAMES)
    table.index=[f'{(s-1)//2:02d}:{((s-1)%2)*30:02d}–{s//2:02d}:{(s%2)*30:02d}' for s in table.index]
    table.index.name='Saat aralığı'
    return table


def render():
    from ortak.veri_onbellegi import cached_calls
    from ortak.calisma_alani_deposu import DEFAULT_DB,save_keys
    from ortak.interval_servisi import prepare_intervals,calendar_flags
    from ortak.grafikler import slot_heatmap
    from ortak.cagri_tahmin_servisi import DAY_NAMES
    state=st.session_state
    st.subheader('Haftalık Çağrı Dağılımı')
    with st.expander('Veri kaynağı',expanded=False):
        source=st.radio('30 dakikalık veri',['Hazır Veritabanı','Dosya (CSV/Excel)'],horizontal=True,key='interval_source')
        raw=None
        if source=='Hazır Veritabanı':
            raw=cached_calls(str(state.get('workspace_db_path',DEFAULT_DB)),True)
            date_col,count_col='tarih','cagri_sayisi'
            st.caption(f'{len(raw):,} yarım saatlik kayıt otomatik yüklendi.')
            if st.button('Veritabanını Yenile',key='interval_refresh'):
                cached_calls.clear();_weekly_model.clear();st.rerun()
        else:
            upload=st.file_uploader('CSV / Excel dosyası',type=['csv','xlsx'],key='interval_upload')
            if upload:
                try:
                    raw=pd.read_csv(upload) if upload.name.lower().endswith('.csv') else pd.read_excel(upload)
                except Exception as exc:
                    st.error(f'Dosya okunamadı: {exc}');return
                a,b=st.columns(2);dt_guess=_guess_datetime_col(raw);call_guess=_guess_calls_col(raw)
                date_col=a.selectbox('Tarih / saat sütunu',list(raw),index=list(raw).index(dt_guess) if dt_guess in raw else 0,key='interval_date_column')
                count_col=b.selectbox('Çağrı sayısı sütunu',list(raw),index=list(raw).index(call_guess) if call_guess in raw else 0,key='interval_calls_column')
    if raw is None:
        st.info('Bir dosya seçin veya hazır veritabanını kullanın.');return
    use_iqr=st.toggle('Aykırı değerleri IQR ile değerlendir',value=False,key='interval_iqr')
    iqr_k=1.5;iqr_mode='cap'
    if use_iqr:
        a,b=st.columns(2)
        iqr_k=a.number_input('IQR katsayısı',min_value=.5,max_value=5.,value=1.5,step=.5,key='interval_iqr_k')
        iqr_mode=b.selectbox('Aykırı değer işlemi',['cap','drop'],format_func=lambda x:'Sınırla (günleri koru)' if x=='cap' else 'Aykırı günleri çıkar',key='interval_iqr_mode')
        st.caption('Aynı haftanın günü ve aynı yarım saat karşılaştırılır. Temizlik yalnızca eğitim geçmişine uygulanır; başarı ölçümündeki gerçek çağrılar değiştirilmez.')
    try:
        dates,_,_,quality=prepare_intervals(raw,date_col,count_col)
        next_monday=dates.max().date()+pd.Timedelta(days=7-dates.max().weekday())
        chosen=st.date_input('Hangi hafta için dağılım oluşturulsun?',value=next_monday,key='interval_target_week')
        week=pd.Timestamp(chosen)-pd.Timedelta(days=chosen.weekday())
        result=_weekly_model(raw,str(week.date()),date_col,count_col,state.get('interval_last_used_profile'),state.get('interval_used_profiles',{}),use_iqr,iqr_k,iqr_mode)
    except (ValueError,TypeError,KeyError) as exc:
        st.error(str(exc));return
    meta=dict(result['meta']);profile=result['profile']
    from ortak.interval_duzenleme_ekrani import edit_distribution
    profile,manual_meta=edit_distribution(profile);meta.update(manual_meta)
    if manual_meta['manual_adjusted']:st.caption('Elle dengelenmiş profil gösteriliyor. Aşağıdaki geçmiş başarı puanları otomatik modellerindir; elle değiştirilen seçimin başarısı kaydedildikten sonra gerçek çağrılarla ölçülür.')
    if use_iqr:st.caption(f"IQR: {meta['iqr_changed_slots']} aykırı yarım saat saptandı; {meta['iqr_removed_days']} tam gün çıkarıldı.")
    st.info(f'{week:%d.%m.%Y} – {week+pd.Timedelta(days=6):%d.%m.%Y} · Her günün çağrıları kendi sütununda %100’e tamamlanır.')
    st.markdown('### Önerilen Haftalık Dağılım')
    slot_heatmap(profile)
    with st.container(border=True):
        st.markdown('#### Haftanın Slot Ağırlıkları')
        st.caption('Örnek: Pazartesi 09:00–09:30 hücresinde %4 yazıyorsa, Pazartesi çağrı tahmininin %4’ü bu yarım saate ayrılır.')
        table=matrix_table(profile)
        st.dataframe(table.style.format('{:.2f}%').background_gradient(cmap='Blues',axis=None).set_properties(**{'text-align':'center'}),use_container_width=True,height=485)
        st.download_button('Haftalık Tabloyu CSV İndir',table.to_csv().encode('utf-8-sig'),'haftalik_slot_agirliklari.csv','text/csv')
    with st.expander('Bu dağılım neden önerildi?'):
        st.write('Son 2 hafta, 1 ay, 3 ay, 6 ay, 12 ay ve tüm geçmiş ayrı ayrı karşılaştırılır. Geçen tam haftayı daha iyi açıklayan geçmişlere daha fazla pay verilir; yeni günler eski günlerden daha etkilidir.')
        scores=result['scores'][['Pencere','Başarı ağırlığı (%)','MAE (yüzde puan)']].rename(columns={'Pencere':'Hesaplamada kullanılan geçmiş','Başarı ağırlığı (%)':'Son dağılıma katkısı (%)','MAE (yüzde puan)':'Geçen haftadaki ortalama sapma (yüzde puan)'})
        from html import escape
        for offset in range(0,len(scores),3):
            for col,r in zip(st.columns(3),scores.iloc[offset:offset+3].to_dict('records')):
                name=r['Hesaplamada kullanılan geçmiş'];weight=r['Son dağılıma katkısı (%)'];error=r['Geçen haftadaki ortalama sapma (yüzde puan)']
                col.markdown(f'<div style="border:1px solid #dce7ed;border-top:4px solid #338e9b;border-radius:16px;padding:17px;margin:6px 0;background:linear-gradient(130deg,#edf8f8,#fff)"><b>{escape(name)}</b><div style="font-size:25px;color:#258694;margin:12px 0">%{weight:.1f} katkı</div><small>Yarım saat payında ortalama fark: <b>{error:.3f} puan</b></small></div>',unsafe_allow_html=True)
        st.info('Pay hatası, çağrının hangi yarım saate dağıldığını ölçer. Örneğin gerçek pay %4, öneri %5 ise fark 1 puandır. Küçük fark daha iyi dağılım demektir; çağrı toplamının doğruluğunu ölçmez.')
        st.caption(f"Kontrol edilen hafta: {meta['validation_start']} – {meta['validation_end']}. Hatanın düşük olması daha iyi uyum demektir; gelecek hafta için garanti değildir.")
        flags=calendar_flags(pd.date_range(week,periods=7))
        labels={'EKSTRE_KESIM':'Ekstre kesim','SON_ODEME':'Son ödeme','Bayram':'Bayram','Arife':'Arife','Bayram_Sonrasi':'Bayram sonrası','Resmi_Tatil':'Resmi tatil','Ramazan':'Ramazan'}
        st.markdown('**Bu haftanın özel günleri**')
        special=[{'Gün':DAY_NAMES[d.weekday()],'Tarih':d.strftime('%d.%m.%Y'),'Etkiler':', '.join(labels[k] for k in flags if flags.loc[d,k]) or 'Standart gün'} for d in flags.index]
        for event in special:
            if event['Etkiler']!='Standart gün':st.markdown(f"<div style='background:#fff3da;border-left:5px solid #dca048;padding:13px;border-radius:12px;margin:7px 0'><b>{event['Tarih']} · {event['Gün']}</b> — {event['Etkiler']}</div>",unsafe_allow_html=True)
        st.caption(f"{meta['used_history_days']} geçmiş tam gün değerlendirildi. {quality['Eksik veya sıfır gün']} eksik/sıfır gün değerlendirmeye alınmadı.")
    from ortak.dagilim_adetleri import render as render_counts
    render_counts(profile,st.session_state,'interval_counts')
    st.markdown('### Planlamada Kullan')
    st.caption('Kaydettiğin dağılım aktif olur. Sonraki adım: Personel Hesap ekranında bu haftanın ihtiyacını hesapla.')
    with st.form('interval_save_form'):
        name=st.text_input('Profil adı',value=f'Hafta {week:%d.%m.%Y}',key=f'interval_profile_label_{week.date()}')
        save=st.form_submit_button('Dağılımı Kaydet ve Aktif Et',key='interval_save')
    if save:
        if not name.strip():
            st.error('Profil adı boş olamaz.');return
        snapshot={'name':name.strip(),'profile_df':profile.copy(),'created_at':pd.Timestamp.now().isoformat(),'meta':meta,'scores':result['scores']}
        state.update(sp_ratio_profiles=[p for p in state.get('sp_ratio_profiles',[]) if p.get('name')!=name.strip()]+[snapshot],
                     sp_active_ratio_profile_df=profile.copy(),sp_active_ratio_profile_name=name.strip(),sp_active_ratio_profile_meta=meta,
                     sp_staffing_result_df=None,plan_ctx_confirmed=False)
        from ortak.tahmin_kayit_servisi import capture_profile
        capture_profile(state,profile,{'name':name.strip(),**meta})
        save_keys(state)
        st.success('Dağılım aktif. Personel Hesap ekranından devam edebilirsin.')

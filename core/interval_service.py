"""Leakage-free weekly 7x48 intraday profiles with calibrated window weights."""
import numpy as np
import pandas as pd

from core.forecast_service import DAY_NAMES

WINDOWS={'Son 2 hafta':('days',14),'Son 1 ay':('months',1),'Son 3 ay':('months',3),
         'Son 6 ay':('months',6),'Son 12 ay':('months',12),'Tüm geçmiş':None}
FLAGS=['EKSTRE_KESIM','SON_ODEME','Bayram','Arife','Bayram_Sonrasi','Resmi_Tatil','Ramazan']


def calendar_flags(dates):
    # Use the exact same calendar definitions as call forecasting.
    from modules.call_forecast.predict_ui import _apply_date_bank_features
    frame=pd.DataFrame({'tarih':pd.to_datetime(dates)})
    return _apply_date_bank_features(frame,'tarih',FLAGS,frame).set_index('tarih')[FLAGS].astype(int)


def recency_weights(age_days):
    """Today gets 1; weight decreases monotonically with log(1 + age/7)."""
    return 1/(1+np.log1p(np.maximum(np.asarray(age_days,dtype=float),0)/7))


def prepare_intervals(raw,dt_col='tarih',calls_col='cagri_sayisi'):
    if raw is None or raw.empty or dt_col not in raw or calls_col not in raw:
        raise ValueError('Tarih/saat ve çağrı sayısı sütunları gerekli.')
    times=pd.to_datetime(raw[dt_col],errors='coerce')
    calls=pd.to_numeric(raw[calls_col],errors='coerce')
    if times.isna().any() or calls.isna().any() or not np.isfinite(calls).all() or (calls<0).any():
        raise ValueError('Geçersiz tarih veya negatif/boş çağrı kaydı var.')
    if times.dt.tz is not None:
        times=times.dt.tz_localize(None)
    if (times.dt.minute==0).all() and (times.dt.hour==0).all() and 'slot' in raw:
        slot=pd.to_numeric(raw.slot,errors='coerce')
        if slot.isna().any() or ((slot<1)|(slot>48)|(slot%1!=0)).any():
            raise ValueError('Slot 1–48 arasında tamsayı olmalı.')
        times=times+pd.to_timedelta((slot-1)*30,unit='m')
    if not ((times.dt.minute%30==0)&(times.dt.second==0)).all():
        raise ValueError('Kayıtlar tam veya yarım saat başlangıcında olmalı.')
    frame=pd.DataFrame({'Tarih':times.dt.normalize(),'Slot':times.dt.hour*2+times.dt.minute//30+1,'Çağrı':calls})
    # Multiple queues for the same slot are summed, missing slots remain missing.
    matrix=frame.groupby(['Tarih','Slot']).Çağrı.sum().unstack('Slot').reindex(columns=range(1,49))
    valid=matrix.notna().all(axis=1)&(matrix.sum(axis=1)>0)
    complete=matrix.loc[valid].astype(float)
    if complete.empty:
        raise ValueError('48 dilimi tam ve toplam çağrısı pozitif bir gün gerekli.')
    shares=complete.div(complete.sum(axis=1),axis=0).to_numpy()
    return complete.index,shares,complete,{'Tam gün':int(valid.sum()),'Eksik veya sıfır gün':int((~valid).sum())}


def _predict(dates,shares,flags,targets,target_flags,window):
    cutoff=dates.max()
    lower=(cutoff-pd.DateOffset(**{window[0]:window[1]})+pd.Timedelta(days=1)) if window else dates.min()
    mask=dates>=lower
    selected_dates=dates[mask]
    values=shares[mask]
    info=flags.loc[selected_dates]
    recency=recency_weights((cutoff-selected_dates).days)
    output=[]; notes=[]
    for target in targets:
        weekday=selected_dates.weekday==target.weekday()
        # Regular weekdays should not inherit holiday shapes by accident.
        special=target_flags.loc[target,['Bayram','Arife','Resmi_Tatil']].any()
        regular=~info[['Bayram','Arife','Resmi_Tatil']].any(axis=1).to_numpy()
        pool=weekday & (regular if not special and (weekday&regular).any() else True)
        if not pool.any():
            pool=np.ones(len(values),dtype=bool)
            notes.append(f'{target.date()}: aynı hafta günü bulunamadı; pencerenin genel dağılımı kullanıldı')
        base=np.average(values[pool],axis=0,weights=recency[pool])
        for flag in FLAGS:
            if not target_flags.loc[target,flag]:
                continue
            analog=info[flag].to_numpy()==1
            if (analog&weekday).sum()>=2:
                analog &= weekday
            support=int(analog.sum())
            if support>=2:
                effect=np.average(values[analog],axis=0,weights=recency[analog])
                strength=min(.7,support/(support+4))
                base=(1-strength)*base+strength*effect
                notes.append(f'{target.date()} · {flag}: {support} benzer gün')
            else:
                notes.append(f'{target.date()} · {flag}: yeterli benzer gün yok; temel dağılım korundu')
        base=np.clip(base,0,None)
        output.append(base/base.sum())
    return np.array(output),list(dict.fromkeys(notes)),int(mask.sum())


def profile_frame(values,dates):
    return pd.DataFrame([{'Tarih':d.date(),'Gün':DAY_NAMES[d.weekday()],'Slot':s+1,
                          'Aralık':f'{s//2:02d}:{(s%2)*30:02d} - {(s+1)//2:02d}:{((s+1)%2)*30:02d}',
                          'Oran(%)':float(values[i,s]*100)} for i,d in enumerate(dates) for s in range(48)])


def clean_iqr(dates,shares,k=1.5,mode='cap'):
    """Fit IQR within weekday/slot training groups; never alter holdout actuals."""
    if k<=0 or mode not in {'cap','drop'}:raise ValueError('Geçersiz IQR ayarı.')
    out=shares.copy();flagged=np.zeros(len(dates),dtype=bool);changed=0
    for dow in range(7):
        indices=np.flatnonzero(dates.weekday==dow)
        if len(indices)<4:continue
        values=out[indices];q1,q3=np.quantile(values,[.25,.75],axis=0);span=q3-q1
        lo=np.maximum(0,q1-k*span);hi=q3+k*span
        bad=(values<lo)|(values>hi);changed+=int(bad.sum());flagged[indices]=bad.any(axis=1)
        if mode=='cap':out[indices]=np.clip(values,lo,hi)
    keep=~flagged if mode=='drop' else np.ones(len(dates),dtype=bool)
    out=out[keep];totals=out.sum(axis=1)
    if (totals<=0).any() or keep.sum()<14:raise ValueError('IQR sonrası en az 14 kullanılabilir tam gün gerekli. Katsayıyı artırın veya sınırla yöntemini seçin.')
    out=out/totals[:,None]
    return dates[keep],out,{'iqr_used':True,'iqr_mode':mode,'iqr_k':float(k),'iqr_changed_slots':changed,'iqr_removed_days':int((~keep).sum())}


def build_weekly_distribution(raw,week_start,dt_col='tarih',calls_col='cagri_sayisi',previous_profile=None,previous_profiles=None, use_iqr=False, iqr_k=1.5, iqr_mode="cap"):
    start=pd.Timestamp(week_start).normalize()
    if start.weekday()!=0:
        raise ValueError('Hafta başlangıcı Pazartesi olmalı.')
    dates,shares,counts,quality=prepare_intervals(raw,dt_col,calls_col)
    past=dates<start
    dates,shares,counts=dates[past],shares[past],counts.loc[past]
    if len(dates)<21:
        raise ValueError('Kalibrasyon için hedef haftadan önce en az 21 tam gün gerekli.')
    # Find the most recent complete Mon–Sun holdout, strictly before target week.
    mondays=sorted({d-pd.Timedelta(days=d.weekday()) for d in dates},reverse=True)
    valid_start=next((m for m in mondays if m+pd.Timedelta(days=6)<start
                      and all(m+pd.Timedelta(days=i) in dates for i in range(7))),None)
    if valid_start is None:
        raise ValueError('Başarı ölçümü için 7 günü tam olan bir geçmiş hafta gerekli.')
    validation_dates=pd.date_range(valid_start,periods=7)
    if previous_profiles and str(valid_start.date()) in previous_profiles:
        previous_profile=previous_profiles[str(valid_start.date())]
    train=dates<valid_start
    if train.sum()<14:
        raise ValueError('Doğrulama haftasından önce en az 14 tam gün gerekli.')
    all_days=dates.union(pd.date_range(start,periods=7))
    flags=calendar_flags(all_days)
    actual=counts.loc[validation_dates].div(counts.loc[validation_dates].sum(axis=1),axis=0).to_numpy()
    lagged=counts.reindex(validation_dates-pd.Timedelta(days=7))
    lagged=lagged.div(lagged.sum(axis=1),axis=0).to_numpy()
    previous=lagged
    baseline_name='Önceki haftanın gerçekleşen dağılımı'
    if previous_profile is not None and not previous_profile.empty:
        prev=previous_profile.copy()
        if 'Tarih' not in prev or set(pd.to_datetime(prev.Tarih).dt.normalize())==set(validation_dates):
            try:
                candidate=prev.pivot(index='Gün',columns='Slot',values='Oran(%)').reindex(index=[DAY_NAMES[d.weekday()] for d in validation_dates],columns=range(1,49)).to_numpy()/100
                if np.isfinite(candidate).all() and (candidate>=0).all() and np.allclose(candidate.sum(axis=1),1,atol=.001):
                    previous=candidate
                    baseline_name=('Doğrulama haftasında kullanılmış kayıtlı dağılım' if 'Tarih' in prev
                                   else 'Kayıtlı önceki dağılım (hafta bilgisi yok)')
            except (ValueError,KeyError):
                pass
    baseline_error=float(np.mean(np.abs(previous-actual))*100) if np.isfinite(previous).all() else None
    train_dates,train_shares=dates[train],shares[train]
    future_dates,future_shares=dates,shares
    iqr_meta={'iqr_used':False}
    if use_iqr:
        train_dates,train_shares,_=clean_iqr(train_dates,train_shares,iqr_k,iqr_mode)
        future_dates,future_shares,iqr_meta=clean_iqr(dates,shares,iqr_k,iqr_mode)
    rows=[];validation_predictions=[];future_predictions=[];notes=[]
    target_dates=pd.date_range(start,periods=7)
    for name,window in WINDOWS.items():
        pred,_,n=_predict(train_dates,train_shares,flags,validation_dates,flags,window)
        error=float(np.mean(np.abs(pred-actual))*100)
        future,explanations,n_future=_predict(future_dates,future_shares,flags,target_dates,flags,window)
        rows.append({'Pencere':name,'MAE (yüzde puan)':error,
                     'Önceki dağılıma göre iyileşme (puan)':None if baseline_error is None else baseline_error-error,
                     'Doğrulama eğitim günleri':n,'Güncel eğitim günleri':n_future})
        validation_predictions.append(pred);future_predictions.append(future);notes.extend(explanations)
    errors=np.array([r['MAE (yüzde puan)'] for r in rows])
    weights=1/np.maximum(errors,.01)
    weights/=weights.sum()
    for row,weight in zip(rows,weights):
        row['Başarı ağırlığı (%)']=float(weight*100)
    combined=np.tensordot(weights,np.array(future_predictions),axes=(0,0))
    validation_mix=np.tensordot(weights,np.array(validation_predictions),axes=(0,0))
    return {'profile':profile_frame(combined,target_dates),'scores':pd.DataFrame(rows),
            'window_profiles':{name:profile_frame(p,target_dates) for name,p in zip(WINDOWS,future_predictions)},
            'actual_validation':profile_frame(actual,validation_dates),
            'predicted_validation':profile_frame(validation_mix,validation_dates),
            'validation_window_profiles':{name:profile_frame(p,validation_dates) for name,p in zip(WINDOWS,validation_predictions)},
            'meta':{'week_start':str(start.date()),'week_end':str((start+pd.Timedelta(days=6)).date()),
                    'history_cutoff':str(dates.max().date()),'used_history_days':len(dates),'validation_start':str(valid_start.date()),
                    'validation_end':str((valid_start+pd.Timedelta(days=6)).date()),
                    'baseline_name':baseline_name,'baseline_mae':baseline_error,
                    'recency_formula':'1 / (1 + log(1 + yaş_gün / 7))',
                    'weights_method':'Ters MAE, 0.01 yüzde puan alt sınırı, toplam %100',
                    'calendar_notes':list(dict.fromkeys(notes)),**quality,**iqr_meta}}


def record_used_profile(state,forecast,profile):
    """Record the profile actually consumed by staffing, rather than previewed."""
    used=dict(state.get('interval_used_profiles',{}))
    dates=pd.to_datetime(forecast.tarih).dt.normalize()
    for monday in sorted({d-pd.Timedelta(days=d.weekday()) for d in dates}):
        week=pd.date_range(monday,periods=7)
        if not set(week)<=set(dates):
            continue
        if 'Tarih' in profile:
            snapshot=profile[pd.to_datetime(profile.Tarih).dt.normalize().isin(week)].copy()
        else:
            snapshot=profile.copy()
            day_dates={DAY_NAMES[d.weekday()]:d.date() for d in week}
            snapshot['Tarih']=snapshot.Gün.map(day_dates)
        if len(snapshot)==336:
            used[str(monday.date())]=snapshot
            state['interval_last_used_profile']=snapshot.copy()
    state['interval_used_profiles']={k:used[k] for k in sorted(used)[-12:]}

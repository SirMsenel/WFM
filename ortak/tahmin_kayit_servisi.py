# Ortak / Tahmin Kayit Servisi — bu ekranın / servisin uygulama kodu.
"""Immutable 30-minute forecast versions and upserted observed calls in SQLite."""
import hashlib,json
from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import uuid4
import numpy as np
import pandas as pd
from ortak.calisma_alani_deposu import connect,DEFAULT_DB,init_db
from ortak.cagri_tahmin_servisi import DAY_NAMES


def init_ledger(path):
    init_db(path)
    with connect(path) as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS forecast_runs(id TEXT PRIMARY KEY, fingerprint TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, start TEXT NOT NULL,end TEXT NOT NULL,metadata TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS forecast_slots(run_id TEXT NOT NULL REFERENCES forecast_runs(id),tarih TEXT NOT NULL,slot INTEGER NOT NULL CHECK(slot BETWEEN 1 AND 48),predicted REAL NOT NULL CHECK(predicted>=0),share REAL NOT NULL CHECK(share>=0),PRIMARY KEY(run_id,tarih,slot));''')


def capture_forecast(state,forecast,profile):
    rows=[]
    for day,total in zip(pd.to_datetime(forecast.tarih),forecast.y_pred):
        selected=profile[profile.Gün==DAY_NAMES[day.weekday()]].copy()
        if 'Tarih' in selected:selected=selected[pd.to_datetime(selected.Tarih).dt.normalize()==day.normalize()]
        if len(selected)!=48 or set(pd.to_numeric(selected.Slot,errors='coerce'))!=set(range(1,49)):raise ValueError('Kayıt için her günün 48 yarım saati gerekli.')
        if not np.isfinite(float(total)) or total<0:raise ValueError('Tahmin negatif/boş olamaz.')
        weights=pd.to_numeric(selected['Oran(%)'],errors='raise')
        if not np.isfinite(weights).all() or (weights<0).any() or abs(weights.sum()-100)>.01:raise ValueError('Dağılım toplamı %100 olmalı.')
        for (_,r),w in zip(selected.iterrows(),weights):rows.append((str(day.date()),int(r.Slot),float(total)*float(w)/100,float(w)))
    if not rows:raise ValueError('Kayıt için tahmin günü gerekli.')
    rows.sort();meta={'forecast':state.get('sp_forecast_meta',{}),'profile':state.get('sp_active_ratio_profile_name'),
                     'profile_meta':state.get('sp_active_ratio_profile_meta',{}),'recorded_by':(state.get('profile') or {}).get('username','system')}
    metadata=json.dumps(meta,ensure_ascii=False,default=str,sort_keys=True)
    digest=hashlib.sha256(json.dumps([rows,metadata],ensure_ascii=False).encode()).hexdigest()
    path=state.get('workspace_db_path') or DEFAULT_DB;init_ledger(path)
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        previous=db.execute('SELECT id FROM forecast_runs WHERE fingerprint=?',(digest,)).fetchone()
        if previous:run=previous[0]
        else:
            run='FC-'+uuid4().hex[:16]
            db.execute('INSERT INTO forecast_runs VALUES(?,?,?,?,?,?)',(run,digest,datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(),rows[0][0],rows[-1][0],metadata))
            db.executemany('INSERT INTO forecast_slots VALUES(?,?,?,?,?)',[(run,*r) for r in rows])
    state['last_forecast_run_id']=run
    return run


def runs(path=DEFAULT_DB):
    init_ledger(path)
    with connect(path) as db:return [dict(r) for r in db.execute('SELECT * FROM forecast_runs ORDER BY created_at DESC,id DESC')]


def slots(run_id,path=DEFAULT_DB):
    init_ledger(path)
    with connect(path) as db:return pd.read_sql_query('SELECT tarih,slot,predicted,share FROM forecast_slots WHERE run_id=? ORDER BY tarih,slot',db,params=(run_id,))


def ingest_actuals(raw,path=DEFAULT_DB):
    if 'tarih' not in raw or 'cagri_sayisi' not in raw:raise ValueError('tarih ve cagri_sayisi sütunları gerekli. İsteğe bağlı slot (1–48) ve aht_sec eklenebilir.')
    dates=pd.to_datetime(raw.tarih,errors='coerce')
    if dates.dt.tz is not None:dates=dates.dt.tz_convert('Europe/Istanbul').dt.tz_localize(None)
    calls=pd.to_numeric(raw.cagri_sayisi,errors='coerce')
    slot=pd.to_numeric(raw['slot'],errors='coerce') if 'slot' in raw else dates.dt.hour*2+dates.dt.minute//30+1
    if dates.isna().any() or calls.isna().any() or not np.isfinite(calls).all() or (calls<0).any() or (calls%1!=0).any():raise ValueError('Geçerli tarih ve negatif olmayan tam sayı çağrı gerekli.')
    if slot.isna().any() or ((slot<1)|(slot>48)|(slot%1!=0)).any():raise ValueError('Slot 1–48 olmalı.')
    if 'slot' not in raw and ((dates.dt.minute%30!=0)|(dates.dt.second!=0)).any():raise ValueError('Saatler 30 dakikalık başlangıç olmalı.')
    aht=pd.to_numeric(raw.get('aht_sec',pd.Series(300.,index=raw.index)),errors='coerce')
    if aht.isna().any() or not np.isfinite(aht).all() or (aht<=0).any():raise ValueError('AHT pozitif olmalı.')
    frame=pd.DataFrame({'tarih':dates.dt.strftime('%Y-%m-%d'),'slot':slot.astype(int),'calls':calls.astype(int),'aht':aht})
    if frame.duplicated(['tarih','slot']).any():raise ValueError('Dosyada aynı tarih/yarım saat birden fazla kez var; önce çağrıları birleştirin.')
    metrics=[]
    if any(c in raw for c in ('answered','answered_target','staffed')):
        from ortak.sabit_demo import init_history
        init_history(path)
        for i,r in raw.reset_index(drop=True).iterrows():
            answer=r.get('answered');within=r.get('answered_target');staff=r.get('staffed')
            if pd.notna(answer) and (float(answer)<0 or float(answer)>calls.iloc[i] or float(answer)%1):raise ValueError('Yanıtlanan çağrı toplam çağrıyı aşamaz.')
            if pd.notna(within) and (pd.isna(answer) or float(within)<0 or float(within)>float(answer) or float(within)%1):raise ValueError('Hedef süredeki yanıt sayısı geçersiz.')
            if pd.notna(staff) and (not np.isfinite(float(staff)) or float(staff)<0):raise ValueError('Aktif personel geçersiz.')
            metrics.append((frame.iloc[i].tarih,int(frame.iloc[i].slot),int(answer) if pd.notna(answer) else None,int(within) if pd.notna(within) else None,float(staff) if pd.notna(staff) else None))
    init_ledger(path)
    with connect(path) as db:
        if metrics:db.executemany('INSERT INTO interval_operations VALUES(?,?,?,?,?) ON CONFLICT(tarih,slot) DO UPDATE SET answered=excluded.answered,answered_target=excluded.answered_target,staffed=excluded.staffed',metrics)
        db.executemany('INSERT INTO calls_interval VALUES(?,?,?,?) ON CONFLICT(tarih,slot) DO UPDATE SET cagri_sayisi=excluded.cagri_sayisi,aht_sec=excluded.aht_sec',frame.itertuples(index=False,name=None))
        for day in frame.tarih.unique():
            totals=db.execute('SELECT SUM(cagri_sayisi),SUM(cagri_sayisi*aht_sec)/NULLIF(SUM(cagri_sayisi),0) FROM calls_interval WHERE tarih=?',(day,)).fetchone()
            db.execute('INSERT INTO calls_daily VALUES(?,?,?) ON CONFLICT(tarih) DO UPDATE SET cagri_sayisi=excluded.cagri_sayisi,aht_sec=excluded.aht_sec',(day,int(totals[0]),float(totals[1] or 300)))
    return len(frame)


def compare(run_id,path=DEFAULT_DB,exclude_early=True):
    planned=slots(run_id,path)
    if planned.empty:return planned
    with connect(path) as db:actual=pd.read_sql_query('SELECT tarih,slot,cagri_sayisi AS actual FROM calls_interval WHERE tarih BETWEEN ? AND ?',db,params=(planned.tarih.min(),planned.tarih.max()))
    result=planned.merge(actual,on=['tarih','slot'],how='left',validate='one_to_one')
    result['counted']=~result.slot.between(7,16) if exclude_early else True
    result['difference']=result.actual-result.predicted
    result['difference_pct']=100*result.difference/result.predicted.replace(0,np.nan)
    return result


def performance(frame):
    used=frame[frame.actual.notna()&frame.counted]
    actual=float(used.actual.sum());predicted=float(used.predicted.sum())
    return {'observed_slots':len(used),'predicted':predicted,'actual':actual,'bias_pct':100*(actual-predicted)/predicted if predicted else None,
            'wape_pct':100*float(used.difference.abs().sum())/actual if actual else None}


def capture_profile(state,profile,meta=None):
    from ortak.calisma_alani_deposu import dumps
    path=state.get('workspace_db_path') or DEFAULT_DB;init_profiles(path)
    frame=profile.sort_values(['Gün','Slot']).reset_index(drop=True)
    payload=dumps(frame);metadata=json.dumps(meta or {},ensure_ascii=False,default=str,sort_keys=True)
    digest=hashlib.sha256((payload+metadata).encode()).hexdigest()
    with connect(path) as db:
        old=db.execute('SELECT id FROM profile_versions WHERE fingerprint=?',(digest,)).fetchone()
        if old:return old[0]
        ident='IP-'+uuid4().hex[:16]
        db.execute('INSERT INTO profile_versions VALUES(?,?,?,?,?)',(ident,digest,datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(),payload,metadata))
        return ident


def init_profiles(path):
    init_ledger(path)
    with connect(path) as db:db.execute('CREATE TABLE IF NOT EXISTS profile_versions(id TEXT PRIMARY KEY,fingerprint TEXT UNIQUE NOT NULL,created_at TEXT NOT NULL,profile TEXT NOT NULL,metadata TEXT NOT NULL)')


def profile_versions(path=DEFAULT_DB):
    from ortak.calisma_alani_deposu import loads
    init_profiles(path)
    with connect(path) as db:
        return [{**dict(r),'frame':loads(r['profile']),'meta':json.loads(r['metadata'])} for r in db.execute('SELECT * FROM profile_versions ORDER BY created_at DESC,id DESC')]


def profile_accuracy(version,path=DEFAULT_DB,exclude_early=True):
    frame=version['frame'].copy()
    if 'Tarih' not in frame:raise ValueError('Başarı ölçümü için profilde tarih bilgisi gerekli.')
    planned=frame.rename(columns={'Tarih':'tarih','Slot':'slot','Oran(%)':'share'})[['tarih','slot','share']]
    planned.tarih=pd.to_datetime(planned.tarih).dt.strftime('%Y-%m-%d')
    with connect(path) as db:actual=pd.read_sql_query('SELECT tarih,slot,cagri_sayisi AS actual FROM calls_interval WHERE tarih BETWEEN ? AND ?',db,params=(planned.tarih.min(),planned.tarih.max()))
    out=planned.merge(actual,on=['tarih','slot'],how='left',validate='one_to_one')
    out['counted']=~out.slot.between(7,16) if exclude_early else True
    out['actual_share']=np.nan;out['planned_share']=np.nan
    for _,indices in out.groupby('tarih').groups.items():
        effective=out.loc[indices];effective=effective[effective.counted]
        if effective.empty or effective.actual.isna().any() or effective.actual.sum()<=0 or effective.share.sum()<=0:continue
        out.loc[effective.index,'actual_share']=100*effective.actual/effective.actual.sum()
        out.loc[effective.index,'planned_share']=100*effective.share/effective.share.sum()
    out['error_points']=out.actual_share-out.planned_share
    return out


def migrate_legacy(state):
    """Preserve old snapshots without inventing an original capture timestamp."""
    from ortak.calisma_alani_deposu import loads
    path=state.get('workspace_db_path')
    if not path:return
    init_profiles(path)
    with connect(path) as db:
        if db.execute("SELECT 1 FROM metadata WHERE key='forecast_ledger_legacy_v1'").fetchone():return
    for week,profile in state.get('interval_used_profiles',{}).items():
        if profile is not None and not profile.empty and 'Tarih' in profile:capture_profile(state,profile,{'name':'Eski kullanılan dağılım '+week,'legacy_timestamp_unknown':True})
    old=state.get('sp_staffing_result_df')
    if old is not None and not old.empty and {'Tarih','Slot','Tahmin Çağrı'}<=set(old):
        frame=old[['Tarih','Slot','Tahmin Çağrı']].copy();frame['Tarih']=pd.to_datetime(frame.Tarih)
        totals=frame.groupby('Tarih')['Tahmin Çağrı'].sum()
        if (totals>0).all() and all(len(part)==48 and part.Slot.nunique()==48 for _,part in frame.groupby('Tarih')):
            frame['Oran(%)']=100*frame['Tahmin Çağrı']/frame.Tarih.map(totals);frame['Gün']=frame.Tarih.dt.weekday.map(dict(enumerate(DAY_NAMES)))
            forecast=totals.rename('y_pred').rename_axis('tarih').reset_index()
            capture_forecast({**dict(state),'sp_forecast_meta':{**state.get('sp_forecast_meta',{}),'legacy_timestamp_unknown':True}},forecast,frame)
            capture_profile(state,frame,{'name':'Eski personel hesabında kullanılan dağılım','legacy_timestamp_unknown':True})
    with connect(path) as db:db.execute("INSERT OR IGNORE INTO metadata VALUES('forecast_ledger_legacy_v1','done')")

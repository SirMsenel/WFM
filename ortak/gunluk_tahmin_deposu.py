"""Günlük Tahmin Deposu — interval hesabından bağımsız, yeniden kullanılabilir sürümler."""
import hashlib,json
from uuid import uuid4
from ortak.calisma_alani_deposu import connect,init_db,dumps,loads,DEFAULT_DB


def init_daily(path):
    init_db(path)
    with connect(path) as db:db.execute('CREATE TABLE IF NOT EXISTS daily_forecasts(id TEXT PRIMARY KEY,fingerprint TEXT UNIQUE NOT NULL,created_at TEXT NOT NULL,start TEXT NOT NULL,end TEXT NOT NULL,payload TEXT NOT NULL)')


def capture_daily(state,frame,meta=None):
    from ortak.cagri_tahmin_servisi import validate_forecast
    from ortak.talep_servisi import now
    frame=validate_forecast(frame);meta=dict(meta or {})
    digest=hashlib.sha256(dumps({'frame':frame,'meta':meta}).encode()).hexdigest()
    path=state.get('workspace_db_path') or DEFAULT_DB;init_daily(path)
    payload={'frame':frame,'meta':meta,'actor':(state.get('profile') or {}).get('username','system')}
    with connect(path) as db:
        row=db.execute('SELECT id FROM daily_forecasts WHERE fingerprint=?',(digest,)).fetchone()
        if row:return row[0]
        ident='DAY-'+uuid4().hex[:16]
        db.execute('INSERT INTO daily_forecasts VALUES(?,?,?,?,?,?)',(ident,digest,now(),str(frame.tarih.min().date()),str(frame.tarih.max().date()),dumps(payload)))
    return ident


def saved_daily(path=DEFAULT_DB):
    init_daily(path)
    with connect(path) as db:return [{**dict(r),**loads(r['payload'])} for r in db.execute('SELECT * FROM daily_forecasts ORDER BY created_at DESC,id DESC')]


def daily_label(record,path):
    from ortak.kayit_basliklari import title_for
    import pandas as pd
    text=f"{record['meta'].get('model_name','Günlük tahmin')} · {pd.Timestamp(record['start']):%d.%m.%Y} – {pd.Timestamp(record['end']):%d.%m.%Y} · {len(record['frame'])} gün"
    return title_for(path,record['id'],text)

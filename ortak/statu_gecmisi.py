"""Gerçekleşen statü kayıtları, sentetik örnek ve geçmişten shrinkage önerisi."""
import hashlib
import numpy as np
import pandas as pd
from ortak.calisma_alani_deposu import connect,loads
from modules.vardiya_plani.vardiya_motoru import bounds

KINDS={'Yemek','Mola','Koçluk','Cuma'}

def init(path):
    with connect(path) as db:db.executescript('CREATE TABLE IF NOT EXISTS status_actuals(id TEXT PRIMARY KEY,employee_id TEXT NOT NULL,start TEXT NOT NULL,end TEXT NOT NULL,kind TEXT NOT NULL,source TEXT NOT NULL);CREATE INDEX IF NOT EXISTS status_actuals_date ON status_actuals(start);')


def seed_demo(state):
    from ortak.calisma_modu import demo_enabled
    if not demo_enabled():return
    path=state['workspace_db_path'];init(path)
    with connect(path) as db:
        if not db.execute("SELECT 1 FROM metadata WHERE key='synthetic' AND value='true'").fetchone() or db.execute("SELECT 1 FROM metadata WHERE key='faz4_status_history'").fetchone():return
        rows=db.execute('SELECT payload FROM roster_history').fetchall()
    output=[]
    for entry in rows:
        row=loads(entry[0]);span=bounds(row)
        if not span:continue
        a,b=map(pd.Timestamp,span);hours=(b-a).total_seconds()/3600
        weekend=a.weekday()>=5
        intervals=[('Mola',a+pd.Timedelta(hours=1.5),10 if weekend else 15)]
        if hours>=4:intervals += [('Yemek',a+pd.Timedelta(hours=hours/2),20 if weekend else 30)]
        if hours>=4 and not weekend:intervals += [('Mola',b-pd.Timedelta(hours=1.5),15)]
        if a.day in {3,10,17,24} and hours>=5:intervals += [('Koçluk',a+pd.Timedelta(hours=2.25),15)]
        for n,(kind,start,minutes) in enumerate(intervals):
            end=start+pd.Timedelta(minutes=minutes)
            if start<a or end>b:continue
            ident='DEMO-'+hashlib.sha256(f"{row['employee_id']}|{row['date']}|{n}".encode()).hexdigest()[:24];output.append((ident,str(row['employee_id']),str(start),str(end),kind,'synthetic'))
    with connect(path) as db:
        db.execute("DELETE FROM status_actuals WHERE source='synthetic'")
        db.executemany('INSERT OR IGNORE INTO status_actuals VALUES(?,?,?,?,?,?)',output); db.execute("INSERT OR REPLACE INTO metadata VALUES('faz4_status_history','1')")


def actuals(state,start,end,ids=None):
    path=state['workspace_db_path'];init(path)
    with connect(path) as db:df=pd.read_sql_query('SELECT * FROM status_actuals WHERE start<? AND end>?',db,params=[str(pd.Timestamp(end)+pd.Timedelta(days=1)),str(pd.Timestamp(start))])
    return df if ids is None else df[df.employee_id.astype(str).isin(set(map(str,ids)))]


def ingest(state,records):
    if state.get('profile',{}).get('position') not in {'wfm','planning_manager'}:raise ValueError('Statü gerçekleşmelerini Planlama kaydeder.')
    prepared=[]
    for r in records:
        a,b=pd.Timestamp(r['start']),pd.Timestamp(r['end'])
        if pd.isna(a) or pd.isna(b) or a>=b or r['kind'] not in KINDS:raise ValueError('Geçerli statü ve başlangıç/bitiş gerekli.')
        prepared.append((r.get('id') or hashlib.sha256(str(r).encode()).hexdigest(),str(r['employee_id']),str(a),str(b),r['kind'],'actual'))
    init(state['workspace_db_path'])
    with connect(state['workspace_db_path']) as db:db.executemany('INSERT INTO status_actuals VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET employee_id=excluded.employee_id,start=excluded.start,end=excluded.end,kind=excluded.kind,source=excluded.source',prepared)
    return len(prepared)


def suggested_shrinkage(state,start,end,by_weekday=False):
    from ortak.sabit_demo import history_rows
    roster=history_rows(state,pd.Timestamp(start)-pd.Timedelta(days=1),end);actual=actuals(state,start,end);days=pd.date_range(start,end);numerator=np.zeros(336 if by_weekday else 48);denominator=np.zeros_like(numerator)
    # Union intervals per employee: overlapping status records must not double count.
    intervals={}
    for p in actual.to_dict('records'):intervals.setdefault(str(p['employee_id']),[]).append((pd.Timestamp(p['start']),pd.Timestamp(p['end'])))
    merged={}
    for eid,values in intervals.items():
        combined=[]
        for a,b in sorted(values):
            if combined and a<=combined[-1][1]:combined[-1]=(combined[-1][0],max(b,combined[-1][1]))
            else:combined.append((a,b))
        merged[eid]=combined
    from bisect import bisect_right,bisect_left
    unit=30*60*1_000_000_000;day_ns=48*unit;low=pd.Timestamp(start).value;high=(pd.Timestamp(end)+pd.Timedelta(days=1)).value
    indexed={eid:([(a.value,b.value) for a,b in spans],[b.value for a,b in spans],[a.value for a,b in spans]) for eid,spans in merged.items()}
    def accumulate(target,a,b):
        a=max(a,low);b=min(b,high)
        if a>=b:return
        ticks=np.arange(a//unit,(b-1)//unit+1,dtype=np.int64)*unit
        seconds=(np.minimum(b,ticks+unit)-np.maximum(a,ticks))/1e9
        slots=(ticks//unit)%48
        if by_weekday:slots=slots+((ticks//day_ns+3)%7)*48
        np.add.at(target,slots,seconds)
    for row in roster:
        span=bounds(row)
        if not span:continue
        a,b=(pd.Timestamp(v).value for v in span)
        accumulate(denominator,a,b)
        spans,ends,starts=indexed.get(str(row['employee_id']),([],[],[]))
        for x,y in spans[bisect_right(ends,a):bisect_left(starts,b)]:accumulate(numerator,max(a,x),min(b,y))
    rates=np.divide(numerator,denominator,out=np.full(len(numerator),np.nan),where=denominator>0)
    from ortak.saat_etiketleri import slot_label
    from ortak.cagri_tahmin_servisi import DAY_NAMES
    n=len(numerator)
    frame=pd.DataFrame({'Slot':[i%48+1 for i in range(n)],'Saat aralığı':[slot_label(i%48+1) for i in range(n)],'Shrinkage (%)':np.round(100*rates,2),'Çalışma kişi-saat':np.round(denominator/3600,2),'Statü kişi-saat':np.round(numerator/3600,2)})
    if by_weekday:
        frame.insert(0,'Gün',[DAY_NAMES[i//48] for i in range(n)]);frame['Haftanın günü']=[i//48 for i in range(n)]
    return frame,100*numerator.sum()/denominator.sum() if denominator.sum() else None,not actual.empty and bool((actual.source=='synthetic').any())

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
        if not db.execute("SELECT 1 FROM metadata WHERE key='synthetic' AND value='true'").fetchone() or db.execute("SELECT 1 FROM metadata WHERE key='faz3_status_history'").fetchone():return
        rows=db.execute('SELECT payload FROM roster_history').fetchall()
    output=[]
    for entry in rows:
        row=loads(entry[0]);span=bounds(row)
        if not span:continue
        a,b=map(pd.Timestamp,span);hours=(b-a).total_seconds()/3600
        intervals=[('Mola',a+pd.Timedelta(hours=1.5),15)]
        if hours>=4:intervals += [('Yemek',a+pd.Timedelta(hours=hours/2),30),('Mola',b-pd.Timedelta(hours=1.5),15)]
        if a.day in {3,10,17,24} and hours>=5:intervals += [('Koçluk',a+pd.Timedelta(hours=2.25),15)]
        for n,(kind,start,minutes) in enumerate(intervals):
            end=start+pd.Timedelta(minutes=minutes)
            if start<a or end>b:continue
            ident='DEMO-'+hashlib.sha256(f"{row['employee_id']}|{row['date']}|{n}".encode()).hexdigest()[:24];output.append((ident,str(row['employee_id']),str(start),str(end),kind,'synthetic'))
    with connect(path) as db:db.executemany('INSERT OR IGNORE INTO status_actuals VALUES(?,?,?,?,?,?)',output);db.execute("INSERT OR REPLACE INTO metadata VALUES('faz3_status_history','1')")


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


def suggested_shrinkage(state,start,end):
    from ortak.sabit_demo import history_rows
    roster=history_rows(state,pd.Timestamp(start)-pd.Timedelta(days=1),end);actual=actuals(state,start,end);days=pd.date_range(start,end);numerator=np.zeros(48);denominator=np.zeros(48)
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
    for row in roster:
        span=bounds(row)
        if not span:continue
        a,b=map(pd.Timestamp,span);usable=[(x,y) for x,y in merged.get(str(row['employee_id']),[]) if x<b and a<y]
        for t in pd.date_range(a.floor('30min'),b-pd.Timedelta(seconds=1),freq='30min'):
            if not pd.Timestamp(start)<=t<pd.Timestamp(end)+pd.Timedelta(days=1):continue
            left,right=max(a,t),min(b,t+pd.Timedelta(minutes=30));slot=t.hour*2+t.minute//30;denominator[slot]+=(right-left).total_seconds()
            numerator[slot]+=sum(max(0,(min(right,y)-max(left,x)).total_seconds()) for x,y in usable)
    rates=np.divide(numerator,denominator,out=np.full(48,np.nan),where=denominator>0)
    from ortak.saat_etiketleri import slot_label
    frame=pd.DataFrame({'Slot':range(1,49),'Saat aralığı':[slot_label(i) for i in range(1,49)],'Shrinkage (%)':np.round(100*rates,2),'Çalışma kişi-saat':denominator/3600,'Statü kişi-saat':numerator/3600})
    return frame,100*numerator.sum()/denominator.sum() if denominator.sum() else None,not actual.empty and bool((actual.source=='synthetic').any())

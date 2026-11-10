"""Sabit örnek dönem: 01.01.2026–09.11.2026. Kullanıcı planlarını ezmez."""
from datetime import date,timedelta
from pathlib import Path
import sqlite3,random,math
from ortak.calisma_alani_deposu import connect,dumps,loads
from ortak.personel_deposu import auth_path,ensure_identity
END=date(2026,11,9)


def directory(state=None):
    from ortak.calisma_modu import demo_enabled
    if not demo_enabled():return
    path=auth_path(state);ensure_identity(path)
    with sqlite3.connect(path) as db:
        if not db.execute("SELECT 1 FROM users WHERE username='moderator'").fetchone():return
        db.execute('CREATE TABLE IF NOT EXISTS demo_migrations(version TEXT PRIMARY KEY)')
        if db.execute("SELECT 1 FROM demo_migrations WHERE version='phase7'").fetchone():return
        from passlib.context import CryptContext
        hashed=CryptContext(schemes=['pbkdf2_sha256']).hash('1234');rng=random.Random(20261109)
        companies=['Ulak','Teleperformance','Assistt','Müşteri Çözümleri AŞ']
        staff=db.execute('SELECT employee_id,company,employment_start FROM employees').fetchall()
        for eid,company,start in staff:
            db.execute('UPDATE employees SET company=?,employment_start=?,gender=COALESCE(gender,?) WHERE employee_id=?',(company or rng.choice(companies),start or str(date(2026,1,1)+timedelta(days=0 if eid<35 else rng.randrange(260))),rng.choice(['Kadın','Erkek']),eid))
        lead=db.execute("SELECT full_name,manager FROM employees WHERE position='tl' LIMIT 1").fetchone()
        for i in range(60):
            username=f'dis_kaynak_ornek_{i+1:02d}'
            if db.execute('SELECT 1 FROM users WHERE username=?',(username,)).fetchone():continue
            start=date(2026,1,1)+timedelta(days=rng.randrange(230));end=start+timedelta(days=rng.randrange(35,75)) if i<14 else None
            eid=db.execute('INSERT INTO employees(full_name,team_lead,manager,location,work_type,position,language,sicil_no,company,employment_start,employment_end,gender) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(f'Dış Kaynak Örnek {i+1:02d}',lead[0] if lead else '',lead[1] if lead else '',rng.choice(['Ankara','İstanbul','Rize','Adana','Diyarbakır']),'dis_kaynak','agent',rng.choice(['tr','tr','tr','en','ar']),f'DEMO7-{i+1:04d}',rng.choice(companies),str(start),str(end) if end else None,rng.choice(['Kadın','Erkek']))).lastrowid
            db.execute('INSERT INTO users(username,password_hash,employee_id,is_active) VALUES(?,?,?,?)',(username,hashed,eid,0 if end else 1))
        for username,name,role in [('planlama2','İkinci Planlamacı','wfm'),('planlama3','Üçüncü Planlamacı','wfm'),('planlama_yoneticisi','Planlama Yöneticisi','planning_manager')]:
            if db.execute('SELECT 1 FROM users WHERE username=?',(username,)).fetchone():continue
            eid=db.execute('INSERT INTO employees(full_name,position,work_type,language,location,sicil_no,company,employment_start) VALUES(?,?,?,?,?,?,?,?)',(name,role,'yonetim','tr','Ankara','DEMO7-'+username,'Ulak','2026-01-01')).lastrowid
            db.execute('INSERT INTO users(username,password_hash,employee_id,is_active) VALUES(?,?,?,1)',(username,hashed,eid))
        db.execute("INSERT INTO demo_migrations VALUES('phase7')")


def init_history(path):
    with connect(path) as db:
        db.executescript('CREATE TABLE IF NOT EXISTS roster_history(employee_id TEXT NOT NULL,date TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(employee_id,date));CREATE INDEX IF NOT EXISTS roster_history_date ON roster_history(date);CREATE TABLE IF NOT EXISTS interval_operations(tarih TEXT NOT NULL,slot INTEGER NOT NULL,answered INTEGER,answered_target INTEGER,staffed REAL,PRIMARY KEY(tarih,slot));')


def history_rows(state,start=None,end=None):
    current=state.get('published_shift_plan',[]);path=state.get('workspace_db_path');output={}
    if path:
        query='SELECT payload FROM roster_history WHERE 1=1';args=[]
        if start is not None:query+=' AND date>=?';args.append(str(start)[:10])
        if end is not None:query+=' AND date<=?';args.append(str(end)[:10])
        with connect(path) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='roster_history'").fetchone():
                output={(r['employee_id'],r['date']):r for row in db.execute(query,args) if (r:=loads(row[0]))}
    for r in current:
        if (start is None or str(r['date'])>=str(start)[:10]) and (end is None or str(r['date'])<=str(end)[:10]):output[(str(r['employee_id']),str(r['date']))]=r
    return list(output.values())


def prepare(state,path):
    init_history(path)
    with connect(path) as db:
        if not db.execute("SELECT 1 FROM metadata WHERE key='synthetic' AND value='true'").fetchone() or db.execute("SELECT 1 FROM metadata WHERE key='phase7_history'").fetchone():return
    from ortak.personel_deposu import list_people
    people=[p for p in list_people(state,True) if p['position']=='agent'];rng=random.Random(20260101)
    from scripts.ornek_kasim_haftasi import add_week
    add_week(path)
    with connect(path) as db:
        # Only this explicitly synthetic fixture is frozen; user publications stay separate.
        db.execute("DELETE FROM calls_interval WHERE tarih>'2026-11-09'");db.execute("DELETE FROM calls_daily WHERE tarih>'2026-11-09'")
        for day,total in db.execute("SELECT tarih,cagri_sayisi FROM calls_daily WHERE tarih>='2026-01-01'").fetchall():
            for slot,calls in db.execute('SELECT slot,cagri_sayisi FROM calls_interval WHERE tarih=?',(day,)).fetchall():
                answered=round(calls*(.93+rng.random()*.06));within=round(answered*(.70+rng.random()*.26));db.execute('INSERT OR IGNORE INTO interval_operations VALUES(?,?,?,?,?)',(day,slot,answered,within,max(1,round(calls*300/1800*1.2))))
        rows=[]
        for person in people:
            eid=str(person['employee_id']);group=person['work_type'];off=int(person['employee_id'])%7;hire=date.fromisoformat(str(person.get('employment_start') or '2026-01-01')[:10]);exit=date.fromisoformat(person['employment_end']) if person.get('employment_end') else END+timedelta(days=1)
            d=max(date(2026,1,1),hire)
            while d<=END and d<exit:
                free=d.weekday()==off or (group=='fulltime' and d.weekday()==(off+1)%7);code='OFF' if free else 'WORK'
                if not free and d.day==20 and int(eid)%11==0:code='YILLIK_IZIN'
                if not free and d.day==12 and int(eid)%17==0:code='RAPOR'
                a,b=('08:00','18:00') if group=='dis_kaynak' else ('10:00','17:00') if group=='akademi' else ('08:00','17:00')
                record={'employee_id':eid,'date':str(d),'shift_code':code,'start':a if code=='WORK' else None,'end':b if code=='WORK' else None,'language':person.get('language','tr'),'source':'demo_phase7'}
                rows.append((eid,str(d),dumps(record)));d+=timedelta(days=1)
        db.executemany('INSERT OR IGNORE INTO roster_history VALUES(?,?,?)',rows)
        db.execute("INSERT INTO metadata VALUES('directory_revision','phase7') ON CONFLICT(key) DO UPDATE SET value=excluded.value")
        db.execute("INSERT INTO metadata VALUES('phase7_history','2026-01-01/2026-11-09')")
        db.execute("INSERT INTO metadata VALUES('history_end','2026-11-09') ON CONFLICT(key) DO UPDATE SET value=excluded.value")

"""Mola talepleri: kişi kendi vardiyası içinde, kapasiteyi aşmadan tek işlemde yer ayırır."""
from uuid import uuid4
import pandas as pd
from ortak.calisma_alani_deposu import connect,loads,dumps,init_db
from ortak.sabit_demo import history_rows
from modules.vardiya_plani.vardiya_motoru import bounds


def init(path):
    init_db(path)
    from ortak.sabit_demo import init_history
    init_history(path)
    with connect(path) as db:db.execute('CREATE TABLE IF NOT EXISTS break_requests(id TEXT PRIMARY KEY,employee_id TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL)');db.execute('CREATE TABLE IF NOT EXISTS planned_breaks(id TEXT PRIMARY KEY,publication_id TEXT,payload TEXT)')


def records(state,db=None):
    path=state.get('workspace_db_path')
    if not path:return []
    init(path) if db is None else None
    def read(c):
        planned=[dict(loads(r[0]),id=r[1],status=loads(r[0]).get('status','Planlı')) for r in c.execute('SELECT payload,id FROM planned_breaks')]
        requested=[dict(loads(r['payload']),id=r['id'],status=r['status']) for r in c.execute('SELECT * FROM break_requests')]
        return planned+requested
    if db is not None:return read(db)
    with connect(path) as db:return read(db)


def availability(state,eid,start,minutes,db=None,kind="Mola"):
    eid=str(eid);a=pd.Timestamp(start);b=a+pd.Timedelta(minutes=minutes)
    if minutes<=0 or minutes>120 or a.minute%5:raise ValueError('Mola süresi ve 5 dakika adımı geçerli olmalı.')
    roster=history_rows(state,a.date()-pd.Timedelta(days=1),b.date());own=[r for r in roster if str(r['employee_id'])==eid and (span:=bounds(r)) and pd.Timestamp(span[0])<=a and b<=pd.Timestamp(span[1])]
    if not own:raise ValueError('Mola yalnızca kendi yayınlanmış çalışma vardiyan içinde alınabilir.')
    people={str(p['employee_id']):p for p in (state.get('employees_cache') or state.get('personnel_cache') or [])};person=people.get(eid,{})
    rule=state.get('status_rules',{}).get('groups',{}).get(person.get('work_type',''),{})
    if rule and own and kind=="Mola":
        span=bounds(own[0])
        if a<pd.Timestamp(span[0])+pd.Timedelta(minutes=rule.get('break_first_minutes',60)) or b>pd.Timestamp(span[1])-pd.Timedelta(minutes=rule.get('break_last_minutes',60)):raise ValueError('Vardiyanın ilk/son saatinde mola kullanılamaz.')
    languages=state.get('planning_languages') or {};lang=person.get('language') or 'tr';specific=state.get('language_demands',{}).get(lang)
    if specific is not None:need=specific;languages={k:k==lang for k in ['tr','en','ar']}
    else:need=__import__('ortak.plan_ihtiyaci',fromlist=['demand']).demand(state)
    if need is None or need.empty:raise ValueError('Bu tarih için personel ihtiyacı hesabı yok.')
    if eid in people and not languages.get(lang,True):raise ValueError('Personelin dili bu ihtiyaç hesabına dahil değil; kendi dilinin ihtiyacı hesaplanmalı.')
    roster=[r for r in roster if languages.get(people.get(str(r['employee_id']),{}).get('language') or 'tr',True)]
    existing=[r for r in records(state,db) if r.get('status')!='İptal']
    if any(str(r['employee_id'])==eid and a<pd.Timestamp(r['end']) and pd.Timestamp(r['start'])<b for r in existing):raise ValueError('Planlı yemek veya başka mola ile çakışıyor.')
    from ortak.kocluk_alanlari import read as read_openings
    openings=read_openings(state,db)
    claim=state.get('_claim_coaching_opening')
    spare=[]
    for t in pd.date_range(a,b-pd.Timedelta(seconds=1),freq='5min'):
        day=t.normalize();slot=t.hour*2+t.minute//30+1;demand=need[(pd.to_datetime(need.Tarih).dt.normalize()==day)&(need.Slot==slot)]
        if demand.empty:raise ValueError('Seçilen saat için ihtiyaç verisi yok; kapasite teyit edilemiyor.')
        workers={str(r['employee_id']) for r in roster if (span:=bounds(r)) and pd.Timestamp(span[0])<=t<pd.Timestamp(span[1])}
        on_break={str(r['employee_id']) for r in existing if str(r['employee_id']) in workers and pd.Timestamp(r['start'])<=t<pd.Timestamp(r['end'])}
        reserved=sum(max(0,int(r.get('remaining_capacity',1))-(1 if r['id']==claim else 0)) for r in openings if pd.Timestamp(r['start'])<=t<pd.Timestamp(r['end']) and (any(languages.get(lang,True) for lang in r.get('languages',[])) if r.get('pool') else languages.get(people.get(str(r['employee_id']),{}).get('language') or 'tr',True)))
        reserve=max([float(r.get('operation_reserve_count',0)) for r in openings if pd.Timestamp(r['start'])<=t<pd.Timestamp(r['end'])],default=0.)
        if state.get('status_rules',{}).get('shrinkage_included'):
            from ortak.statuler import shrinkage_for
            rate=float(demand['Shrinkage (%)'].iloc[0])/100 if 'Shrinkage (%)' in demand else shrinkage_for(state,t,slot,float(state.get('staffing_parameters',{}).get('shrinkage',.3)))
            net=float(demand['Net Agent'].max()) if 'Net Agent' in demand else float(demand['Planlanan Agent'].max())*(1-rate)
            # Extra simultaneous statuses may use the already-funded shrinkage budget.
            spare.append(max(0,len(workers)-len(on_break)-reserved-reserve-net) if len(workers)*(1-rate)>=net else 0)
        else:spare.append(len(workers-on_break)-reserved-reserve-float(demand['Planlanan Agent'].max()))
    return min(spare)


def request(state,start,minutes):
    if state.get('status_rules',{}).get('automatic'):raise ValueError('Mola hakkının tamamı otomatik planlanır; elle mola seçimi kapalıdır.')
    from ortak.personel import get_people
    from ortak.talep_servisi import now
    profile=state.get('profile') or {}
    if profile.get('position')!='agent':raise ValueError('Mola talebini Müşteri Temsilcisi kendi hesabından yapar.')
    eid=str(profile['employee_id']);people=get_people(state);person=next(p for p in people if str(p['employee_id'])==eid)
    maximum=state.get('status_rules',{}).get('groups',{}).get(person['work_type'],{}).get('break_minutes',15)
    if not 0<minutes<=maximum:raise ValueError(f'Grup mola hakkı en fazla {maximum} dakika.')
    if pd.Timestamp(start)<pd.Timestamp.now(tz='Europe/Istanbul').tz_localize(None):raise ValueError('Geçmiş saate mola talep edilemez.')
    path=state['workspace_db_path'];init(path)
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE');check=dict(state)
        for key in ('published_shift_plan','sp_staffing_result_df','status_rules','planning_languages','employees_cache','language_demands'):
            raw=db.execute('SELECT payload FROM work_state WHERE key=?',(key,)).fetchone()
            if raw:check[key]=loads(raw[0])
        check['employees_cache']=[p for p in people if p.get('position')=='agent']
        if check.get('status_rules',{}).get('automatic'):raise ValueError('Mola hakkının tamamı otomatik planlanır; elle mola seçimi kapalıdır.')
        maximum=check.get('status_rules',{}).get('groups',{}).get(person['work_type'],{}).get('break_minutes',15)
        if minutes>maximum:raise ValueError('Mola hakkı değişti; ekranı yenileyin.')
        rule=check.get('status_rules',{}).get('groups',{}).get(person['work_type'],{})
        if check.get('status_rules',{}).get('automatic'):
            from ortak.statu_planlayici import allowance
            a=pd.Timestamp(start);own=[r for r in history_rows(check,a.date(),a.date()) if str(r['employee_id'])==eid and bounds(r)]
            hours=sum((bounds(r)[1]-bounds(r)[0]).total_seconds()/3600 for r in own)
            planned=[r for r in records(check,db) if str(r['employee_id'])==eid and r['kind']=='Mola' and r['status']!='İptal' and pd.Timestamp(r['start']).date()==a.date()]
            used=sum((pd.Timestamp(r['end'])-pd.Timestamp(r['start'])).total_seconds()/60 for r in planned)
            if used+minutes>allowance(rule,hours):raise ValueError('Bu vardiyanın mola hakkı planlanmış/kullanılmış; kalan süre yetersiz.')
            end=a+pd.Timedelta(minutes=minutes);maximum_hour=int(rule.get('break_per_hour_max',15))
            for bucket in pd.date_range(a.floor('h'),(end-pd.Timedelta(seconds=1)).floor('h'),freq='h'):
                upper=bucket+pd.Timedelta(hours=1)
                booked=sum(max(0,(min(pd.Timestamp(r['end']),upper)-max(pd.Timestamp(r['start']),bucket)).total_seconds()/60) for r in planned)
                requested=max(0,(min(end,upper)-max(a,bucket)).total_seconds()/60)
                if booked+requested>maximum_hour:raise ValueError('Bir saat içindeki mola süresi grup sınırını aşıyor; başka saat seçin.')
        if availability(check,eid,start,minutes,db)<1:raise ValueError('Bu aralıkta yeterli kapasite yok; farklı saat seç.')
        item={'employee_id':eid,'start':str(pd.Timestamp(start)),'end':str(pd.Timestamp(start)+pd.Timedelta(minutes=minutes)),'kind':'Mola','created_at':now(),'actor':profile['username']};ident='BRK-'+uuid4().hex[:12]
        db.execute('INSERT INTO break_requests VALUES(?,?,?,?)',(ident,eid,'Onaylı',dumps(item)))
    return ident


def cancel(state,ident):
    init(state['workspace_db_path']);profile=state['profile']
    with connect(state['workspace_db_path']) as db:
        db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT * FROM break_requests WHERE id=?',(ident,)).fetchone()
        if not row or str(row['employee_id'])!=str(profile.get('employee_id')):raise ValueError('Kendi mola talebini seç.')
        if pd.Timestamp(loads(row['payload'])['start'])<=pd.Timestamp.now(tz='Europe/Istanbul').tz_localize(None):raise ValueError('Başlamış mola iptal edilemez.')
        db.execute("UPDATE break_requests SET status='İptal' WHERE id=?",(ident,))

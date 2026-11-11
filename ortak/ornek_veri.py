# Ortak / Ornek Veri — bu ekranın / servisin uygulama kodu.
"""Deterministic synthetic call history and a persistent, explorable workbench."""
from datetime import date, datetime, timedelta
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from ortak.varsayilan_kurallar import default_shift_rules
from ortak.calisma_alani_deposu import DEFAULT_DB, connect, dumps, init_db, load_calls, save_keys, put_request, hydrate


def employees():
    from ortak.personel_deposu import list_people
    return list_people()


def ensure_demo(path=DEFAULT_DB, today=None):
    init_db(path)
    with connect(path) as con:
        if con.execute("SELECT 1 FROM metadata WHERE key='demo_version'").fetchone():
            return
    today=today or datetime(2026,11,10).date()
    end=today-timedelta(days=1)
    dates=pd.date_range(end-timedelta(days=729),end)
    rng=np.random.default_rng(20261107)
    daily,intervals=[],[]
    hours=np.arange(48)/2
    weights=.025+np.exp(-((hours-11)/3.5)**2)+.82*np.exp(-((hours-17)/3.7)**2)
    weights/=weights.sum()
    for i,d in enumerate(dates):
        weekly=[1.12,1.06,1.02,1.00,1.08,.69,.53][d.weekday()]
        annual=1+.08*np.sin(2*np.pi*d.dayofyear/365.25)
        billing=1.08 if d.day in (9,16,24,31) else 1
        total=int(max(1000,12500*weekly*annual*billing*(1+i*.00012)+rng.normal(0,480)))
        aht=float(round(290+18*np.sin(2*np.pi*d.dayofyear/365)+rng.normal(0,7),1))
        counts=rng.multinomial(total,weights)
        daily.append((str(d.date()),total,aht))
        intervals.extend((str(d.date()),slot+1,int(n),round(aht+rng.normal(0,4),1)) for slot,n in enumerate(counts))
    all_staff=employees()
    agents=[e for e in all_staff if e['position']=='agent']
    academy=[e for e in agents if e['work_type']=='akademi']
    next_week=datetime(2026,11,10).date()
    term=f"{today.year}-{'Güz' if today.month>=8 else 'Bahar'}"
    schedules,exams={},{}
    for i,e in enumerate(academy[:12]):
        schedules[e['username']]={term:{'Saat':['08:00-10:00','10:00-12:00','12:00-14:00','14:00-16:00','16:00-18:00','18:00-20:00'],
                                      'Pazartesi':['Matematik','','','','',''],'Salı':['','İstatistik','','','',''],
                                      'Çarşamba':['','','','','',''],'Perşembe':['','','Bölüm dersi','','',''],
                                      'Cuma':['','','','','',''],'Cumartesi':['','','','','',''],'Pazar':['','','','','','']}}
        if i<4:
            exams[e['username']]={f'{today.year}-Sinav':{'Tarih':[str(next_week+timedelta(days=i))],
                                                        'Saat':['10:00'],'Ders':['Dönem sınavı'],'Sınav Türü':['Vize'],'Not':['Örnek sınav bildirimi']}}
    fixed=[]
    # Rotate people through existing night assignments; each person gets at most
    # two nights. These are fixture records, not auto-generated working shifts.
    for day_i in range(7):
        for lang,count in [('tr',2),('en',1),('ar',1)]:
            pool=[e for e in academy if e['language']==lang and e['username'] not in schedules]
            if not pool:
                pool=[e for e in academy if e['language']==lang]
            for offset in range(count):
                e=pool[(day_i*count+offset)%len(pool)]
                d=str(next_week+timedelta(days=day_i))
                fixed.append({'id':f'DEMO-N-{day_i}-{lang}-{offset}','employee_id':str(e['employee_id']),
                              'full_name':e['full_name'],'start_date':d,'end_date':d,'shift_code':'GECE',
                              'start':default_shift_rules()['general']['night_window_start'],'end':default_shift_rules()['general']['night_window_end'],'note':'Hazır demo gece kaydı'})
    for i,e in enumerate([e for e in agents if e['work_type']=='fulltime'][:3]):
        fixed.append({'id':f'DEMO-L-{i}','employee_id':str(e['employee_id']),'full_name':e['full_name'],
                      'start_date':str(next_week),'end_date':str(next_week+timedelta(days=2)),
                      'shift_code':'YILLIK_IZIN','start':None,'end':None,'note':'Hazır demo yıllık izin kaydı'})
    published=[]
    for e in agents:
        for i in range(7):
            d=next_week-timedelta(days=7-i)
            work=i<5
            hours={'fulltime':9,'akademi':7,'dis_kaynak':10}[e['work_type']]
            published.append({'employee_id':str(e['employee_id']),'full_name':e['full_name'],'date':str(d),
                              'group':e['work_type'],'shift_code':'WORK' if work else 'OFF',
                              'start':'08:00' if work else None,'end':f'{8+hours:02d}:00' if work else None,'source':'demo','note':'Örnek yayınlanmış geçmiş plan'})
    state={'acad_schedules':schedules,'acad_exam_calendar':exams,'acad_bayram_requests':{},
           'fixed_shift_records':fixed,'published_shift_plan':published,'draft_shift_plan':[],
           'shift_rules':default_shift_rules(),'plan_group_priority':['akademi','fulltime','dis_kaynak'],
           'plan_ctx':{'start':next_week,'end':next_week+timedelta(days=6)},'plan_ctx_confirmed':True}
    request_rows=[]
    for i,e in enumerate(agents[:16]):
        typ=['Yıllık İzin Talebi','Mesai Talebi','Genel Talep','Gece Vardiyası Talebi'][i%4]
        if typ=='Gece Vardiyası Talebi' and e['work_type']!='akademi':
            typ='Genel Talep'
        status,queue=[('Beklemede','TL'),('Planlamaya İletildi','WFM'),('Uygulandı','Closed'),('Reddedildi','Closed')][i%4]
        rid=f'DEMO-REQ-{i+1:03d}'
        d=str(next_week+timedelta(days=i%5))
        created=(datetime.combine(today-timedelta(days=3),datetime.min.time())+timedelta(hours=9,minutes=i)).isoformat()
        events=[{'at':created,'actor':e['username'],'actor_name':e['full_name'],'action':'Talep oluşturuldu','from':'—','to':'Beklemede','note':'Hazır demo kaydı'}]
        if queue!='TL':
            events.append({'at':created,'actor':'demo-tl','actor_name':e['team_lead'],'action':'Takım lideri onayladı ve planlamaya iletti','from':'Beklemede','to':'Planlamaya İletildi','note':'Uygunluk kontrolü için planlamaya iletildi.'})
        if queue=='Closed':
            events.append({'at':created,'actor':'demo-wfm','actor_name':'WFM Ekibi','action':'Planlama onayladı; plana alınacak' if status=='Uygulandı' else 'Planlama reddetti',
                           'from':'Planlamaya İletildi','to':status,'note':'Örnek karar: uygun bulundu.' if status=='Uygulandı' else 'İlgili tarihte personel ihtiyacı nedeniyle uygun bulunmadı.'})
        request_rows.append({'id':rid,'created_by':e['username'],'created_by_name':e['full_name'],'employee_id':e['employee_id'],
                             'type':typ,'note':'Örnek: belirtilen tarihte vardiya planımın değerlendirilmesini istiyorum.',
                             'start_date':d,'end_date':d,'overtime_start':'00:00' if typ=='Gece Vardiyası Talebi' else ('18:00' if typ=='Mesai Talebi' else None),
                             'overtime_end':default_shift_rules()['general']['night_window_end'] if typ=='Gece Vardiyası Talebi' else ('20:00' if typ=='Mesai Talebi' else None),
                             'assigned_tls':[e['team_lead']],'targets':[],'queue':queue,'status':status,'version':1,
                             'events':events,'created_at':created,'source':'personel','attachment':None})
    # A real structured school notification for inbox/detail testing.
    if academy:
        e=academy[0]
        request_rows.append({'id':'DEMO-CLASS-001','created_by':e['username'],'created_by_name':e['full_name'],
                             'employee_id':e['employee_id'],'type':'Ders Programı','note':f'{term} ders programı',
                             'assigned_tls':[e['team_lead']],'targets':[],'queue':'TL','status':'Beklemede','version':1,
                             'created_at':datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(),'source':'class_schedule',
                             'generated_from':'class_schedule','generated_ref':f"{e['username']}::{term}",
                             'attachment':{'title':term,'rows':pd.DataFrame(schedules[e['username']][term]).to_dict('records')},'events':[]})
    with connect(path) as con:
        con.execute('BEGIN IMMEDIATE')
        # A second process may have initialised the same database while data was built.
        if con.execute("SELECT 1 FROM metadata WHERE key='demo_version'").fetchone():
            return
        con.executemany('INSERT OR IGNORE INTO calls_daily VALUES(?,?,?)',daily)
        con.executemany('INSERT OR IGNORE INTO calls_interval VALUES(?,?,?,?)',intervals)
        for key,value in state.items():
            con.execute('INSERT OR IGNORE INTO work_state VALUES(?,?)',(key,dumps(value)))
        for row in request_rows:
            con.execute('INSERT OR IGNORE INTO requests VALUES(?,?,?)',(row['id'],1,dumps(row)))
            for seq,event in enumerate(row['events']):
                con.execute('INSERT OR IGNORE INTO request_events(request_id,sequence,payload) VALUES(?,?,?)',(row['id'],seq,dumps(event)))
        con.execute('INSERT INTO metadata VALUES(?,?)',('demo_version','1'))
        con.execute('INSERT INTO metadata VALUES(?,?)',('history_end',str(end)))
        con.execute('INSERT INTO metadata VALUES(?,?)',('synthetic','true'))


def load_demo_history(state, interval=False, path=DEFAULT_DB):
    from ortak.calisma_modu import demo_enabled
    source='Hazır Demo Veritabanı' if demo_enabled() else 'Çağrı Veritabanı'
    df=load_calls(interval,path)
    for key in list(state):
        if key.startswith(('cf_model','cf_candidate','cf_X_','cf_y_','cf_scaler','cf_forecast','cf_selected','cf_bank_','cf_daily_','cf_slot_')):
            del state[key]
    state.update(cf_all_df=df.copy(),cf_raw_df=df.copy(),cf_full_df=df.copy(),
                 cf_meta={'rows':len(df),'cols':len(df.columns),'columns':list(df),'source':source},
                 cf_last_filename='SQLite · 30 dk' if interval else 'SQLite · günlük',cf_source=source,
                 cf_target_name='cagri_sayisi',cf_scope_enabled=False,cf_scope_sig=('ALL',))
    return df


def bootstrap(state, path=DEFAULT_DB):
    from ortak.calisma_modu import demo_enabled
    demo=demo_enabled();state['production_mode']=not demo
    if demo:
        from ortak.sabit_demo import directory
        directory(state)
        ensure_demo(path)
    else:init_db(path)
    # Preserve a pre-database user session when adopting the new workbench.
    if not state.get('workspace_hydrated_path') and state.get('cf_all_df') is not None:
        from ortak.calisma_alani_deposu import get_requests
        existing={r['id'] for r in get_requests(path)}
        for request in state.get('trk_requests',[]):
            if request.get('id') and request['id'] not in existing:
                put_request(request,path=path)
        state['workspace_db_path']=str(path)
        save_keys(state)
    hydrate(state,path)
    if demo:
        from ortak.sabit_demo import prepare
        prepare(state,path)
        from ortak.statu_gecmisi import seed_demo
        seed_demo(state)
    from ortak.varsayilan_kurallar import enforce_current_rules
    if not state.get('shift_rules'):state['shift_rules']=default_shift_rules()
    if not state.get('plan_ctx'):
        start=datetime(2026,11,10).date()
        state.update(plan_ctx={'start':start,'end':start+timedelta(days=6)},plan_ctx_confirmed=False)
    from ortak.statuler import defaults
    state.setdefault("status_rules",dict(defaults(),enabled=True))
    state["status_rules"]["shrinkage_included"]=True
    state["status_rules"]["enabled"]=True
    state["status_rules"]["automatic"]=True
    state["status_rules"]["coaching_by_leader"]=True
    state["status_rules"].setdefault("operation_reserve_rate",.05)
    state["status_rules"]["coaching_slot_minutes"]=15
    state["status_rules"].setdefault("coaching_by_leader",True)
    from copy import deepcopy
    for group,settings in defaults()["groups"].items():
        target=state["status_rules"].setdefault("groups",{}).setdefault(group,{})
        for field,value in settings.items():
            if field=='break_preferred_minutes':value=min(value,max(1,int(target.get('break_minutes',15))))
            target.setdefault(field,deepcopy(value))
    enforce_current_rules(state)
    state["shift_rules"].setdefault("friday",{"prefer_women_midday":True,"block_men_midday":False})
    state["shift_rules"].setdefault("publication_approvals",{"enabled":True})
    state["shift_rules"].setdefault("capacity",{"max_overstaff":2,"min_overtime_hours":4})
    from ortak.gunluk_tahmin_deposu import capture_daily
    for option in state.get('cf_forecast_options',[]):
        if not option.get('daily_record_id'):option['daily_record_id']=capture_daily(state,option['frame'],option['meta'])
    from ortak.personel import get_people
    get_people(state)
    if not state.get('employees_cache'):
        state['employees_cache']=[e for e in get_people(state) if e['position']=='agent']
    if state.get('cf_all_df') is None:
        # İlk oturum açılışı kayıtlı tahmin seçeneklerini yeni deneme gibi üretmez.
        saved_options=state.get('cf_forecast_options')
        load_demo_history(state,path=path)
        if saved_options:state['cf_forecast_options']=saved_options
    if not demo:
        save_keys(state);return
    # Four genuine model fits per session; persisted forecasts stay intact.
    if not state.get('cf_model_candidates') and state.get('cf_last_filename','').startswith('SQLite'):
        from ortak.cagri_tahmin_servisi import reference_models,forecast_candidates
        from ortak.veri_onbellegi import cached_calls,demo_model_snapshot
        state.update(demo_model_snapshot(cached_calls(str(path))))
        if not state.get('cf_forecast_options'):
            ctx=state['plan_ctx']
            forecast_candidates(state,ctx['start'],ctx['end'])
    if state.get('cf_forecast_options') and state.get('sp_forecast_df') is None:
        from ortak.cagri_tahmin_servisi import activate_forecast
        first=state['cf_forecast_options'][0]
        activate_forecast(state,first['frame'],first['meta'])
    if state.get('sp_active_ratio_profile_df') is None and not state.get('demo_initial_profile_done'):
        from ortak.cagri_tahmin_servisi import DAY_NAMES
        from ortak.veri_onbellegi import cached_calls
        df=cached_calls(str(path),True)
        df['Gün']=df.tarih.dt.weekday.map(dict(enumerate(DAY_NAMES)))
        df['Slot']=df.slot
        grp=df.groupby(['Gün','Slot'],as_index=False).cagri_sayisi.sum()
        grp['Oran(%)']=100*grp.cagri_sayisi/grp.groupby('Gün').cagri_sayisi.transform('sum')
        grp['Aralık']=grp.Slot.map(lambda s:f'{((s-1)*30)//60:02d}:{((s-1)*30)%60:02d} - {(s*30)//60:02d}:{(s*30)%60:02d}')
        profile=grp[['Gün','Slot','Aralık','Oran(%)']]
        name='Demo · 2 yıllık 30 dk dağılım'
        state.update(sp_active_ratio_profile_df=profile,sp_active_ratio_profile_name=name,
                     sp_ratio_profiles=[{'name':name,'profile_df':profile,'created_at':datetime.now().isoformat(), 'meta':{'source':'SQLite demo'}}])
    if state.get('sp_active_ratio_profile_df') is not None:
        state['demo_initial_profile_done']=True
    if (state.get('sp_staffing_result_df') is None and state.get('sp_forecast_df') is not None
            and state.get('sp_active_ratio_profile_df') is not None and not state.get('demo_initial_staffing_done')):
        from modules.mesai_plani.personel_ihtiyaci import calculate_staffing
        state['sp_staffing_result_df']=calculate_staffing(state['sp_forecast_df'],state['sp_active_ratio_profile_df'])
        state['plan_ctx_confirmed']=True
        state['demo_initial_staffing_done']=True
    save_keys(state)
    from ortak.tahmin_kayit_servisi import migrate_legacy
    migrate_legacy(state)
    from ortak.ornek_gecmis_tahmin import prepare_demo_backtest
    prepare_demo_backtest(state)
    from ortak.ornek_gecmis_tahmin import prepare_six_month_history
    prepare_six_month_history(state)

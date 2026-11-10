"""Kesin Gece ve İzin Kayıtları — onaylı talepleri, sabitleri ve yayını tek takvimde birleştirir."""
import pandas as pd


def fixed_calendar_rows(state,start,end):
    from ortak.planlama import REQUEST_CODES
    from ortak.sabit_demo import history_rows
    rows={};start=pd.Timestamp(start).date();end=pd.Timestamp(end).date()
    def add(record,code,source):
        a=record.get('date') or record.get('start_date');b=record.get('date') or record.get('end_date') or a
        if not a:return
        for d in pd.date_range(max(start,pd.Timestamp(a).date()),min(end,pd.Timestamp(b).date())):
            eid=record.get('employee_id')
            if eid is None:continue
            row={'employee_id':str(eid),'date':str(d.date()),'shift_code':code,'start':record.get('start') or record.get('overtime_start'),'end':record.get('end') or record.get('overtime_end'),'source':source,'request_id':record.get('id')}
            rows[(str(eid),row['date'])]=row
    # Published records are supplemented by newly approved requests and fixed records.
    for r in history_rows(state,start,end):add(r,r.get("shift_code"),"published")
    for req in state.get('trk_requests',[]):
        if req.get('status') not in {'Onaylandı','Uygulandı'} or req.get('queue') in {'TL','TL_SWAP','WFM'}:continue
        code=REQUEST_CODES.get(req.get('type'))
        if code:add(req,code,'approved_request')
    for r in state.get('fixed_shift_records',[]):add(r,r.get('shift_code'),'fixed_external')
    for r in state.get('published_shift_plan',[]):
        if r.get('change_id'):add(r,r.get('shift_code'),'audited_change')
    return list(rows.values())


def night_capacity_check(state,employee_id,start,end,exclude_request=None):
    from ortak.personel import planner_people
    people={str(e['employee_id']):e for e in planner_people(state)};person=people.get(str(employee_id))
    if not person:raise ValueError('Personel bulunamadı.')
    rules=state.get('shift_rules') or {};night=rules.get('night',{})
    allowed=night.get('allowed_work_types',['akademi'])
    if not night.get('enabled',False) or person.get('work_type') not in allowed or not rules.get('work_type',{}).get(person.get('work_type'),{}).get('night_allowed',False):raise ValueError('Çalışma grubun için gece talebi açık değil.')
    lang=person.get('language') or 'tr';target=int(night.get(night.get('mode','normal'),{}).get(lang,0))
    if target<=0:raise ValueError('Bu dil için gece kontenjanı tanımlı değil.')
    used=fixed_calendar_rows(state,start,end)
    occupied={(r['employee_id'],r['date']) for r in used if r['shift_code']=='GECE' and people.get(r['employee_id'],{}).get('language','tr')==lang}
    for req in state.get('trk_requests',[]):
        if req.get('id')==exclude_request or req.get('type')!='Gece Vardiyası Talebi' or req.get('status') in {'Reddedildi','İptal Edildi','Güncellendi'}:continue
        eid=str(req.get('employee_id'))
        if people.get(eid,{}).get('language','tr')!=lang:continue
        for d in pd.date_range(max(pd.Timestamp(start),pd.Timestamp(req['start_date'])),min(pd.Timestamp(end),pd.Timestamp(req.get('end_date') or req['start_date']))):occupied.add((eid,str(d.date())))
    for d in pd.date_range(start,end):
        day=str(d.date());count=sum(date==day for _,date in occupied)
        if (str(employee_id),day) in occupied:raise ValueError(f'{d:%d.%m.%Y}: zaten gece kaydın veya bekleyen talebin var.')
        if count>=target:raise ValueError(f'{d:%d.%m.%Y}: gece listesi dolu ({count}/{target}); yeni talep iletilemez.')
    return True


def store_night_request(state,row):
    from ortak.calisma_alani_deposu import connect,loads,put_request_in_transaction
    path=state['workspace_db_path']
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE');check=dict(state)
        for key in ('fixed_shift_records','published_shift_plan','shift_rules'):
            stored=db.execute('SELECT payload FROM work_state WHERE key=?',(key,)).fetchone()
            if stored:check[key]=loads(stored[0])
        check['trk_requests']=[loads(r[0]) for r in db.execute('SELECT payload FROM requests')]
        night_capacity_check(check,row['employee_id'],row['start_date'],row['end_date'])
        saved=put_request_in_transaction(db,row)
    state['trk_requests']=[r for r in state.get('trk_requests',[]) if r['id']!=saved['id']]+[saved]
    return saved

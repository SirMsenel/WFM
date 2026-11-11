"""Yönetim ajandası: çalışma aralıkları ve ekip uygunluğuna göre koçluk."""
from uuid import uuid4
import pandas as pd
from ortak.calisma_alani_deposu import connect,dumps,loads
from ortak.personel import get_people,visible_people
from ortak.roller_ve_yetkiler import append_audit,init_governance
from modules.vardiya_plani.vardiya_motoru import bounds
MANAGEMENT={'tl','manager','assistant_manager','wfm','planning_manager','moderator'}

def init(path):
    init_governance(path)
    with connect(path) as db:db.execute('CREATE TABLE IF NOT EXISTS manager_agenda(id TEXT PRIMARY KEY,owner TEXT NOT NULL,employee_id TEXT,start TEXT NOT NULL,end TEXT NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL)')


def rows(state,all_visible=False):
    path=state['workspace_db_path'];init(path);profile=state['profile'];role=profile.get('position')
    if role not in MANAGEMENT:return []
    with connect(path) as db:items=[dict(loads(r['payload']),id=r['id'],owner=r['owner'],employee_id=r['employee_id'],start=r['start'],end=r['end'],kind=r['kind']) for r in db.execute('SELECT * FROM manager_agenda ORDER BY start')]
    if all_visible and role in {'manager','assistant_manager','wfm','planning_manager','moderator'}:return items
    return [r for r in items if r['owner']==profile['username']]


def add_work(state,start,end):
    p=state['profile'];a,b=pd.Timestamp(start),pd.Timestamp(end)
    if p.get('position') not in MANAGEMENT:raise ValueError('Ajanda yönetim rolleri içindir.')
    if pd.isna(a) or pd.isna(b) or a>=b or (b-a).total_seconds()>16*3600:raise ValueError('Geçerli, en fazla 16 saatlik çalışma aralığı girin.')
    path=state['workspace_db_path'];init(path);ident='AG-'+uuid4().hex[:12]
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT 1 FROM manager_agenda WHERE owner=? AND kind='Çalışma' AND start<? AND end>?",(p['username'],str(b),str(a))).fetchone():raise ValueError('Çalışma aralığı ajandada zaten var veya çakışıyor.')
        db.execute('INSERT INTO manager_agenda VALUES(?,?,?,?,?,?,?)',(ident,p['username'],str(p['employee_id']),str(a),str(b),'Çalışma',dumps({'name':p.get('full_name',p['username'])})));append_audit(db,'Ajandaya çalışma eklendi',p,{'id':ident,'start':str(a),'end':str(b)})
    return ident


def add_coaching(state,eid,start,minutes=15,opening_id=None):
    p=state['profile'];eid=str(eid);all_people=get_people(state);person=next((x for x in visible_people(p,all_people) if str(x['employee_id'])==eid),None)
    if p.get('position') not in MANAGEMENT or person is None:raise ValueError('Yalnızca yetki kapsamındaki personele görüşme atayabilirsin.')
    a=pd.Timestamp(start);b=a+pd.Timedelta(minutes=int(minutes))
    if pd.isna(a) or minutes<5 or minutes>60:raise ValueError('Görüşme süresi 5–60 dakika olmalı.')
    if a<pd.Timestamp.now(tz='Europe/Istanbul').tz_localize(None):raise ValueError('Geçmişe görüşme atanamaz.')
    path=state['workspace_db_path'];init(path)
    from ortak.kocluk_alanlari import init as init_openings
    init_openings(path)
    from ortak.mola_servisi import init as init_breaks,availability
    init_breaks(path)
    from ortak.sabit_demo import history_rows
    ident='COACH-'+uuid4().hex[:12]
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        work=db.execute("SELECT 1 FROM manager_agenda WHERE owner=? AND kind='Çalışma' AND start<=? AND end>=?",(p['username'],str(a),str(b))).fetchone()
        if not work:raise ValueError('Önce bu saati kapsayan çalışma aralığını kendi ajandana gir.')
        if db.execute("SELECT 1 FROM manager_agenda WHERE kind='Koçluk' AND (owner=? OR employee_id=?) AND start<? AND end>?",(p['username'],eid,str(b),str(a))).fetchone():raise ValueError('Takım liderinin veya personelin başka görüşmesi var.')
        check=dict(state)
        for key in ('published_shift_plan','sp_staffing_result_df','status_rules','planning_languages','language_demands','slot_shrinkage','staffing_parameters'):
            raw=db.execute('SELECT payload FROM work_state WHERE key=?',(key,)).fetchone()
            if raw:check[key]=loads(raw[0])
        check['employees_cache']=[x for x in all_people if x.get('position')=='agent']
        if opening_id:
            opening=db.execute("SELECT * FROM coaching_openings WHERE id=? AND status='Açık'",(opening_id,)).fetchone()
            if not opening:raise ValueError('Koçluk alanı artık uygun değil; listeyi yenileyin.')
            slot=loads(opening['payload'])
            from ortak.kocluk_alanlari import accepts
            if not accepts(slot,eid) or pd.Timestamp(slot['start'])!=a or pd.Timestamp(slot['end'])!=b:raise ValueError('Seçilen personel ve saat ayrılmış alanla eşleşmiyor.')
            check['_claim_coaching_opening']=opening_id
        if check.get('status_rules',{}).get('automatic') and not opening_id:raise ValueError('Koçluğu planlamada ayrılan kontenjandan seçin.')
        if availability(check,eid,a,minutes,db,kind="Koçluk")<1:raise ValueError('Bu dilimde görüşme için hat kapasitesi yetersiz.')
        cfg=check.get('status_rules',{}).get('groups',{}).get(person['work_type'],{});target=int(cfg.get('coaching_monthly_minutes',60));used=0
        for record in db.execute('SELECT payload FROM planned_breaks'):
            r=loads(record[0])
            if str(r['employee_id'])==eid and r.get('kind')=='Koçluk' and r['start'][:7]==str(a)[:7]:used+=(pd.Timestamp(r['end'])-pd.Timestamp(r['start'])).total_seconds()/60
        if not cfg.get('coaching_multiple_per_week',False):
            week=a.normalize()-pd.Timedelta(days=a.weekday());week_end=week+pd.Timedelta(days=7)
            for record in db.execute('SELECT payload FROM planned_breaks'):
                other=loads(record[0])
                if str(other['employee_id'])==eid and other.get('kind')=='Koçluk' and week<=pd.Timestamp(other['start'])<week_end:raise ValueError('Bu personel aynı hafta zaten koçluk aldı. Grup kuralı ikinci görüşmeye izin vermiyor.')
        if used+minutes>target:raise ValueError('Personelin aylık koçluk hedefi aşılır; başka dönem veya süre seçin.')
        payload={'employee_id':eid,'date':str(a.date()),'kind':'Koçluk','start':str(a),'end':str(b),'status':'Planlı','leader':p['username'],**({'opening_id':opening_id} if opening_id else {})}
        db.execute('INSERT INTO manager_agenda VALUES(?,?,?,?,?,?,?)',(ident,p['username'],eid,str(a),str(b),'Koçluk',dumps({'name':person['full_name'],**({'opening_id':opening_id} if opening_id else {})})))
        db.execute('INSERT INTO planned_breaks VALUES(?,?,?)',(ident,'AGENDA',dumps(payload)))
        if opening_id:
            remaining=int(slot.get('remaining_capacity',1))-1
            if remaining<0:raise ValueError('Koçluk kontenjanı doldu; listeyi yenileyin.')
            slot['remaining_capacity']=remaining
            db.execute("UPDATE coaching_openings SET status=?,payload=? WHERE id=? AND status='Açık'",('Açık' if remaining else 'Atandı',dumps(slot),opening_id))
        append_audit(db,'Koçluk atandı',p,payload)
    return ident


def save_week(state,week,entries):
    from datetime import datetime
    p=state['profile']
    if p.get('position') not in MANAGEMENT:raise ValueError('Ajanda yönetim rolleri içindir.')
    left=pd.Timestamp(week).normalize();right=left+pd.Timedelta(days=7);prepared=[]
    for entry in entries:
        if not entry.get('Çalışıyor'):continue
        day=pd.Timestamp(entry['Tarih']);a=pd.Timestamp(f"{day.date()} {entry['Başlangıç']}");b=pd.Timestamp(f"{day.date()} {entry['Bitiş']}")
        if b<a:b+=pd.Timedelta(days=1)
        if not left<=a<right or a>=b or b-a>pd.Timedelta(hours=16):raise ValueError('Çalışma günü ve saatleri geçerli olmalı; en fazla 16 saat.')
        if any(a<y and x<b for x,y in prepared):raise ValueError('Çalışma saatleri çakışıyor.')
        prepared.append((a,b))
    path=state['workspace_db_path'];init(path)
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        meetings=db.execute("SELECT start,end FROM manager_agenda WHERE owner=? AND kind='Koçluk' AND start<? AND end>?",(p['username'],str(right),str(left))).fetchall()
        if any(not any(a<=pd.Timestamp(m['start']) and pd.Timestamp(m['end'])<=b for a,b in prepared) for m in meetings):raise ValueError('Atanmış koçluk görüşmelerini kapsayan çalışma saatleri korunmalı.')
        db.execute("DELETE FROM manager_agenda WHERE owner=? AND kind='Çalışma' AND start>=? AND start<?",(p['username'],str(left),str(right)))
        other=db.execute("SELECT start,end FROM manager_agenda WHERE owner=? AND kind='Çalışma'",(p['username'],)).fetchall()
        for a,b in prepared:
            if any(a<pd.Timestamp(r['end']) and pd.Timestamp(r['start'])<b for r in other):raise ValueError('Komşu haftanın çalışma kaydıyla çakışma var.')
            db.execute('INSERT INTO manager_agenda VALUES(?,?,?,?,?,?,?)',('AG-'+uuid4().hex[:12],p['username'],str(p['employee_id']),str(a),str(b),'Çalışma',dumps({'name':p.get('full_name',p['username'])})))
        append_audit(db,'Haftalık ajanda kaydedildi',p,{'start':str(left),'end':str(right),'work':[(str(a),str(b)) for a,b in prepared]})

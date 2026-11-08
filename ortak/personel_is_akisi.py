# Ortak / Personel Is Akisi — bu ekranın / servisin uygulama kodu.
"""Personel Ekleme / Çıkarma — Takım Lideri → Yönetici → Planlama."""
from uuid import uuid4
import pandas as pd
from ortak.calisma_alani_deposu import connect,dumps,loads,save_keys
from ortak.roller_ve_yetkiler import init_governance,require,append_audit
from ortak.personel_deposu import auth_path,ensure_identity
from ortak.talep_servisi import now


def proposals(state):
    init_governance(state['workspace_db_path'])
    with connect(state['workspace_db_path']) as db:return [dict(loads(r['payload']),version=r['version']) for r in db.execute('SELECT * FROM personnel_workflows ORDER BY rowid DESC')]


def submit(state,kind,values,reason):
    require(state,'personel_talebi');profile=state['profile']
    if profile.get('position')!='tl':raise ValueError('Personel önerisini Takım Lideri iletir.')
    if kind not in {'Ekleme','Ayrılma'} or not reason.strip():raise ValueError('İşlem türü ve gerekçe gerekli.')
    manager=profile.get('manager')
    if not manager:raise ValueError('Takım liderinin yöneticisi tanımlı değil.')
    values=dict(values)
    if kind=='Ekleme':
        if any(not str(values.get(k,'')).strip() for k in ('full_name','sicil_no','username','work_type','language','location')):raise ValueError('Ad, sicil, kullanıcı adı, grup, dil ve lokasyon gerekli.')
        if values['work_type'] not in {'fulltime','akademi','dis_kaynak'}:raise ValueError('Çalışma grubu geçersiz.')
        values.update(team_lead=profile['full_name'],manager=manager,position='agent')
    else:
        from ortak.personel_deposu import list_people
        selected=next((r for r in list_people(state) if str(r['employee_id'])==str(values.get('employee_id')) and r.get('team_lead')==profile['full_name']),None)
        if not selected:raise ValueError('Ayrılma için kendi ekibinden bir kişi seçin.')
        values={**selected,'effective_date':values.get('effective_date')}
    date=pd.to_datetime(values.get('effective_date'),errors='coerce')
    if pd.isna(date):raise ValueError('Geçerli işe giriş / ayrılma tarihi gerekli.')
    values['effective_date']=str(date.date());values.pop('password',None)
    item={'id':'HR-'+uuid4().hex[:12],'kind':kind,'values':values,'reason':reason.strip(),'stage':'Yönetici onayı','created_by':profile.get('username'),
          'team_lead':profile['full_name'],'manager':manager,'created_at':now(),'events':[]}
    path=state['workspace_db_path'];init_governance(path)
    with connect(path) as db:
        db.execute('INSERT INTO personnel_workflows VALUES(?,?,?)',(item['id'],1,dumps(item)));append_audit(db,'Personel talebi',profile,item)
    return dict(item,version=1)


def decide(state,item,approve,note='',password=None):
    profile=state['profile'];role=profile.get('position');stage=item['stage']
    if stage=='Yönetici onayı':
        require(state,'personel_incele')
        if role!='moderator' and profile.get('full_name')!=item['manager']:raise ValueError('Bu personel talebi başka yöneticinin onayında.')
        next_stage='Planlama onayı'
    elif stage=='Planlama onayı':require(state,'personel_onayla');next_stage='Tamamlandı'
    else:raise ValueError('Sonuçlanan personel talebi tekrar işlenemez.')
    if not approve and not note.strip():raise ValueError('Ret gerekçesi gerekli.')
    path=state['workspace_db_path'];init_governance(path)
    identity=auth_path(state)
    if approve and next_stage=='Tamamlandı':
        import os
        from ortak.calisma_modu import demo_enabled
        if not demo_enabled():raise ValueError('Kurumsal personel kaynağı etkin. Bu onayı kurumsal İK yazma adaptörüne bağlamadan yerel personel değişikliği uygulanamaz.')
        ensure_identity(identity)
    with connect(path) as db:
        if approve and next_stage=='Tamamlandı':db.execute('ATTACH DATABASE ? AS kimlik',(identity,))
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT * FROM personnel_workflows WHERE id=?',(item['id'],)).fetchone()
        if not old or old['version']!=item['version']:raise ValueError('Talep başka bir oturumda değişti. Yenileyin.')
        new=loads(old['payload']);new['stage']=next_stage if approve else 'Reddedildi'
        if approve and next_stage=='Tamamlandı':
            v=new['values']
            if new['kind']=='Ekleme':
                if db.execute('SELECT 1 FROM kimlik.employees WHERE sicil_no=?',(str(v['sicil_no']),)).fetchone() or db.execute('SELECT 1 FROM kimlik.users WHERE username=?',(v['username'],)).fetchone():raise ValueError('Sicil veya kullanıcı adı zaten kayıtlı.')
                eid=db.execute('INSERT INTO kimlik.employees(full_name,team_lead,manager,location,work_type,position,language,sicil_no,employment_start) VALUES(?,?,?,?,?,?,?,?,?)',tuple(v[k] for k in ['full_name','team_lead','manager','location','work_type','position','language','sicil_no','effective_date'])).lastrowid
                hashed='!KURUMSAL_GIRIS_BEKLIYOR'
                if password:
                    if len(password)<8:raise ValueError('Geçici parola en az 8 karakter olmalı.')
                    from passlib.context import CryptContext
                    hashed=CryptContext(schemes=['pbkdf2_sha256'],deprecated='auto').hash(password)
                db.execute('INSERT INTO kimlik.users(username,password_hash,employee_id,is_active) VALUES(?,?,?,1)',(v['username'],hashed,eid));new['employee_id']=str(eid)
            else:
                db.execute('UPDATE kimlik.employees SET employment_end=? WHERE employee_id=?',(v['effective_date'],v['employee_id']))
                from datetime import datetime
                from zoneinfo import ZoneInfo
                if v['effective_date']<=datetime.now(ZoneInfo('Europe/Istanbul')).date().isoformat():db.execute('UPDATE kimlik.users SET is_active=0 WHERE employee_id=?',(v['employee_id'],))
        new['events'].append({'actor':profile.get('username'),'date':now(),'decision':'Onay' if approve else 'Ret','note':note})
        db.execute('UPDATE personnel_workflows SET version=version+1,payload=? WHERE id=?',(dumps(new),item['id']))
        if approve and next_stage=='Tamamlandı':db.execute("INSERT INTO metadata VALUES('directory_revision',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(now()+uuid4().hex,))
        append_audit(db,'Personel kararı',profile,{'before':loads(old['payload']),'after':new,'reason':note})
    state.pop('personnel_cache',None);state.pop('employees_cache',None)
    from ortak.personel import planner_people
    planner_people(state);return dict(new,version=item['version']+1)

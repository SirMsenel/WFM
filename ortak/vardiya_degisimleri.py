# Ortak / Vardiya Degisimleri — bu ekranın / servisin uygulama kodu.
"""Vardiya Değişiklikleri — ortak kontrol, toplam koruma ve değişmez işlem kaydı."""
from copy import deepcopy
from uuid import uuid4
import pandas as pd
from ortak.calisma_alani_deposu import connect,dumps,loads,save_keys
from ortak.roller_ve_yetkiler import require,init_governance,append_audit
from modules.vardiya_plani.vardiya_motoru import bounds,generate_plan


def totals(rows):
    result={}
    for r in rows:
        eid=str(r['employee_id']);item=result.setdefault(eid,{'hours':0.,'off':0})
        interval=bounds(r)
        if interval:item['hours']+=(interval[1]-interval[0]).total_seconds()/3600
        if r.get('shift_code')=='OFF':item['off']+=1
    return result


def check_conservation(before,after):
    from collections import Counter,defaultdict
    def weekly(rows):
        result=defaultdict(lambda:{'hours':0.,'off':0})
        for r in rows:
            week=pd.Timestamp(r['date']).date().isocalendar()[:2];key=(str(r['employee_id']),week);interval=bounds(r)
            if interval:result[key]['hours']+=(interval[1]-interval[0]).total_seconds()/3600
            if r.get('shift_code')=='OFF':result[key]['off']+=1
        return result
    old,new=weekly(before),weekly(after)
    for key in set(old)|set(new):
        a,b=old.get(key,{'hours':0.,'off':0}),new.get(key,{'hours':0.,'off':0})
        if a['off']!=b['off'] or abs(a['hours']-b['hours'])>1e-7:raise ValueError(f"Personel {key[0]} / hafta {key[1][1]}: haftalık OFF ve çalışma saati değişemez (OFF {a['off']} → {b['off']}, saat {a['hours']:g} → {b['hours']:g}).")
    durations={round((b[1]-b[0]).total_seconds()/3600,6) for r in before if (b:=bounds(r))}
    if len(durations)>1:raise ValueError('Değiştirilen çalışma vardiyalarının süreleri aynı olmalı; 7 saat ile 5 saat değiştirilemez.')
    def signatures(rows):return Counter((str(r['date']),r['shift_code'],r.get('start') or None,r.get('end') or None) for r in rows)
    if signatures(before)!=signatures(after):raise ValueError('Yeni vardiyalar aynı günün mevcut saatlerinden alınmalı. Serbest saat değişikliği vardiya değişimi değildir.')


def validate_changes(state,changes,kind,reason,current=None,submitting=False,report_authorized=False):
    role=(state.get('profile') or {}).get('position')
    if not (submitting and role=='agent'):require(state,'vardiya_degistir')
    if kind not in {'Vardiya değişimi','Erken çıkış','Geç giriş','Rapor','Yıllık izin','Mazeret izni'}:raise ValueError('Geçersiz değişiklik türü.')
    if not reason.strip():raise ValueError('Reason / değişiklik gerekçesi zorunlu.')
    if kind=='Rapor' and not (role=='wfm' and report_authorized):require(state,'rapor_gir')
    if not changes:raise ValueError('En az bir kayıt değiştirin.')
    current=current if current is not None else state.get('published_shift_plan',[])
    bykey={(str(r['employee_id']),str(r['date'])):r for r in current}
    keys=[(str(r['employee_id']),str(r['date'])) for r in changes]
    if len(keys)!=len(set(keys)):raise ValueError('Aynı sicil/tarih iki kez değiştirilemez.')
    people={str(e['employee_id']):e for e in state.get('employees_cache',[])}
    missing={key[0] for key in keys}-set(people)
    if missing and state.get('workspace_db_path'):
        from ortak.personel_deposu import list_people
        people.update({str(e['employee_id']):e for e in list_people(state,True) if str(e['employee_id']) in missing})
    profile=state.get('profile') or {};before=[];after=[]
    for key,new in zip(keys,changes):
        if key not in bykey:raise ValueError('Yalnızca yayınlanmış bir gün değiştirilebilir.')
        old=bykey[key];person=people.get(key[0],{})
        if role=='agent' and kind!='Vardiya değişimi' and str(profile.get('employee_id'))!=key[0]:raise ValueError('Yalnızca kendi vardiyan için talep oluşturabilirsin.')
        if profile.get('position')=='tl' and person.get('team_lead')!=profile.get('full_name'):raise ValueError('Yalnızca kendi ekibinin vardiyasını değiştirebilirsin.')
        row={**old,'shift_code':new.get('shift_code',old['shift_code']),'start':new.get('start'),'end':new.get('end')}
        from modules.vardiya_plani.vardiya_motoru import NON_WORK
        if row['shift_code'] in NON_WORK:row.update(start=None,end=None)
        if kind in {'Erken çıkış','Geç giriş'}:row['attendance_adjusted']=True
        interval=bounds(row);old_interval=bounds(old)
        if row['shift_code']=='RAPOR' and old.get('shift_code')!='RAPOR' and not(role=='wfm' and report_authorized):require(state,'rapor_gir')
        if kind=='Erken çıkış' and (not interval or not old_interval or interval[0]!=old_interval[0] or interval[1]>=old_interval[1]):raise ValueError('Erken çıkışta başlangıç korunmalı, bitiş erkene alınmalı.')
        if kind=='Geç giriş' and (not interval or not old_interval or interval[1]!=old_interval[1] or interval[0]<=old_interval[0]):raise ValueError('Geç girişte bitiş korunmalı, başlangıç ileri alınmalı.')
        expected={'Rapor':'RAPOR','Yıllık izin':'YILLIK_IZIN','Mazeret izni':'MAZERET_IZNI'}.get(kind)
        if expected and row['shift_code']!=expected:raise ValueError('Seçilen işlem türüyle statü uyuşmuyor.')
        before.append(old);after.append(row)
    if kind=='Vardiya değişimi':
        if len({(people.get(eid,{}).get('work_type'),people.get(eid,{}).get('language') or 'tr') for eid,_ in keys})!=1:raise ValueError('Farklı çalışma grupları veya farklı diller arasında vardiya değiştirilemez.')
        if len({eid for eid,_ in keys})!=2:raise ValueError('Vardiya değişimi iki personel arasında yapılmalı.')
        if role=='agent' and str(profile.get('employee_id')) not in {eid for eid,_ in keys}:raise ValueError('Değişimin tarafı olmalısın.')
        check_conservation(before,after)
    # The same engine checks rest, school, day limits and period budgets.
    if not state.get('shift_rules'):raise ValueError('Değişiklikten önce mesai kuralları tanımlanmalı.')
    if state.get('shift_rules'):
        check=dict(state);check['planning_languages']={'tr':True,'en':True,'ar':True};check['employees_cache']=list(people.values());dates=[pd.Timestamp(r['date']).date() for r in after]
        check['plan_ctx']={'start':min(dates),'end':max(dates)};check['draft_shift_plan']=[]
        from modules.vardiya_plani.planlama_verileri import collect_inputs
        staff,_,history,unavailable,issues=collect_inputs(check)
        staff=[e for e in staff if str(e['employee_id']) in {k[0] for k in keys}]
        relevant=[r for r in current if str(r['employee_id']) in {k[0] for k in keys} and (str(r['employee_id']),str(r['date'])) not in keys]
        # Attendance modifications may shorten a fixed-duration WORK shift.
        validation=[dict(r,shift_code='MESAI' if kind in {'Erken çıkış','Geç giriş'} and r['shift_code']=='WORK' else r['shift_code'],source='change_candidate') for r in after]
        demand=pd.DataFrame([{'Tarih':d.date(),'Slot':s,'Planlanan Agent':0} for d in pd.date_range(min(dates),max(dates)) for s in range(1,49)])
        result=generate_plan(staff,demand,state['shift_rules'],list(state['shift_rules']['work_type']),min(dates),max(dates),fixed=relevant+validation,history=relevant,unavailable=unavailable,auto_fill=False,hour_targets=state.get('group_hour_targets',[]))
        problems=[r for r in result['issues'] if r.get('source')=='change_candidate' and r.get('severity')!='warning']
        if problems:raise ValueError(' / '.join(dict.fromkeys(r['Sorun'] for r in problems)))
    return before,after


def apply_changes(state,changes,kind,reason,request_update=None,proposal_update=None):
    if (state.get("profile") or {}).get("position")!="wfm":raise ValueError("Yayınlanmış vardiya yalnızca Planlama onayıyla değiştirilebilir.")
    path=state['workspace_db_path'];init_governance(path)
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        stored=db.execute("SELECT payload FROM work_state WHERE key='published_shift_plan'").fetchone();current=loads(stored[0]) if stored else state.get('published_shift_plan',[])
        expected={(str(r['employee_id']),str(r['date'])):r for r in state.get('published_shift_plan',[])}
        actual={(str(r['employee_id']),str(r['date'])):r for r in current}
        for r in changes:
            key=(str(r['employee_id']),str(r['date']))
            if expected.get(key)!=actual.get(key):raise ValueError('Vardiya başka bir işlemle değişti. Ekranı yenileyin.')
        report_authorized=False
        if request_update:
            requested,version=request_update
            receipt=db.execute('SELECT version,payload FROM requests WHERE id=?',(requested['id'],)).fetchone()
            if not receipt or receipt['version']!=version:raise ValueError('Talep başka bir oturumda değişti.')
            original_request=loads(receipt['payload'])
            if original_request.get('proposed_before') and original_request['proposed_before']!=[actual.get((str(r['employee_id']),str(r['date']))) for r in changes]:raise ValueError('Vardiyalar talep sonrası değişmiş; yeni talep oluşturun.')
            report_authorized=kind=='Rapor' and original_request.get('submitted_by_role')=='tl'
        if proposal_update:
            proposal,version=proposal_update
            saved=db.execute('SELECT version,payload FROM shift_change_requests WHERE id=?',(proposal['id'],)).fetchone()
            if not saved or saved['version']!=version:raise ValueError('Değişim talebi başka bir oturumda değişti.')
            original=loads(saved['payload'])
            if original['status']!='Planlama onayı' or original['changes']!=changes or original['kind']!=kind or original['reason']!=reason:raise ValueError('Talep içeriği değişti; yeniden kontrol edin.')
            if original['before']!=[actual.get((str(r['employee_id']),str(r['date']))) for r in changes]:raise ValueError('Vardiyalar talep sonrası değişmiş; talebi yeniden oluşturun.')
            report_authorized=kind=='Rapor' and original['requester'].get('position')=='tl'
        before,after=validate_changes(state,changes,kind,reason,current,report_authorized=report_authorized)
        from ortak.talep_servisi import now
        ident='CHG-'+uuid4().hex[:12]
        people={str(e['employee_id']):e for e in state.get('employees_cache',[])}
        after=[dict(r,change_id=ident,change_type=kind,source='audited_change',sicil_no=people.get(str(r['employee_id']),{}).get('sicil_no',str(r['employee_id'])),username=people.get(str(r['employee_id']),{}).get('username','')) for r in after]
        for r in after:actual[(str(r['employee_id']),str(r['date']))]=r
        payload={'id':ident,'type':kind,'reason':reason.strip(),'actor':state['profile'].get('username'),
         'before':before,'after':after,'date':now()}
        db.execute('INSERT INTO shift_change_batches VALUES(?,?,?)',(ident,now(),dumps(payload)))
        append_audit(db,'Vardiya değişikliği',state['profile'],payload)
        db.execute("INSERT INTO work_state VALUES('published_shift_plan',?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload",(dumps(list(actual.values())),))
        if proposal_update:
            updated_proposal={**original,'status':'Uygulandı','change_id':ident,'decided_by':state['profile'].get('username'),'decided_at':now()}
            db.execute('UPDATE shift_change_requests SET version=version+1,payload=? WHERE id=?',(dumps(updated_proposal),original['id']))
        if request_update:
            from ortak.calisma_alani_deposu import put_request_in_transaction
            updated,version=request_update
            updated=dict(updated,change_id=ident,resolved_assignments=after)
            updated=put_request_in_transaction(db,updated,version)
    if request_update:
        state['trk_requests']=[r for r in state.get('trk_requests',[]) if r['id']!=updated['id']]+[updated]
    state['published_shift_plan']=list(actual.values());save_keys(state);return ident

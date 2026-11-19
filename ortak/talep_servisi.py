# Ortak / Talep Servisi — bu ekranın / servisin uygulama kodu.
"""One request, one stable ID, immutable attachments and an audited workflow."""
from copy import deepcopy
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd

from ortak.calisma_alani_deposu import get_requests, put_request, save_keys

TERMINAL = {"Uygulandı", "Reddedildi", "İptal Edildi", "Güncellendi"}
TYPE_LABELS = {"Gece Vardiyası Talebi":"Gece vardiyası", "Mesai Talebi":"Ek mesai", "Yıllık İzin Talebi":"Yıllık izin",
               "Genel Talep":"Genel talep", "Vardiya Değişim Talebi":"Vardiya değişimi", "Ders Programı":"Ders programı",
               "Sınav Takvimi":"Sınav bildirimi", "Bayram Talebi":"Bayram izni"}


def is_terminal(request):
    return request.get('queue') == 'Closed' or request.get('status') in TERMINAL


TYPE_LABELS.update({'Evlilik İzni Talebi':'Evlilik izni','Mazeret İzni Talebi':'Mazeret izni',
                    'Erken Çıkış Talebi':'Erken çıkış','Geç Giriş Talebi':'Geç giriş','Rapor Bildirimi':'Rapor','Ücretsiz İzin Talebi':'Ücretsiz izin','Doğum İzni Talebi':'Doğum izni'})


def now():
    return datetime.now(ZoneInfo("Europe/Istanbul")).isoformat(timespec="seconds")


def refresh(state):
    if state.get("workspace_db_path"):
        state["trk_requests"] = get_requests(state["workspace_db_path"])
    return state.get("trk_requests", [])


def visible(request, profile):
    role = profile.get("position")
    if role in {"wfm","manager","assistant_manager","moderator","planning_manager"}:
        return True
    if request.get("created_by") == profile.get("username"):
        return True
    if role == "tl":
        return str(profile.get("full_name", "")).casefold() in {str(x).casefold() for x in request.get("assigned_tls",[])}
    return any(str(t.get("employee_id")) == str(profile.get("employee_id")) for t in request.get("targets",[]))


def _store(state, request, expected=None):
    actor=(state.get("profile") or {}).get("_actor_username")
    if actor and request.get("events"):request["events"][-1]["real_actor"]=actor
    if state.get("workspace_db_path"):
        request = put_request(request, expected, state["workspace_db_path"])
    else:
        request = dict(request, version=1 if expected is None else expected+1)
    state["trk_requests"] = [r for r in state.get("trk_requests",[]) if r["id"] != request["id"]]+[request]
    return request


def create_request(state, payload, attachment=None):
    profile = state.get("profile") or {}
    if profile.get("position") != "agent" and not (profile.get("position")=="tl" and payload.get("type")=="Rapor Bildirimi"):
        raise ValueError("Personel talepleri agent hesabından oluşturulur.")
    from ortak.roller_ve_yetkiler import require
    require(state,"rapor_gir" if payload.get("type")=="Rapor Bildirimi" else "talep_ilet")
    request = deepcopy(payload)
    typ = request.get("type")
    if typ=="Rapor Bildirimi" and profile.get("position")!="tl":raise ValueError("Rapor girişini yalnızca Takım Lideri yapabilir.")
    if typ=='Gece Vardiyası Talebi':
        from ortak.kesin_kayit_deposu import night_capacity_check
        night_capacity_check(state,profile.get('employee_id'),request.get('start_date'),request.get('end_date') or request.get('start_date'))
    if typ not in TYPE_LABELS:
        raise ValueError("Geçerli bir talep türü seçin.")
    if typ != "Ders Programı":
        start = pd.to_datetime(request.get("start_date"), errors="coerce")
        end = pd.to_datetime(request.get("end_date") or request.get("start_date"), errors="coerce")
        if pd.isna(start) or pd.isna(end) or start > end or (end-start).days > 366:
            raise ValueError("Geçerli bir başlangıç/bitiş tarihi girin (en fazla 367 gün).")
        request.update(start_date=str(start.date()), end_date=str(end.date()))
    if typ in {"Mesai Talebi", "Gece Vardiyası Talebi"}:
        from modules.vardiya_plani.vardiya_motoru import bounds
        bounds({"date":request['start_date'],"shift_code":"WORK","start":request.get("overtime_start"),"end":request.get("overtime_end")})
    if typ=="Vardiya Değişim Talebi" and not str(request.get("note","")).strip():raise ValueError("Vardiya değişimi gerekçesi gerekli.")
    if typ=="Vardiya Değişim Talebi" and any(t.get("position","agent")!="agent" for t in request.get("targets",[])):raise ValueError("Değişim karşı tarafı Müşteri Temsilcisi olmalı.")
    if typ == "Vardiya Değişim Talebi" and not request.get("targets"):
        raise ValueError("Vardiya değişimi için karşı personeli seçin.")
    if typ == "Genel Talep" and not str(request.get("note", "")).strip():
        raise ValueError("Genel talep için açıklama yazın.")
    tls = list(dict.fromkeys([profile.get("team_lead")]+[t.get("team_lead") for t in request.get("targets",[])]))
    tls = [profile.get('full_name')] if typ=='Rapor Bildirimi' and profile.get('position')=='tl' else [x for x in tls if x]
    if not tls:
        raise ValueError("Personelin takım lideri tanımlı değil.")
    request.update(id="REQ-"+uuid4().hex[:12].upper(),created_at=now(),created_by=profile["username"],
                   created_by_name=profile.get("full_name",profile["username"]),employee_id=profile.get("employee_id"),
                   team_lead=profile.get("team_lead"),location=profile.get("location"),work_type=profile.get("work_type"),
                   status="Beklemede",queue="TL_SWAP" if typ=="Vardiya Değişim Talebi" else "TL",
                   assigned_tls=tls,tl_approvals=[],source=payload.get("generated_from") or "personel",
                   attachment=deepcopy(attachment),events=[],version=1)
    if typ=='Rapor Bildirimi' and profile.get('position')=='tl':
        target=next((e for e in state.get('employees_cache',[]) if str(e['employee_id'])==str(payload.get('report_employee_id')) and e.get('team_lead')==profile.get('full_name')),None)
        if not target:raise ValueError('Rapor için kendi ekibinden bir Müşteri Temsilcisi seçin.')
        request.update(employee_id=target['employee_id'],created_by=target.get('username',str(target['employee_id'])),created_by_name=target['full_name'],submitted_by=profile['username'],submitted_by_role='tl',status='Planlamaya İletildi',queue='WFM')
    if typ=='Vardiya Değişim Talebi':
        from ortak.talep_yerlestirme import resolve_swap
        request['proposed_assignments']=resolve_swap(state,request)
    if typ in {'Erken Çıkış Talebi','Geç Giriş Talebi'}:
        records=[r for r in state.get('published_shift_plan',[]) if str(r['employee_id'])==str(profile['employee_id']) and request['start_date']<=r['date']<=request['end_date']]
        if not records:raise ValueError('Bu tarihlerde yayınlanmış vardiyan yok.')
        from modules.vardiya_plani.vardiya_motoru import bounds
        if any(not bounds(r) for r in records):raise ValueError('Erken/geç giriş talebi yalnızca çalışma gününe girilebilir.')
        request['proposed_assignments']=[dict(r,**({'end':request.get('overtime_end')} if typ=='Erken Çıkış Talebi' else {'start':request.get('overtime_start')})) for r in records]
    if typ=='Rapor Bildirimi':
        existing=[r for r in state.get('published_shift_plan',[]) if str(r['employee_id'])==str(request['employee_id']) and request['start_date']<=r['date']<=request['end_date']]
        if existing:request['proposed_assignments']=[dict(r,shift_code='RAPOR',start=None,end=None) for r in existing]
    if request.get('proposed_assignments'):
        proposed=request['proposed_assignments'];bykey={(str(r['employee_id']),str(r['date'])):r for key in ('draft_shift_plan','published_shift_plan') for r in state.get(key,[])}
        request['proposed_before']=[deepcopy(bykey[(str(r['employee_id']),str(r['date']))]) for r in proposed]
        if all(r in state.get('published_shift_plan',[]) for r in request['proposed_before']):
            from ortak.vardiya_degisimleri import validate_changes
            validate_changes(state,proposed,{'Vardiya Değişim Talebi':'Vardiya değişimi','Erken Çıkış Talebi':'Erken çıkış','Geç Giriş Talebi':'Geç giriş','Rapor Bildirimi':'Rapor'}[typ],request.get('note',''),submitting=True)
    request["events"].append({"at":now(),"actor":profile["username"],"actor_name":profile.get("full_name",profile["username"]),
                              "action":"Talep oluşturuldu","from":"—","to":"Takım lideri değerlendirmesi","note":request.get("note","")})
    if typ=="Gece Vardiyası Talebi" and state.get("workspace_db_path"):
        from ortak.kesin_kayit_deposu import store_night_request
        return store_night_request(state,request)
    return _store(state,request)


def act(state, request, action, note=""):
    if action in {"takeover","simulate","cancel_planning"}:
        from ortak.talep_simulasyonu import decide
        return decide(state,request,action,note)
    profile = state.get("profile") or {}
    if not visible(request,profile):
        raise ValueError("Bu talepte işlem yetkiniz yok.")
    if is_terminal(request):
        raise ValueError("Sonuçlanan talep tekrar işlenemez.")
    role = profile.get("position")
    queue = request.get("queue")
    from ortak.planlama import REQUEST_CODES
    if action=="apply" and request.get("type") in REQUEST_CODES and (state.get("shift_rules") or {}).get("publication_approvals",{}).get("enabled"):
        from ortak.talep_simulasyonu import decide
        return decide(state,request,"simulate",note)
    if action=="apply" and request.get("type") in {"Vardiya Değişim Talebi","Erken Çıkış Talebi","Geç Giriş Talebi","Rapor Bildirimi"} and role!="wfm":raise ValueError("Vardiya değişimleri için son onayı yalnızca Planlama verir.")
    if action=='apply' and request.get('proposed_before'):
        sources={(str(r['employee_id']),str(r['date'])):r for key in ('draft_shift_plan','published_shift_plan') for r in state.get(key,[])}
        if any(sources.get((str(r['employee_id']),str(r['date'])))!=r for r in request['proposed_before']):raise ValueError('Vardiyalar talep sonrası değişmiş; yeni talep oluşturun.')
    new = deepcopy(request)
    if action == "cancel":
        if request.get("created_by") != profile.get("username"):
            raise ValueError("Yalnızca kendi talebinizi geri çekebilirsiniz.")
        status, new_queue, label = "İptal Edildi","Closed","Talep geri çekildi"
    elif action in {"forward","reject"} and role == "tl" and queue in {"TL","TL_SWAP"}:
        if str(profile.get("full_name", "")).casefold() not in {str(x).casefold() for x in request.get("assigned_tls",[])}:
            raise ValueError("Talep size atanmış değil.")
        if action == "reject":
            if not note.strip():
                raise ValueError("Ret gerekçesi yazın.")
            status,new_queue,label = "Reddedildi","Closed","Takım lideri reddetti"
        else:
            if profile.get("full_name") in request.get("tl_approvals",[]):
                raise ValueError("Bu talep için takım lideri onayınız zaten kayıtlı.")
            approvals = list(dict.fromkeys(request.get("tl_approvals",[])+[profile.get("full_name")]))
            new["tl_approvals"] = approvals
            complete = set(request.get("assigned_tls",[])) <= set(approvals)
            status,new_queue,label = (("Planlamaya İletildi","WFM","Takım lideri onayladı ve planlamaya iletti") if complete
                                       else ("Diğer TL Onayı Bekliyor","TL_SWAP","Takım lideri onayladı; diğer lider bekleniyor"))
    elif action in {"apply","reject"} and role in {"wfm","manager","assistant_manager","moderator","planning_manager"} and queue=="WFM":
        if action == "reject" and not note.strip():
            raise ValueError("Ret gerekçesi yazın.")
        if action=="apply" and request.get("type")=="Vardiya Değişim Talebi":
            from ortak.talep_yerlestirme import resolve_swap
            new["resolved_assignments"]=resolve_swap(state,request)
        if action=="apply" and request.get("type") in {"Erken Çıkış Talebi","Geç Giriş Talebi","Rapor Bildirimi"} and request.get("proposed_assignments"):new["resolved_assignments"]=request["proposed_assignments"]
        status,new_queue,label = (("Onaylandı","Closed","Planlama onayladı; plana alınacak") if action=="apply"
                                  else ("Reddedildi","Closed","Planlama reddetti"))
    else:
        raise ValueError("Bu aşamada bu işlem yapılamaz.")
    new.update(status=status,queue=new_queue,last_action=label,last_action_by=profile.get("username"),
               last_action_at=now(),decision_note=note.strip())
    new.setdefault("events",[]).append({"at":now(),"actor":profile.get("username"),"actor_name":profile.get("full_name",profile.get("username")),
                                        "action":label,"from":request.get("status"),"to":status,"note":note.strip()})
    if action=='apply' and new.get('resolved_assignments') and state.get('workspace_db_path'):
        keys={(str(r['employee_id']),str(r['date'])) for r in state.get('published_shift_plan',[])}
        if all((str(r['employee_id']),str(r['date'])) in keys for r in new['resolved_assignments']):
            from ortak.vardiya_degisimleri import apply_changes
            new['status']='Uygulandı';new['last_action']='Planlama onayladı; yayınlanan vardiyaya uygulandı'
            new['events'][-1].update(to='Uygulandı',action=new['last_action'])
            apply_changes(state,new['resolved_assignments'],{'Vardiya Değişim Talebi':'Vardiya değişimi','Erken Çıkış Talebi':'Erken çıkış','Geç Giriş Talebi':'Geç giriş','Rapor Bildirimi':'Rapor'}[request['type']],request['note'],request_update=(new,request.get('version',1)))
            return next(r for r in state['trk_requests'] if r['id']==new['id'])
    if action=='apply' and request.get('type')=='Gece Vardiyası Talebi' and state.get('workspace_db_path'):
        from ortak.calisma_alani_deposu import connect,loads,put_request_in_transaction
        from ortak.kesin_kayit_deposu import night_capacity_check
        with connect(state['workspace_db_path']) as db:
            db.execute('BEGIN IMMEDIATE');check=dict(state)
            for field in ('shift_rules','fixed_shift_records','published_shift_plan'):
                stored=db.execute('SELECT payload FROM work_state WHERE key=?',(field,)).fetchone()
                if stored:check[field]=loads(stored[0])
            check['trk_requests']=[loads(r[0]) for r in db.execute('SELECT payload FROM requests')]
            night_capacity_check(check,request['employee_id'],request['start_date'],request['end_date'],exclude_request=request['id'])
            saved=put_request_in_transaction(db,new,request.get('version',1))
        state['trk_requests']=[r for r in state.get('trk_requests',[]) if r['id']!=saved['id']]+[saved]
        return saved
    return _store(state,new,request.get("version",1))


def supersede_generated(state, source, ref):
    for req in list(refresh(state)):
        if req.get("generated_from") == source and req.get("generated_ref") == ref and req.get("status") != "Güncellendi":
            if req.get("created_by") != (state.get("profile") or {}).get("username"):
                continue
            new = deepcopy(req)
            new.update(status="Güncellendi",queue="Closed")
            new.setdefault("events",[]).append({"at":now(),"actor":req["created_by"],"actor_name":req.get("created_by_name",req["created_by"]),
                                                "action":"Yeni bildirimle değiştirildi","from":req.get("status"),"to":"Güncellendi","note":"Eski bildirim geçmişte korunur."})
            _store(state,new,req.get("version",1))
    save_keys(state)

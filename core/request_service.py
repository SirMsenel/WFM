"""One request, one stable ID, immutable attachments and an audited workflow."""
from copy import deepcopy
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd

from core.workspace_store import get_requests, put_request, save_keys

TERMINAL = {"Uygulandı", "Reddedildi", "İptal Edildi", "Güncellendi"}
TYPE_LABELS = {"Gece Vardiyası Talebi":"Gece vardiyası", "Mesai Talebi":"Ek mesai", "Yıllık İzin Talebi":"Yıllık izin",
               "Genel Talep":"Genel talep", "Vardiya Değişim Talebi":"Vardiya değişimi", "Ders Programı":"Ders programı",
               "Sınav Takvimi":"Sınav bildirimi", "Bayram Talebi":"Bayram izni"}


def is_terminal(request):
    return request.get('queue') == 'Closed' or request.get('status') in TERMINAL


TYPE_LABELS.update({'Evlilik İzni Talebi':'Evlilik izni','Mazeret İzni Talebi':'Mazeret izni',
                    'Rapor Bildirimi':'Rapor','Ücretsiz İzin Talebi':'Ücretsiz izin','Doğum İzni Talebi':'Doğum izni'})


def now():
    return datetime.now(ZoneInfo("Europe/Istanbul")).isoformat(timespec="seconds")


def refresh(state):
    if state.get("workspace_db_path"):
        state["trk_requests"] = get_requests(state["workspace_db_path"])
    return state.get("trk_requests", [])


def visible(request, profile):
    role = profile.get("position")
    if role in {"wfm","manager","moderator"}:
        return True
    if request.get("created_by") == profile.get("username"):
        return True
    if role == "tl":
        return str(profile.get("full_name", "")).casefold() in {str(x).casefold() for x in request.get("assigned_tls",[])}
    return any(str(t.get("employee_id")) == str(profile.get("employee_id")) for t in request.get("targets",[]))


def _store(state, request, expected=None):
    if state.get("workspace_db_path"):
        request = put_request(request, expected, state["workspace_db_path"])
    else:
        request = dict(request, version=1 if expected is None else expected+1)
    state["trk_requests"] = [r for r in state.get("trk_requests",[]) if r["id"] != request["id"]]+[request]
    return request


def create_request(state, payload, attachment=None):
    profile = state.get("profile") or {}
    if profile.get("position") != "agent":
        raise ValueError("Personel talepleri agent hesabından oluşturulur.")
    request = deepcopy(payload)
    typ = request.get("type")
    if typ not in TYPE_LABELS:
        raise ValueError("Geçerli bir talep türü seçin.")
    if typ != "Ders Programı":
        start = pd.to_datetime(request.get("start_date"), errors="coerce")
        end = pd.to_datetime(request.get("end_date") or request.get("start_date"), errors="coerce")
        if pd.isna(start) or pd.isna(end) or start > end or (end-start).days > 366:
            raise ValueError("Geçerli bir başlangıç/bitiş tarihi girin (en fazla 367 gün).")
        request.update(start_date=str(start.date()), end_date=str(end.date()))
    if typ in {"Mesai Talebi", "Gece Vardiyası Talebi"}:
        from modules.shift_planing.engine import bounds
        bounds({"date":request['start_date'],"shift_code":"WORK","start":request.get("overtime_start"),"end":request.get("overtime_end")})
    if typ == "Vardiya Değişim Talebi" and not request.get("targets"):
        raise ValueError("Vardiya değişimi için karşı personeli seçin.")
    if typ == "Genel Talep" and not str(request.get("note", "")).strip():
        raise ValueError("Genel talep için açıklama yazın.")
    tls = list(dict.fromkeys([profile.get("team_lead")]+[t.get("team_lead") for t in request.get("targets",[])]))
    tls = [x for x in tls if x]
    if not tls:
        raise ValueError("Personelin takım lideri tanımlı değil.")
    request.update(id="REQ-"+uuid4().hex[:12].upper(),created_at=now(),created_by=profile["username"],
                   created_by_name=profile.get("full_name",profile["username"]),employee_id=profile.get("employee_id"),
                   team_lead=profile.get("team_lead"),location=profile.get("location"),work_type=profile.get("work_type"),
                   status="Beklemede",queue="TL_SWAP" if typ=="Vardiya Değişim Talebi" else "TL",
                   assigned_tls=tls,tl_approvals=[],source=payload.get("generated_from") or "personel",
                   attachment=deepcopy(attachment),events=[],version=1)
    request["events"].append({"at":now(),"actor":profile["username"],"actor_name":profile.get("full_name",profile["username"]),
                              "action":"Talep oluşturuldu","from":"—","to":"Takım lideri değerlendirmesi","note":request.get("note","")})
    return _store(state,request)


def act(state, request, action, note=""):
    profile = state.get("profile") or {}
    if not visible(request,profile):
        raise ValueError("Bu talepte işlem yetkiniz yok.")
    if is_terminal(request):
        raise ValueError("Sonuçlanan talep tekrar işlenemez.")
    role = profile.get("position")
    queue = request.get("queue")
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
    elif action in {"apply","reject"} and role in {"wfm","manager","moderator"} and queue=="WFM":
        if action == "reject" and not note.strip():
            raise ValueError("Ret gerekçesi yazın.")
        status,new_queue,label = (("Onaylandı","Closed","Planlama onayladı; plana alınacak") if action=="apply"
                                  else ("Reddedildi","Closed","Planlama reddetti"))
    else:
        raise ValueError("Bu aşamada bu işlem yapılamaz.")
    new.update(status=status,queue=new_queue,last_action=label,last_action_by=profile.get("username"),
               last_action_at=now(),decision_note=note.strip())
    new.setdefault("events",[]).append({"at":now(),"actor":profile.get("username"),"actor_name":profile.get("full_name",profile.get("username")),
                                        "action":label,"from":request.get("status"),"to":status,"note":note.strip()})
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

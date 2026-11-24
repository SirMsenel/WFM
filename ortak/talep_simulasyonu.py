"""Planlama üstlenme, erteleme, simüle etme ve yayın anında kesin karar."""
from copy import deepcopy
import pandas as pd
from ortak.talep_servisi import _store,now


def decide(state,req,action,note=''):
    profile=state.get('profile') or {}
    if profile.get('position')!='wfm':raise ValueError('Bu kararları Planlama verir.')
    if action not in {'takeover','simulate','cancel_planning'}:raise ValueError('Geçersiz işlem.')
    new=deepcopy(req)
    if req.get('queue')=='Closed':raise ValueError('Talep sonuçlanmış. Yayınlanan izin/vardiya için Değişim Alanı üzerinden gerekçeli düzenleme yapın.')
    if action in {'takeover','cancel_planning'} and not note.strip():raise ValueError('İşlem gerekçesi zorunlu.')
    if action=='takeover':new.update(queue='WFM',status='Planlama üstlendi',claimed_by=profile['username'])
    elif action=='simulate':
        from ortak.planlama import REQUEST_CODES
        if req['type'] not in REQUEST_CODES:raise ValueError('Bu talep, kendi onay ekranından sonuçlandırılır.')
        new.update(queue='SIMULATION',status='Simülasyonda',simulated_by=profile['username'])
    else:new.update(queue='Closed',status='İptal Edildi',decision_note=note)
    new.setdefault('events',[]).append({'at':now(),'actor':profile['username'],'action':{'takeover':'Planlama üstlendi','simulate':'Taslağa simüle edildi; yayın onayı bekleniyor','cancel_planning':'Planlama talebi iptal etti'}[action],'from':req.get('status'),'to':new['status'],'note':note})
    return _store(state,new,req.get('version',1))


def _publication_decision(req,bykey,identities,start,end,actor):
    from ortak.planlama import REQUEST_CODES
    if req.get('queue')!='SIMULATION':
        return None
    eid=identities.get(str(req.get('employee_id'))) or identities.get(str(req.get('created_by')))
    code=REQUEST_CODES.get(req.get('type'))
    first=req.get('start_date')
    if not eid or not code or not first:
        return None
    last=str(req.get('end_date') or first)
    all_days=[str(day.date()) for day in pd.date_range(first,last)]
    relevant=[day for day in all_days if str(start)<=day<=str(end)]
    if not relevant:
        return None
    matched=set(req.get('committed_dates',[]))
    for day in relevant:
        row=bykey.get((eid,day))
        fits=bool(row and row.get('shift_code')==code)
        if fits and code in {'GECE','MESAI'}:
            for field in ('start','end'):
                requested=req.get(field) or req.get(field+'_time') or req.get('overtime_'+field)
                if requested and str(row.get(field))[:5]!=str(requested)[:5]:
                    fits=False
        if fits:matched.add(day)
        else:matched.discard(day)
    complete=all(day in matched for day in all_days)
    decision=deepcopy(req)
    decision.update(status='Onaylandı' if complete else 'Reddedildi',queue='Closed',committed_dates=sorted(matched))
    decision.setdefault('events',[]).append({'at':now(),'actor':actor,'action':'Yayınla birlikte kesinleşti' if complete else 'Yayın planına uygulanmadı','from':req.get('status'),'to':decision['status'],'note':f'{start} – {end} · uygulanan {len(matched.intersection(all_days))}/{len(all_days)} gün'})
    return decision


def _publication_people(rows,staff):
    identities={str(r['employee_id']):str(r['employee_id']) for r in [*rows,*staff]}
    identities.update({str(p['username']):str(p['employee_id']) for p in staff if p.get('username')})
    return identities


def finalize(db,rows,start,end,actor,staff=()):
    from ortak.calisma_alani_deposu import loads,put_request_in_transaction
    bykey={(str(r['employee_id']),str(r['date'])):r for r in rows}
    identities=_publication_people(rows,staff)
    for record in db.execute('SELECT payload,version FROM requests').fetchall():
        decision=_publication_decision(loads(record[0]),bykey,identities,start,end,actor)
        if decision:put_request_in_transaction(db,decision,record[1])


def finalize_in_memory(state,rows,start,end,actor,staff=()):
    bykey={(str(r['employee_id']),str(r['date'])):r for r in rows}
    identities=_publication_people(rows,staff)
    state['trk_requests']=[_publication_decision(req,bykey,identities,start,end,actor) or req for req in state.get('trk_requests',[])]

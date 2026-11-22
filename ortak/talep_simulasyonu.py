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


def finalize(db,rows,start,end,actor):
    from ortak.calisma_alani_deposu import loads,put_request_in_transaction
    from ortak.planlama import REQUEST_CODES
    bykey={(str(r['employee_id']),r['date']):r for r in rows}
    for record in db.execute('SELECT payload,version FROM requests').fetchall():
        req=loads(record[0])
        if req.get('queue')!='SIMULATION':continue
        code=REQUEST_CODES.get(req['type']);eid=str(req.get('employee_id'));a=req.get('start_date');b=req.get('end_date') or a
        if not code or not a:continue
        overlap_start=max(str(start),a);overlap_end=min(str(end),b)
        if overlap_start>overlap_end:continue
        matched=set(req.get('committed_dates',[]))
        for day in pd.date_range(overlap_start,overlap_end):
            text=str(day.date());row=bykey.get((eid,text))
            if row and row['shift_code']==code:matched.add(text)
        new=deepcopy(req);new['committed_dates']=sorted(matched)
        complete=all(str(d.date()) in matched for d in pd.date_range(a,b))
        new.update(status='Onaylandı' if complete else 'Reddedildi',queue='Closed')
        applied=len([d for d in pd.date_range(a,b) if str(d.date()) in matched])
        new.setdefault('events',[]).append({'at':now(),'actor':actor,'action':'Yayınla birlikte kesinleşti' if complete else 'Yayın planına uygulanmadı','from':req['status'],'to':new['status'],'note':f'{start} – {end} · uygulanan {applied}/{len(pd.date_range(a,b))} gün'})
        put_request_in_transaction(db,new,record[1])


def finalize_in_memory(state,rows,start,end,actor):
    """Veritabanı kullanılmayan demo oturumunda aynı kesinleştirmeyi uygula."""
    from ortak.planlama import REQUEST_CODES
    bykey={(str(r['employee_id']),str(r['date'])):r for r in rows};updated=[]
    for req in state.get('trk_requests',[]):
        if req.get('queue')!='SIMULATION':updated.append(req);continue
        code=REQUEST_CODES.get(req.get('type'));a=req.get('start_date');b=req.get('end_date') or a
        if not code or not a or max(str(start),a)>min(str(end),b):updated.append(req);continue
        matched=set(req.get('committed_dates',[]))
        for day in pd.date_range(max(str(start),a),min(str(end),b)):
            text=str(day.date());row=bykey.get((str(req.get('employee_id')),text))
            if row and row.get('shift_code')==code:matched.add(text)
        new=deepcopy(req);new['committed_dates']=sorted(matched);all_days=[str(d.date()) for d in pd.date_range(a,b)];complete=all(day in matched for day in all_days)
        new.update(status='Onaylandı' if complete else 'Reddedildi',queue='Closed')
        new.setdefault('events',[]).append({'at':now(),'actor':actor,'action':'Yayınla birlikte kesinleşti' if complete else 'Yayın planına uygulanmadı','from':req.get('status'),'to':new['status'],'note':f'{start} – {end} · uygulanan {sum(day in matched for day in all_days)}/{len(all_days)} gün'})
        updated.append(new)
    state['trk_requests']=updated

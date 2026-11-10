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
        matched=set(req.get('committed_dates',[]))
        for day in pd.date_range(max(str(start),a),min(str(end),b)):
            text=str(day.date());row=bykey.get((eid,text))
            if row and row['shift_code']==code:matched.add(text)
        if matched==set(req.get('committed_dates',[])):continue
        new=deepcopy(req);new['committed_dates']=sorted(matched)
        complete=all(str(d.date()) in matched for d in pd.date_range(a,b))
        new.update(status='Onaylandı' if complete else 'Kısmen planlandı',queue='Closed' if complete else 'SIMULATION')
        new.setdefault('events',[]).append({'at':now(),'actor':actor,'action':'Yayınla birlikte kesinleşti' if complete else 'Dönemin bir bölümü yayınlandı','from':req['status'],'to':new['status'],'note':f'{start} – {end}'})
        put_request_in_transaction(db,new,record[1])

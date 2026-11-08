# Ortak / Talep Yerlestirme — bu ekranın / servisin uygulama kodu.
"""Freeze both sides of an approved swap so later edits cannot change its meaning."""
from copy import deepcopy
import pandas as pd


def resolve_swap(state,request):
    targets=request.get('targets') or []
    if len(targets)!=1:raise ValueError('Vardiya değişimi için tam bir karşı personel gerekli.')
    own=str(request.get('employee_id') or '')
    if not own:
        own=next((str(e['employee_id']) for e in state.get('employees_cache',[]) if e.get('username')==request.get('created_by')),'')
    other=str(targets[0].get('employee_id') or '')
    if not own or not other or own==other:raise ValueError('Vardiya değişimindeki iki personel kimliği geçerli olmalı.')
    rows={(str(r['employee_id']),str(r['date'])):r for key in ('draft_shift_plan','published_shift_plan') for r in state.get(key,[])}
    output=[]
    dates=pd.to_datetime(request.get('swap_dates') or list(pd.date_range(request['start_date'],request.get('end_date') or request['start_date'])))
    before=[]
    for day in dates:
        key=str(day.date())
        if (own,key) not in rows or (other,key) not in rows:raise ValueError(f'{key}: her iki personelin vardiyası bulunmadan değişim onaylanamaz.')
        if any(rows[(person,key)]['shift_code'] not in {'OFF','WORK','MESAI','GECE'} for person in (own,other)):raise ValueError('İzin/rapor günleri vardiya değişim talebiyle taşınamaz.')
        before.extend([rows[(own,key)],rows[(other,key)]])
        for person,source in [(own,rows[(other,key)]),(other,rows[(own,key)])]:
            output.append({'employee_id':person,'date':key,'shift_code':source['shift_code'],'start':source.get('start'),'end':source.get('end'),'note':'Onaylı vardiya değişimi '+request['id']})
    from ortak.vardiya_degisimleri import check_conservation
    check_conservation(before,output)
    return output

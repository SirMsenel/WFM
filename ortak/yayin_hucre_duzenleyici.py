"""Yayın takvimindeki hücre metnini denetlenebilir vardiya değişimine çevirir."""
import re
from datetime import time
from ortak.planlama import SHIFT_LABELS

def parse_cell(value,old):
    text=str(value or '').strip()
    labels={str(v).casefold():k for k,v in SHIFT_LABELS.items()}
    code=labels.get(text.casefold(),text.upper())
    if code in SHIFT_LABELS and code not in {'MESAI','GECE'}:
        return {**old,'shift_code':code,'start':None,'end':None}
    m=re.fullmatch(r'(Gece\s+)?(\d{2}:\d{2})\s*[-–→]\s*(\d{2}:\d{2})',text,re.I)
    if not m:raise ValueError('Hücreye 08:00–17:00, Gece 00:00–08:00 veya geçerli izin/OFF adı girin.')
    for clock in m.group(2,3):time.fromisoformat(clock)
    if m.group(2)==m.group(3):raise ValueError('Başlangıç ve bitiş aynı olamaz.')
    return {**old,'shift_code':'GECE' if m.group(1) else 'MESAI','start':m.group(2),'end':m.group(3)}


def changes_from_grid(original,edited,people,batch):
    import pandas as pd
    if len(original)!=len(edited):raise ValueError('Personel satırları değiştirilemez.')
    columns=list(original.columns)[1:];days=list(pd.date_range(batch['start'],batch['end']))
    before={(str(r['employee_id']),str(r['date'])):r for r in batch['rows']};changes=[]
    for i,person in enumerate(people):
        for col,day in zip(columns,days):
            if str(original.iloc[i][col])==str(edited.iloc[i][col]):continue
            key=(str(person['employee_id']),str(day.date()));old=before.get(key)
            if not old:raise ValueError('Bu personel/gün için yayınlanmış kayıt yok.')
            parsed=parse_cell(edited.iloc[i][col],old);changes.append({k:parsed.get(k) for k in ('employee_id','date','shift_code','start','end')})
    return changes

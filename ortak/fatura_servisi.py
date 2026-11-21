"""Şirket/grup sözleşme parametreleri ve vardiya statüsünden aylık mutabakat."""
import calendar
import hashlib
import math
import pandas as pd

from ortak.calisma_alani_deposu import connect,dumps,loads,init_db

STATUS_LABELS={
    'WORK':'Çalışma','MESAI':'Ek mesai','GECE':'Gece','OFF':'OFF','YILLIK_IZIN':'Yıllık izin',
    'RAPOR':'Rapor','UCRETSIZ_IZIN':'Ücretsiz izin','MAZERET_IZNI':'Mazeret izni',
    'EVLILIK_IZNI':'Evlilik izni','DOGUM_IZNI':'Doğum izni','SINAV':'Sınav','DERS':'Ders',
}
ROLES={'wfm','planning_manager','manager','assistant_manager','moderator'}


def init(path):
    init_db(path)
    with connect(path) as db:db.execute('CREATE TABLE IF NOT EXISTS billing_profiles(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')


def profiles(state):
    path=state.get('workspace_db_path')
    if not path:return []
    init(path)
    with connect(path) as db:return [dict(loads(row['payload']),id=row['id']) for row in db.execute('SELECT id,payload FROM billing_profiles ORDER BY id')]


def save_profile(state,value):
    if (state.get('profile') or {}).get('position') not in ROLES:raise ValueError('Fatura parametrelerini yalnızca planlama ve yönetim rolleri düzenleyebilir.')
    company=str(value.get('company','')).strip();group=str(value.get('group','')).strip();method=value.get('method');amount=float(value.get('amount',0))
    if not company or not group or method not in {'Günlük','Aylık'} or not math.isfinite(amount) or amount<0:raise ValueError('Şirket, kaynak grubu, yöntem ve pozitif ücret gereklidir.')
    statuses=sorted(set(value.get('paid_statuses',[])))
    if not set(statuses)<=set(STATUS_LABELS):raise ValueError('Bilinmeyen ödeme statüsü seçildi.')
    taxes=[]
    for row in value.get('taxes',[]):
        if not str(row.get('name','')).strip():continue
        rate=float(row.get('rate',0))
        if not math.isfinite(rate) or not 0<=rate<=100:raise ValueError('Vergi oranı %0–100 arasında olmalı.')
        if row.get('direction') not in {'Artı','Eksi'} or row.get('application') not in {'Ana hesaba ekle','Vergiden düş'}:raise ValueError('Vergi yönü ve uygulama biçimi seçilmelidir.')
        taxes.append({'name':str(row['name']).strip(),'rate':rate,'direction':row['direction'],'application':row['application']})
    ident=hashlib.sha1((company+'|'+group).encode()).hexdigest()[:16]
    payload={'company':company,'group':group,'method':method,'amount':amount,'paid_statuses':statuses,'coefficient_basis':value.get('coefficient_basis','Takvim günü'),'taxes':taxes}
    init(state['workspace_db_path'])
    with connect(state['workspace_db_path']) as db:db.execute('INSERT INTO billing_profiles VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(ident,dumps(payload)))
    return ident


def delete_profile(state,ident):
    if (state.get('profile') or {}).get('position') not in ROLES:raise ValueError('Bu işlem için yetkiniz yok.')
    init(state['workspace_db_path'])
    with connect(state['workspace_db_path']) as db:db.execute('DELETE FROM billing_profiles WHERE id=?',(ident,))


def _tax(base,taxes):
    total=0.;parts=[]
    for tax in taxes:
        raw=base*float(tax['rate'])/100
        value=(-abs(raw) if tax['application']=='Vergiden düş' else raw*(1 if tax['direction']=='Artı' else -1))
        total+=value;parts.append((tax['name'],value))
    return total,parts


def calculate(state,month):
    month=pd.Timestamp(month).replace(day=1).normalize();end=month+pd.offsets.MonthEnd();days=end.day
    from ortak.personel import WORK_LABELS
    from ortak.personel_deposu import list_people
    people=[p for p in list_people(state,True) if p.get('position')=='agent']
    from ortak.sabit_demo import history_rows
    roster=history_rows(state,month.date(),end.date());by_person={}
    for row in roster:by_person.setdefault(str(row['employee_id']),[]).append(row)
    output=[]
    for contract in profiles(state):
        matching=[p for p in people if str(p.get('company') or 'Belirtilmemiş')==contract['company'] and p.get('work_type')==contract['group']]
        divisor=30 if contract.get('coefficient_basis')=='30 gün sabit' else days
        for person in matching:
            rows=by_person.get(str(person['employee_id']),[]);counts={code:0 for code in STATUS_LABELS};hours=0.
            from modules.vardiya_plani.vardiya_motoru import bounds
            for row in rows:
                code=row.get('shift_code','WORK');counts[code]=counts.get(code,0)+1
                span=bounds(row)
                if span:hours+=(span[1]-span[0]).total_seconds()/3600
            paid_days=sum(counts.get(code,0) for code in contract['paid_statuses']);coefficient=min(1.,paid_days/divisor) if contract['method']=='Aylık' else float(paid_days)
            base=float(contract['amount'])*coefficient;tax,parts=_tax(base,contract.get('taxes',[]));net=base+tax
            output.append({'Sicil no':person.get('sicil_no',person['employee_id']),'Personel':person['full_name'],'Şirket':contract['company'],'Kaynak':WORK_LABELS.get(contract['group'],contract['group']),'group':contract['group'],'Yöntem':contract['method'],'Birim ücret':contract['amount'],'Ücretli gün':paid_days,'Katsayı':coefficient,'Çalışma saati':hours,'Ana tutar':base,'Vergi/ek kesinti':tax,'Net ödeme':net,'Vergi detayı':', '.join(f'{name}: {value:+.2f}' for name,value in parts) or '—',**{STATUS_LABELS.get(code,code):value for code,value in counts.items()}})
    return pd.DataFrame(output)


def summary(frame):
    if frame.empty:return pd.DataFrame()
    return frame.groupby(['Şirket','Kaynak'],as_index=False).agg(Personel=('Personel','nunique'),**{'Ücretli gün':('Ücretli gün','sum'),'Çalışma saati':('Çalışma saati','sum'),'Ana tutar':('Ana tutar','sum'),'Vergi/ek kesinti':('Vergi/ek kesinti','sum'),'Net ödeme':('Net ödeme','sum')})

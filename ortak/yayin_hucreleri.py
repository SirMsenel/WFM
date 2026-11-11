"""Planlamacı doğrudan hücre düzenlemesi: kurallar, statüler ve denetim aynı işlemde."""
import pandas as pd
from ortak.calisma_alani_deposu import loads,dumps
from modules.vardiya_plani.vardiya_motoru import bounds


def reconcile_statuses(db,state,after,current,change_id):
    db.execute('CREATE TABLE IF NOT EXISTS planned_breaks(id TEXT PRIMARY KEY,publication_id TEXT,payload TEXT)')
    keys={(str(r['employee_id']),r['date']) for r in after};existing=[(r['id'],r['publication_id'],loads(r['payload'])) for r in db.execute('SELECT * FROM planned_breaks')];affected=[r for r in existing if (str(r[2]['employee_id']),r[2].get('date',r[2]['start'][:10])) in keys]
    kept=[]
    for item in affected:
        if item[2]['kind']=='Koçluk':
            new=next((r for r in after if str(r['employee_id'])==str(item[2]['employee_id']) and r['date']==item[2].get('date',item[2]['start'][:10])),None);span=bounds(new) if new else None
            if span and pd.Timestamp(span[0])<=pd.Timestamp(item[2]['start']) and pd.Timestamp(item[2]['end'])<=pd.Timestamp(span[1]):kept.append(item)
    affected=[r for r in affected if r not in kept]
    if state.get('status_rules',{}).get('enabled'):
        source=state.get('sp_staffing_result_df')
        if source is None:raise ValueError('Statüler yeniden planlanacak; önce bu günün ihtiyacını hesaplayın.')
        dates={r['date'] for r in after};coverage=source[pd.to_datetime(source.Tarih).dt.strftime('%Y-%m-%d').isin(dates)].copy()
        if coverage.empty:raise ValueError('Düzenlenen gün için ihtiyaç verisi yok; statüler yeniden kontrol edilemedi.')
        coverage=coverage.rename(columns={'Planlanan Agent':'İhtiyaç'});coverage['Atanan']=0.
        for i,r in coverage.iterrows():
            a=pd.Timestamp(r['Tarih'])+pd.Timedelta(minutes=(int(r['Slot'])-1)*30);b=a+pd.Timedelta(minutes=30);coverage.at[i,'Atanan']=sum(max(0,(min(b,pd.Timestamp(span[1]))-max(a,pd.Timestamp(span[0]))).total_seconds()/1800) for x in current if (span:=bounds(x)))
        coverage['Eksik']=(coverage['İhtiyaç']-coverage.Atanan).clip(lower=0);coverage['Fazla']=(coverage.Atanan-coverage['İhtiyaç']).clip(lower=0);check=dict(state);check['_status_fixed_baseline']=[r[2] for r in existing if r not in affected];check['status_rules']={**state['status_rules'],'coaching_by_leader':True}
        from ortak.statu_planlayici import plan
        planned,_,issues=plan(check,after,coverage,list(state.get('employees_cache',[])),used={})
        if any(x.get('severity')!='warning' for x in issues):raise ValueError('Yeni vardiyaya yemek/statü sığmıyor; süreleri kontrol edin.')
    else:planned=[]
    for ident,_,r in affected:
        db.execute('DELETE FROM planned_breaks WHERE id=?',(ident,))
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='manager_agenda'").fetchone():db.execute("DELETE FROM manager_agenda WHERE id=? AND kind='Koçluk'",(ident,))
    for n,r in enumerate(planned):
        pub=next((x.get('publication_id') for x in after if str(x['employee_id'])==r['employee_id'] and x['date']==r['date']),None);db.execute('INSERT INTO planned_breaks VALUES(?,?,?)',(change_id+'-ST-'+str(n),pub,dumps(r)))

    from ortak.roller_ve_yetkiler import append_audit
    append_audit(db,'Vardiyaya bağlı statüler yeniden planlandı',state['profile'],{'change_id':change_id,'before':[{'id':i,**p} for i,_,p in affected],'after':planned,'kept_coaching':[p for _,_,p in kept]})

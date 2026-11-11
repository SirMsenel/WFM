"""Yayın hücresi değişiminde statü hakları ve ortak kontenjanlar aynı işlemde yenilenir."""
import pandas as pd
from ortak.calisma_alani_deposu import loads,dumps
from modules.vardiya_plani.vardiya_motoru import bounds


def reconcile_statuses(db,state,after,current,change_id):
    db.execute('CREATE TABLE IF NOT EXISTS planned_breaks(id TEXT PRIMARY KEY,publication_id TEXT,payload TEXT)')
    db.execute("CREATE TABLE IF NOT EXISTS coaching_openings(id TEXT PRIMARY KEY,publication_id TEXT NOT NULL,employee_id TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL)")
    keys={(str(r['employee_id']),r['date']) for r in after};dates={r['date'] for r in after};pubs={r.get('publication_id') for r in after if r.get('publication_id')}
    roster=[r for r in current if not pubs or r.get('publication_id') in pubs];ids={str(r['employee_id']) for r in roster}
    people=[p for p in state.get('employees_cache',[]) if str(p['employee_id']) in ids];languages={p.get('language') or 'tr' for p in people}
    existing=[(r['id'],r['publication_id'],loads(r['payload'])) for r in db.execute('SELECT * FROM planned_breaks')];affected=[r for r in existing if (str(r[2]['employee_id']),r[2].get('date',r[2]['start'][:10])) in keys]
    for opening in db.execute("SELECT * FROM coaching_openings WHERE status='Açık'").fetchall():
        item=loads(opening['payload'])
        if item['date'] in dates and ((pubs and opening['publication_id'] in pubs) or (not pubs and (item.get('pool') or str(item['employee_id']) in ids))):db.execute("UPDATE coaching_openings SET status='İptal' WHERE id=?",(opening['id'],))
    kept=[]
    for item in affected:
        if item[2]['kind']=='Koçluk':
            new=next((r for r in after if str(r['employee_id'])==str(item[2]['employee_id']) and r['date']==item[2].get('date',item[2]['start'][:10])),None);span=bounds(new) if new else None
            if span and pd.Timestamp(span[0])<=pd.Timestamp(item[2]['start']) and pd.Timestamp(item[2]['end'])<=pd.Timestamp(span[1]):kept.append(item)
    affected=[r for r in affected if r not in kept]
    if state.get('status_rules',{}).get('enabled'):
        source=state.get('language_demands',{}).get(next(iter(languages))) if len(languages)==1 else None
        if source is None:source=state.get('sp_staffing_result_df')
        if source is None:raise ValueError('Statüler yeniden planlanacak; önce bu günün ihtiyacını hesaplayın.')
        coverage=source[pd.to_datetime(source.Tarih).dt.strftime('%Y-%m-%d').isin(dates)].copy()
        if coverage.empty:raise ValueError('Düzenlenen gün için ihtiyaç verisi yok; statüler yeniden kontrol edilemedi.')
        coverage=coverage.rename(columns={'Planlanan Agent':'İhtiyaç'});coverage['Atanan']=0.
        for i,r in coverage.iterrows():
            a=pd.Timestamp(r['Tarih'])+pd.Timedelta(minutes=(int(r['Slot'])-1)*30);b=a+pd.Timedelta(minutes=30);coverage.at[i,'Atanan']=sum(max(0,(min(b,pd.Timestamp(span[1]))-max(a,pd.Timestamp(span[0]))).total_seconds()/1800) for x in roster if (span:=bounds(x)))
        coverage['Eksik']=(coverage['İhtiyaç']-coverage.Atanan).clip(lower=0);coverage['Fazla']=(coverage.Atanan-coverage['İhtiyaç']).clip(lower=0)
        check=dict(state);check['_status_fixed_baseline']=[r[2] for r in existing if r not in affected and str(r[2]['employee_id']) in ids];check['_coaching_roster']=roster;check['status_rules']={**state['status_rules'],'coaching_by_leader':True}
        used={}
        for _,__,item in existing:
            if item.get('kind')!='Koçluk' or any(item is deleted[2] for deleted in affected):continue
            a,b=pd.Timestamp(item['start']),pd.Timestamp(item['end']);key=(str(item['employee_id']),a.strftime('%Y-%m'));used[key]=used.get(key,0)+(b-a).total_seconds()/60
        from ortak.statu_planlayici import plan
        planned,_,issues=plan(check,after,coverage,people,used=used)
        if any(x.get('severity')!='warning' for x in issues):raise ValueError('Yeni vardiyaya yemek/mola hakkının tamamı sığmıyor; vardiya ve statü kurallarını kontrol edin.')
        from ortak.statu_haklari import assert_complete
        assert_complete(check,{'plan':after,'staff':people,'breaks':planned})
    else:planned=[]
    for ident,_,r in affected:
        db.execute('DELETE FROM planned_breaks WHERE id=?',(ident,))
        if r.get('opening_id'):db.execute("UPDATE coaching_openings SET status='İptal' WHERE id=?",(r['opening_id'],))
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='manager_agenda'").fetchone():db.execute("DELETE FROM manager_agenda WHERE id=? AND kind='Koçluk'",(ident,))
    for n,r in enumerate(planned):
        pub=next((x.get('publication_id') for x in after if str(x['employee_id'])==r['employee_id'] and x['date']==r['date']),None)
        if r['kind']=='Koçluk Alanı':db.execute('INSERT INTO coaching_openings VALUES(?,?,?,?,?)',(change_id+'-ST-'+str(n),next(iter(pubs),'LEGACY'),str(r['employee_id']),'Açık',dumps(r)))
        else:db.execute('INSERT INTO planned_breaks VALUES(?,?,?)',(change_id+'-ST-'+str(n),pub,dumps(r)))
    from ortak.roller_ve_yetkiler import append_audit
    append_audit(db,'Vardiyaya bağlı statüler yeniden planlandı',state['profile'],{'change_id':change_id,'before':[{'id':i,**p} for i,_,p in affected],'after':planned,'kept_coaching':[p for _,_,p in kept]})

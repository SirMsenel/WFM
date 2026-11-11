"""Planlama/yönetim için hak sahibi kişi, dağıtım ve 15 dk koçluk kapasitesi."""
import pandas as pd
from ortak.calisma_alani_deposu import connect,loads
from modules.vardiya_plani.vardiya_motoru import bounds

CAPACITY_ROLES={'wfm','planning_manager','manager','assistant_manager','moderator'}

def capacity_visible(profile):return profile.get('position') in CAPACITY_ROLES


def entitlement_snapshot(state,rows,people):
    from ortak.statu_haklari import entitlements
    from ortak.statu_planlayici import MolaKuralHatasi
    lookup={str(p['employee_id']):p for p in people};result=[]
    for row in rows:
        if not bounds(row):continue
        eid=str(row['employee_id']);person=lookup.get(eid,{});error=''
        try:rights=entitlements(state,row,person)
        except MolaKuralHatasi as exc:rights={'Yemek':None,'Mola':None};error=str(exc)
        for kind,minutes in rights.items():result.append({'employee_id':eid,'date':str(row['date']),'kind':kind,'required_minutes':minutes,'name':person.get('full_name',eid),'error':error})
    return result


def published_entitlements(state,rows,people):
    """Yeni yayınların hakları kendi sürümünden; eski kayıtlar açıkça yaklaşık."""
    path=state.get('workspace_db_path');snapshots={}
    if path:
        with connect(path) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='publication_batches'").fetchone():
                for entry in db.execute("SELECT payload FROM publication_batches WHERE status='active' ORDER BY created_at"):
                    batch=loads(entry[0]);rights=list(batch.get('status_rights',[]))
                    for update in batch.get('status_rights_updates',[]):rights.extend(update['rights'])
                    for r in rights:snapshots[(str(r['employee_id']),r['date'],r['kind'])]=r
    fallback=entitlement_snapshot(state,rows,people);approximate=0;result=[]
    for r in fallback:
        saved=snapshots.get((r['employee_id'],r['date'],r['kind']))
        if saved is None:approximate+=1
        result.append(saved if saved is not None else r)
    return result,approximate


def capacity_openings(state,start,end,ids):
    if not capacity_visible(state.get('profile',{})):return []
    path=state.get('workspace_db_path');ids=set(map(str,ids));result=[]
    if not path:return result
    with connect(path) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='coaching_openings'").fetchone():return result
        for row in db.execute("SELECT * FROM coaching_openings WHERE status IN ('Açık','Atandı','İptal')"):
            item=loads(row['payload'])
            if row['status']=='İptal' and not item.get('operation_cancelled'):continue
            if item.get('superseded_by'):continue
            eligible=set(map(str,item.get('eligible_employee_ids',[item['employee_id']])))
            if not eligible&ids or not str(start)<=item['start'][:10]<=str(end):continue
            result.append(dict(item,remaining_capacity=int(item.get('remaining_capacity',1)) if row['status']=='Açık' else 0,capacity=int(item.get('capacity',1)),cancelled_capacity=int(item.get('cancelled_capacity',0))))
    return result


def person_headcounts(items,start,end):
    index=pd.date_range(start,pd.Timestamp(end)+pd.Timedelta(days=1)-pd.Timedelta(minutes=30),freq='30min');sets={kind:{t:set() for t in index} for kind in ['Yemek','Mola','Koçluk','Cuma']}
    for r in items:
        kind=r.get('kind')
        if kind not in sets or r.get('status')=='İptal':continue
        a,b=pd.Timestamp(r['start']),pd.Timestamp(r['end'])
        if b<=a:continue
        first=max(a.floor('30min'),index[0]);last=min((b-pd.Timedelta(microseconds=1)).floor('30min'),index[-1])
        for t in pd.date_range(first,last,freq='30min'):sets[kind][t].add(str(r['employee_id']))
    return pd.DataFrame({kind:[len(values[t]) for t in index] for kind,values in sets.items()},index=index)


def slot_capacity(items,openings,day):
    counts=person_headcounts(items,day,day).rename(columns={'Yemek':'Yemek kullanan kişi','Mola':'Mola kullanan kişi','Koçluk':'Koçluk atanan kişi','Cuma':'Cuma statüsü kullanan kişi'})
    counts['Toplam koçluk kontenjanı']=0;counts['Açık koçluk kontenjanı']=0;counts['İptal koçluk kontenjanı']=0
    for item in openings:
        a,b=pd.Timestamp(item['start']),pd.Timestamp(item['end'])
        if b-a!=pd.Timedelta(minutes=15) or a.normalize()!=pd.Timestamp(day).normalize():continue
        t=a.floor('30min');counts.at[t,'Toplam koçluk kontenjanı']+=int(item.get('capacity',1));counts.at[t,'Açık koçluk kontenjanı']+=int(item.get('remaining_capacity',item.get('capacity',1)));counts.at[t,'İptal koçluk kontenjanı']+=int(item.get('cancelled_capacity',0))
    counts['Atanmış koçluk kontenjanı']=counts['Toplam koçluk kontenjanı']-counts['Açık koçluk kontenjanı']-counts['İptal koçluk kontenjanı']
    return counts


def associate_items(items,rows):
    from bisect import bisect_right
    lookup={}
    for row in rows:
        span=bounds(row)
        if span:lookup.setdefault(str(row['employee_id']),[]).append((pd.Timestamp(span[0]),pd.Timestamp(span[1]),str(row['date'])))
    for eid in lookup:lookup[eid].sort()
    starts={eid:[r[0] for r in values] for eid,values in lookup.items()};result=[]
    for item in items:
        if item.get('date'):result.append(item);continue
        values=lookup.get(str(item['employee_id']),[]);a,b=pd.Timestamp(item['start']),pd.Timestamp(item['end']);pos=bisect_right(starts.get(str(item['employee_id']),[]),a)-1
        day=values[pos][2] if pos>=0 and b<=values[pos][1] else item['start'][:10]
        result.append(dict(item,date=day))
    return result


def fulfillment(rights,items,start,end):
    intervals={}
    for item in items:
        if item.get('status')=='İptal':continue
        key=(str(item['employee_id']),str(item.get('date') or item['start'][:10]),item['kind']);intervals.setdefault(key,[]).append((pd.Timestamp(item['start']),pd.Timestamp(item['end'])))
    totals={}
    for key,values in intervals.items():
        merged=[]
        for a,b in sorted(values):
            if b<=a:continue
            if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
            else:merged.append((a,b))
        totals[key]=sum((b-a).total_seconds()/60 for a,b in merged)
    result={kind:{'required_people':0,'given_people':0,'complete_people':0,'required_minutes':0.,'given_minutes':0.,'missing_minutes':0.,'excess_minutes':0.,'unknown_people':0} for kind in ['Yemek','Mola']};seen=set()
    for r in rights:
        key=(str(r['employee_id']),r['date'],r['kind'])
        if key in seen or r['kind'] not in result or not str(start)<=r['date']<=str(end):continue
        seen.add(key);s=result[r['kind']];required=r.get('required_minutes');actual=max(0,totals.get(key,0));s['given_minutes']+=actual;s['given_people']+=actual>0
        if required is None:s['unknown_people']+=1;continue
        required=float(required);s['required_minutes']+=required;s['missing_minutes']+=max(0,required-actual);s['excess_minutes']+=max(0,actual-required)
        if required>0:
            s['required_people']+=1;s['complete_people']+=actual+1e-8>=required
    return result


def render_capacity_report(state,rights,items,openings,start,end,key,actual=False,reference_items=None,include_cancellations=True):
    if not capacity_visible(state.get('profile',{})):return
    import streamlit as st
    from html import escape
    from ortak.statu_iptalleri import events
    cancellations=[]
    if include_cancellations and state.get('workspace_db_path'):
        with connect(state['workspace_db_path']) as db:cancellations=events(state,db)
    valid_ids={str(r['employee_id']) for r in rights}
    cancellations=[r for r in cancellations if str(r.get('employee_id')) in valid_ids and str(start)<=str(r.get('before',{}).get('date') or r['start'][:10])<=str(end)]
    report=fulfillment(rights,items,start,end);st.markdown('### Hak ve Dağıtım Özeti')
    if actual:st.caption('Gerçekleşen, gözlenen statü kayıtlarıdır. Henüz iletilmemiş veya gün içinde daha sonra kullanılacak süreler kesin kayıp sayılmaz.')
    if actual and not items:st.warning('Gerçekleşen statü verisi yok; dağıtım başarısı henüz ölçülemiyor.')
    st.caption('Kişi sayıları kişi-vardiya bazındadır: aynı kişi farklı günlerde ayrı sayılır. Eksik süreler günlük hakkın tamamlanıp tamamlanmadığını gösterir.')
    cols=st.columns(3)
    for col,kind,color in zip(cols[:2],['Yemek','Mola'],['#258f94','#7c69b0']):
        r=report[kind];canceled=[x for x in cancellations if x['kind']==kind];cancel_minutes=sum(x['cancelled_minutes'] for x in canceled);cancel_people=len({(x['employee_id'],x.get('before',{}).get('date') or x['start'][:10]) for x in canceled});text='Gerçekleşen' if actual else 'Dağıtılan'
        col.markdown(f'<div style="padding:18px;border:1px solid {color}44;border-top:4px solid {color};border-radius:16px;background:{color}0c;min-height:230px"><b style="color:{color};font-size:20px">{kind}</b><div style="font-size:14px;line-height:2;margin-top:12px">Hak sahibi: <b>{r["required_people"]} kişi-vardiya</b><br>{text}: <b>{r['given_people'] if not (actual and not items) else 'Veri yok'}</b> · Hakkı tamamlanan: <b>{r['complete_people'] if not (actual and not items) else '—'}</b><br>Hak: <b>{r["required_minutes"]:.0f} dk</b> · {text}: <b>{format(r['given_minutes'],'.0f') if not (actual and not items) else '—'} dk</b><br>Eksik: <b>{format(r['missing_minutes'],'.0f') if not (actual and not items) else '—'} dk</b> · Fazla: <b>{r["excess_minutes"]:.0f} dk</b><br>Operasyonel iptal: <b>{cancel_people} kişi-vardiya · {cancel_minutes:.0f} dk</b></div></div>',unsafe_allow_html=True)
    valid=[r for r in openings if pd.Timestamp(r['end'])-pd.Timestamp(r['start'])==pd.Timedelta(minutes=15) and str(start)<=r['start'][:10]<=str(end)]
    total=sum(int(r.get('capacity',1)) for r in valid);available=sum(int(r.get('remaining_capacity',r.get('capacity',1))) for r in valid);canceled_count=sum(int(r.get('cancelled_capacity',0)) for r in valid)
    cols[2].markdown(f'<div style="padding:18px;border:1px solid #b6dfc3;border-top:4px solid #38895a;border-radius:16px;background:#eff8f1;min-height:230px"><b style="color:#38895a;font-size:20px">Koçluk · 15 dk</b><div style="font-size:14px;line-height:2;margin-top:12px">Toplam kayıtlı kontenjan: <b>{total}</b><br>Atanan kontenjan: <b>{total-available-canceled_count}</b><br>Açık kontenjan: <b>{available}</b><br>İptal kontenjan: <b>{canceled_count}</b><br>Açık süre: <b>{available*15} dk</b></div></div>',unsafe_allow_html=True)
    if any(r['unknown_people'] for r in report.values()):st.warning('Bazı vardiyaların hak kuralı belirlenemiyor; bunlar sıfır hak sayılmadı. Statü kurallarını kontrol edin.')
    days=list(pd.date_range(start,end));day=st.selectbox('Yarım saatlik kapasite günü',days,format_func=lambda t:t.strftime('%d.%m.%Y'),key=key+'_day') if len(days)>1 else pd.Timestamp(start)
    table=slot_capacity(items,openings,day)
    if reference_items is not None:
        planned=person_headcounts(reference_items,day,day);table.insert(0,'Planlanan yemek kişi',planned['Yemek']);table.insert(1,'Planlanan mola kişi',planned['Mola'])
    st.markdown('#### 30 Dakikalık Kişi ve Koçluk Adetleri')
    st.caption('Yemek/mola sütunları o yarım saatte statü kullanan tekil kişilerdir; 10 dakika mola kullanan kişi 1 sayılır. Koçluk sütunları bu yarım saatte başlayan 15 dakikalık görüşme adetleridir; aynı kişi farklı dilimlerde tekrar görünebilir. Açık, henüz atanmamış kapasitedir; geçmiş saatler yeniden seçilemez.')
    st.bar_chart(table[['Yemek kullanan kişi','Mola kullanan kişi','Koçluk atanan kişi','Açık koçluk kontenjanı']],stack=False,color=['#258f94','#7c69b0','#c18e44','#38895a'])
    table.index=[f'{t:%H:%M}–{t+pd.Timedelta(minutes=30):%H:%M}' for t in table.index];table.index.name='Saat aralığı'
    st.dataframe(table.style.format('{:.0f}').background_gradient(cmap='Greens',subset=['Açık koçluk kontenjanı']),use_container_width=True,height=420)

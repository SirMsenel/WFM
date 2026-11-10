"""Aylık kapasite senaryosu ve ters Erlang C."""
import math
import pandas as pd
import streamlit as st
from modules.mesai_plani.personel_ihtiyaci import erlang_c_metrics_for_m,erlang_c_required_agents
from ortak.personel import get_people,WORK_LABELS
from ortak.calisma_alani_deposu import connect,dumps,loads


def inverse_erlang(agents,aht=300,target=.8,seconds=20,occupancy=.85):
    if agents<=0:return 0.
    low,high=0.,agents*1800/aht*occupancy
    for _ in range(45):
        mid=(low+high)/2;_,sl,occ=erlang_c_metrics_for_m(mid,aht,1800,int(agents),seconds)
        if sl>=target and occ<=occupancy:low=mid
        else:high=mid
    return low


def render():
    s=st.session_state;st.title('🔮 Similasyon');people=[p for p in get_people(s) if p.get('position')=='agent']
    a,b,c=st.columns(3);groups=a.multiselect('Çalışma grupları',list(WORK_LABELS),default=list(WORK_LABELS));months=b.slider('Gelecek ay sayısı',1,12,3);start=c.date_input('Senaryo başlangıcı',value=pd.Timestamp('2026-12-01').date())
    staff=sum(p['work_type'] in groups for p in people);a,b,c=st.columns(3);headcount=a.number_input('Başlangıç personel',0,100000,staff);growth=b.number_input('Aylık çağrı artışı (%)',-90.,300.,5.);attrition=c.number_input('Aylık ayrılma (%)',0.,100.,2.)
    a,b,c,d=st.columns(4);aht=a.number_input('AHT (sn)',30,3600,300);shrink=b.slider('Diğer kayıp (%)',0,90,30);days=c.slider('Kişi başına haftalık gün',1,6,5);hours=d.number_input('Günlük çalışma (saat)',1.,12.,8.)
    from ortak.gunluk_tahmin_deposu import saved_daily,daily_label
    records=saved_daily(s['workspace_db_path']);byid={r['id']:r for r in records};selected=st.selectbox('Tahmin kaynağı',['history']+list(byid),format_func=lambda i:'Son 30 gün aynı hafta günü' if i=='history' else daily_label(byid[i],s['workspace_db_path']),key='sim_daily')
    from ortak.calisma_alani_deposu import load_calls
    history=load_calls(False,s['workspace_db_path']);history=history.tail(30)
    if history.empty:st.info('Çağrı geçmişi gerekli.');return
    profile=s.get('sp_active_ratio_profile_df');rows=[]
    for i,month in enumerate(pd.date_range(pd.Timestamp(start).replace(day=1),periods=months,freq='MS')):
        dates=pd.date_range(month,month+pd.offsets.MonthEnd());frame=byid[selected]['frame'] if selected!='history' else None;forecast=[]
        for day in dates:
            known=frame[pd.to_datetime(frame.tarih).dt.normalize()==day] if frame is not None else pd.DataFrame()
            same=history[pd.to_datetime(history.tarih).dt.weekday==day.weekday()]
            forecast.append(float(known.y_pred.iloc[0]) if not known.empty else float(same.cagri_sayisi.mean() if not same.empty else history.cagri_sayisi.mean())*(1+growth/100)**(i+1))
        peak_share=float(profile['Oran(%)'].max())/100 if profile is not None and not profile.empty else 1/32
        peak=max(forecast)*peak_share;net=erlang_c_required_agents(peak,aht,1800,.8,20,.85)['m'];needed=math.ceil(net/(1-shrink/100)*7*16/(days*hours));available=math.floor(headcount*(1-attrition/100)**(i+1));agents=math.floor(available*days*hours/(7*16)*(1-shrink/100))
        rows.append({'Ay':month.strftime('%Y-%m'),'Çağrı tahmini':round(sum(forecast)),'Mevcut personel':available,'Gerekli personel':needed,'Önerilen alım':max(0,needed-available),'Tepe yarım saat çağrı kapasitesi':round(inverse_erlang(agents,aht))})
    table=pd.DataFrame(rows);st.dataframe(table,hide_index=True,use_container_width=True);st.line_chart(table.set_index('Ay')[['Mevcut personel','Gerekli personel']]);st.caption('08–24 aralığında ortalama kapasite senaryosu; gerçek vardiya çizelgesi değildir. Eksik tahmin tarihleri aynı hafta günü geçmişiyle tamamlanır; büyüme yalnızca bu tamamlamalara uygulanır. Alım önerisi kurum İK sistemine gönderilmez.')
    month=st.selectbox('Aksiyon ayı',table.Ay.tolist());kind=st.selectbox('Aksiyon',['Personel alım önerisi','Olağan dışı durum aksiyonu']);note=st.text_area('Aksiyon gerekçesi')
    path=s['workspace_db_path']
    with connect(path) as db:db.execute('CREATE TABLE IF NOT EXISTS simulation_actions(id INTEGER PRIMARY KEY,payload TEXT NOT NULL)')
    if st.button('Aksiyonu Takibe Al',disabled=not note.strip()):
        with connect(path) as db:db.execute('INSERT INTO simulation_actions(payload) VALUES(?)',(dumps({'month':month,'kind':kind,'reason':note,'actor':s['profile']['username'],'status':'Açık','scenario':rows}),))
        st.success('Aksiyon kayıt altına alındı.')
    with connect(path) as db:items=[dict(loads(r['payload']),id=r['id']) for r in db.execute('SELECT * FROM simulation_actions')]
    if items:
        st.dataframe([{k:r[k] for k in ('id','month','kind','reason','status')} for r in items],hide_index=True,use_container_width=True)
        ident=st.selectbox('Tamamlanan aksiyon',[r['id'] for r in items if r['status']=='Açık'],key='sim_close') if any(r['status']=='Açık' for r in items) else None
        if ident and st.button('Aksiyonu Tamamlandı Yap'):
            item=next(r for r in items if r['id']==ident);item['status']='Tamamlandı'
            with connect(path) as db:db.execute('UPDATE simulation_actions SET payload=? WHERE id=?',(dumps(item),ident))
            st.rerun()

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
    from ortak.senaryolar import simulate
    from ortak.calisma_alani_deposu import load_calls
    from ortak.modern_kartlar import metric_cards
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import plotly.express as px
    s=st.session_state;st.title('🔮 Similasyon')
    st.markdown('<div style="padding:20px 24px;margin:6px 0 18px;border-radius:20px;background:linear-gradient(110deg,#e6f4f6,#edf0fb);border:1px solid #d5e4ec"><div style="font-size:12px;font-weight:800;letter-spacing:.11em;color:#367783">KAPASİTE SENARYO LABORATUVARI</div><div style="font-size:24px;font-weight:800;color:#214c61;margin:6px 0">Çağrı, AHT, shrinkage ve servis seviyesini birlikte simüle et</div><div style="color:#58717d">Senaryolar, gelecek aylardaki iş gücü ihtiyacını görünür kılar; yayınlanmış vardiya planını değiştirmez.</div></div>',unsafe_allow_html=True)
    people=[p for p in get_people(s) if p.get('position')=='agent'];a,b,c=st.columns(3);groups=a.multiselect('Çalışma grupları',list(WORK_LABELS),default=list(WORK_LABELS));months=b.slider('Gelecek ay sayısı',1,24,12);today=datetime.now(ZoneInfo('Europe/Istanbul')).date();start=c.date_input('Senaryo başlangıcı',value=(pd.Timestamp(today)+pd.offsets.MonthBegin(1)).date())
    staff=sum(p['work_type'] in groups for p in people)
    group_rows=[]
    from ortak.calisma_sureleri import personnel_hours
    for group in groups:
        cohort=[p for p in people if p['work_type']==group];hours_frame=personnel_hours(s,cohort,today.replace(day=1),today,published_only=True)
        group_rows.append({'Grup':WORK_LABELS.get(group,group),'Aktif personel':len(cohort),'Seçili ay ort. çalışma saati':round(float(hours_frame['Toplam saat'].mean()),1) if not hours_frame.empty else 0})
    st.markdown('### Mevcut Personel ve Çalışma Kapasitesi')
    st.dataframe(pd.DataFrame(group_rows),hide_index=True,use_container_width=True)
    staff=sum(p['work_type'] in groups for p in people);a,b,c=st.columns(3);headcount=a.number_input('Başlangıç personel',0,100000,staff);growth=b.number_input('Aylık çağrı büyümesi (%)',-50.,100.,2.);attrition=c.number_input('Aylık ayrılma (%)',0.,50.,2.)
    a,b,c,d=st.columns(4);sl=a.slider('Hedef servis seviyesi (%)',50,99,80);aht=b.number_input('AHT (sn)',30,3600,300);shrink=c.slider('Toplam shrinkage (%)',0,90,30);seconds=d.number_input('Hedef cevap süresi (sn)',5,120,20,5)
    a,b=st.columns(2);days=a.slider('Kişi başına haftalık gün',1,6,5);hours=b.number_input('Günlük çalışma (saat)',1.,12.,8.)
    from ortak.gunluk_tahmin_deposu import saved_daily,daily_label
    records=saved_daily(s['workspace_db_path']);byid={r['id']:r for r in records};selected=st.selectbox('Tahmin kaynağı',['history']+list(byid),format_func=lambda i:'Son 12 ay geçmiş + gün/mevsim örüntüsü' if i=='history' else daily_label(byid[i],s['workspace_db_path']),key='sim_daily');profile=s.get('sp_active_ratio_profile_df');peak_share=float(profile['Oran(%)'].max())/100 if profile is not None and not profile.empty else 1/32
    try:table,meta=simulate(load_calls(False,s['workspace_db_path']),start,months,headcount,aht,shrink/100,sl/100,seconds,growth=growth/100,attrition=attrition/100,days=days,hours=hours,peak_share=peak_share,forecast=byid[selected]['frame'] if selected!='history' else None)
    except ValueError as e:st.info(str(e));return
    metric_cards([('Geçmiş gün',meta['history_days']),('Ölçülen geçmiş hata',f"%{meta['wape']:.1f}"),('Senaryo farkı',f"±%{meta['spread']:.1f}")]);st.caption(f"Geçmiş: {meta['history_start']} – {meta['history_end']}. İyi senaryoda çağrı/ayrılma daha düşük, kötüde daha yüksektir. Aralık geçmiş hata oranından türetilir; güven aralığı değildir.")
    from ortak.senaryo_kartlari import render_scenarios
    render_scenarios(table,sl)
    st.markdown('### Parametre Varyasyonları · İlk Ay')
    first_month=table[table['Ay']==sorted(table['Ay'].unique())[0]];peak=max(1,int(first_month[first_month['Senaryo']=='Normal']['Tepe yarım saat çağrı'].iloc[0]))
    variations=[]
    for test_aht in (190,195,200):
        for test_shrinkage in (.20,.25,.30):
            for test_sl in (.80,.85,.90):
                net=erlang_c_required_agents(peak,test_aht,1800,test_sl,seconds,.85)['m'];planned=math.ceil(net/(1-test_shrinkage))
                variations.append({'AHT (sn)':test_aht,'Shrinkage':f'%{test_shrinkage*100:.0f}','Hedef SL':f'%{test_sl*100:.0f} / {seconds} sn','Net agent':net,'Planlanan agent':planned})
    st.caption(f'İlk ayın normal senaryosundaki tepe yarım saat çağrısı ({peak:,}) üzerinden hesaplanmış 27 parametre kombinasyonu.')
    st.dataframe(pd.DataFrame(variations),hide_index=True,use_container_width=True,height=360)
    fig=px.line(table,x='Ay',y='Gerekli personel',color='Senaryo',markers=True,color_discrete_map={'İyi':'#269d89','Normal':'#6983bb','Kötü':'#c96f72'});st.plotly_chart(fig,use_container_width=True)
    fig=px.line(table,x='Ay',y='Simüle SL (%)',color='Senaryo',markers=True);fig.add_hline(y=sl,line_dash='dash',annotation_text='Hedef SL');st.plotly_chart(fig,use_container_width=True)
    st.download_button('Tüm Senaryo Aylarını CSV İndir',table.to_csv(index=False).encode('utf-8-sig'),'simulasyon_senaryolari.csv','text/csv',key='sim_scenarios_csv')
    st.caption('08–24 hizmet penceresi için ortalama kapasite senaryosudur; gerçek vardiya optimizasyonunun yerini almaz. Kayıtlı tahmin olmayan tarihler geçmişten tamamlanır. Alım önerileri otomatik İK emri değildir.')
    rows=table.to_dict('records');path=s['workspace_db_path']
    with connect(path) as db:db.execute('CREATE TABLE IF NOT EXISTS simulation_actions(id INTEGER PRIMARY KEY,payload TEXT NOT NULL)')
    month=st.selectbox('Aksiyon ayı',sorted(table.Ay.unique()));kind=st.selectbox('Aksiyon',['Personel alım önerisi','Olağan dışı durum aksiyonu']);note=st.text_area('Aksiyon gerekçesi')
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

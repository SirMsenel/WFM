"""Aylık kapasite senaryosu, ters Erlang C ve yönetim aksiyonları."""
import math
import pandas as pd
import streamlit as st

from modules.mesai_plani.personel_ihtiyaci import erlang_c_metrics_for_m,erlang_c_required_agents
from ortak.personel import get_people,WORK_LABELS


def inverse_erlang(agents,aht=300,target=.8,seconds=20,occupancy=.85):
    from ortak.senaryolar import inverse_erlang_calls
    return inverse_erlang_calls(agents,aht,target,seconds,occupancy)


def _variation_cards(first,seconds):
    variants=[('İyi',190,.20,.80,'#2d8b68'),('Normal',195,.25,.85,'#c18735'),('Kötü',200,.30,.90,'#bd6262')]
    for col,(scenario,test_aht,test_shrinkage,test_sl,color) in zip(st.columns(3),variants):
        source=first[first['Senaryo']==scenario];peak=max(1,int(source['Tepe yarım saat çağrı'].iloc[0]));net=erlang_c_required_agents(peak,test_aht,1800,test_sl,seconds,.85)['m'];planned=math.ceil(net/(1-test_shrinkage))
        col.markdown(f'<div style="min-height:225px;padding:19px;border-radius:19px;border:1px solid {color}35;border-top:5px solid {color};background:linear-gradient(145deg,{color}12,#fff)"><div style="display:flex;justify-content:space-between;align-items:center;color:{color}"><b style="font-size:18px">{scenario} Senaryo</b><small>%{test_sl*100:.0f} SL</small></div><div style="font-size:35px;font-weight:850;color:{color};margin:16px 0">{planned}<small style="font-size:13px"> planlanan kişi</small></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:9px;font-size:12px"><span>Net agent<br><b>{net}</b></span><span>Tepe çağrı<br><b>{peak}</b></span><span>AHT<br><b>{test_aht} sn</b></span><span>Shrinkage<br><b>%{test_shrinkage*100:.0f}</b></span></div></div>',unsafe_allow_html=True)


def _action_page(state,table):
    from ortak.simulasyon_aksiyonlari import submit,list_actions
    from html import escape
    month=st.selectbox('Aksiyon ayı',sorted(table.Ay.unique()),key='sim_action_month');kind=st.selectbox('Aksiyon',['Personel alım önerisi','Olağan dışı durum aksiyonu'],key='sim_action_kind');note=st.text_area('Aksiyon gerekçesi',key='sim_action_note')
    if st.button('Yönetim Onayına Gönder',disabled=not note.strip(),type='primary',key='sim_action_submit'):
        try:
            ident=submit(state,month,kind,note,table.to_dict('records'));st.success(f'Aksiyon #{ident} yönetici ve planlama onay merkezine gönderildi.')
        except ValueError as exc:st.warning(str(exc))
    items=list_actions(state)
    if not items:return
    st.markdown('### Aksiyon Takibi')
    colors={'Onay bekliyor':'#c18735','Onaylandı':'#2d8b68','Reddedildi':'#bd6262','Tamamlandı':'#65768a'}
    for offset in range(0,len(items),3):
        for col,item in zip(st.columns(3),items[offset:offset+3]):
            color=colors.get(item.get('status'),'#65768a')
            col.markdown(f'<div style="min-height:150px;padding:16px;border-radius:16px;border-left:5px solid {color};background:{color}0e"><small style="color:{color}">{escape(item.get("status","—").upper())}</small><h4>{escape(item.get("kind","Aksiyon"))}</h4><b>{escape(item.get("month","—"))}</b><p style="font-size:12px">{escape(item.get("reason",""))}</p></div>',unsafe_allow_html=True)


def render():
    from ortak.senaryolar import simulate
    from ortak.calisma_alani_deposu import load_calls
    from ortak.modern_kartlar import metric_cards
    import plotly.express as px
    s=st.session_state;st.title('🧮 Similasyon')
    st.markdown('<div style="display:grid;grid-template-columns:95px 1fr;gap:20px;align-items:center;padding:20px 24px;margin:6px 0 18px;border-radius:20px;background:linear-gradient(110deg,#e7f5ef,#edf1fb);border:1px solid #d5e4ec"><div style="height:76px;display:flex;align-items:flex-end;gap:7px;padding:10px;border-radius:17px;background:#fff"><i style="height:32%;width:18px;background:#62aa91;border-radius:5px"></i><i style="height:57%;width:18px;background:#6f88bd;border-radius:5px"></i><i style="height:88%;width:18px;background:#d18a4c;border-radius:5px"></i></div><div><div style="font-size:12px;font-weight:800;letter-spacing:.11em;color:#367783">KAPASİTE SENARYO LABORATUVARI</div><div style="font-size:24px;font-weight:800;color:#214c61;margin:6px 0">Çağrı, servis seviyesi ve personel kapasitesini birlikte simüle et</div><div style="color:#58717d">İleri yönlü Erlang C personel ihtiyacını; ters Erlang C mevcut ekibin taşıyabileceği çağrıyı hesaplar.</div></div></div>',unsafe_allow_html=True)
    from ortak.demo_zamani import today as active_today
    people=[p for p in get_people(s) if p.get('position')=='agent'];a,b,c=st.columns(3);groups=a.multiselect('Çalışma grupları',list(WORK_LABELS),default=list(WORK_LABELS),format_func=WORK_LABELS.get);months=b.slider('Gelecek ay sayısı',1,24,12);today=active_today(s);start=c.date_input('Senaryo başlangıcı',value=(pd.Timestamp(today)+pd.offsets.MonthBegin(1)).date())
    staff=sum(p['work_type'] in groups for p in people);a,b,c=st.columns(3);headcount=a.number_input('Başlangıç personel',0,100000,staff);growth=b.number_input('Aylık çağrı büyümesi (%)',-50.,100.,2.);attrition=c.number_input('Aylık ayrılma (%)',0.,50.,2.)
    a,b,c,d=st.columns(4);sl=a.slider('Hedef servis seviyesi (%)',50,99,80);aht=b.number_input('AHT (sn)',30,3600,300);shrink=c.slider('Toplam shrinkage (%)',0,90,30);seconds=d.number_input('Hedef cevap süresi (sn)',5,120,20,5)
    a,b=st.columns(2);days=a.slider('Kişi başına haftalık gün',1,6,5);hours=b.number_input('Günlük çalışma (saat)',1.,12.,8.)
    from ortak.gunluk_tahmin_deposu import saved_daily,daily_label
    records=saved_daily(s['workspace_db_path']);byid={r['id']:r for r in records};selected=st.selectbox('Tahmin kaynağı',['history']+list(byid),format_func=lambda i:'Son 12 ay geçmiş + gün/mevsim örüntüsü' if i=='history' else daily_label(byid[i],s['workspace_db_path']),key='sim_daily');profile=s.get('sp_active_ratio_profile_df');peak_share=float(profile['Oran(%)'].max())/100 if profile is not None and not profile.empty else 1/32
    try:table,meta=simulate(load_calls(False,s['workspace_db_path']),start,months,headcount,aht,shrink/100,sl/100,seconds,growth=growth/100,attrition=attrition/100,days=days,hours=hours,peak_share=peak_share,forecast=byid[selected]['frame'] if selected!='history' else None)
    except ValueError as exc:st.info(str(exc));return
    view=st.segmented_control('Simülasyon bölümü',['Senaryo Özeti','Parametre Varyasyonları','Aksiyonlar'],default='Senaryo Özeti',key='sim_section') or 'Senaryo Özeti'
    if view=='Parametre Varyasyonları':
        st.markdown('### Parametre Varyasyonları · İlk Ay')
        first=table[table['Ay']==sorted(table['Ay'].unique())[0]];_variation_cards(first,seconds);return
    if view=='Aksiyonlar':_action_page(s,table);return
    metric_cards([('Geçmiş gün',meta['history_days']),('Ölçülen geçmiş hata',f"%{meta['wape']:.1f}"),('Senaryo farkı',f"±%{meta['spread']:.1f}")])
    from ortak.senaryo_kartlari import render_scenarios
    render_scenarios(table,sl)
    with st.expander('Hesaplama yöntemi'):
        st.markdown('**İleri Erlang C:** Tahmin edilen tepe yarım saat çağrısı, AHT, cevap süresi, doluluk ve hedef servis seviyesiyle net agent ihtiyacını bulur. Shrinkage ve çalışma süresi eklenerek kişi sayısına çevrilir.\n\n**Ters Erlang C:** Mevcut kişi sayısından aynı anda hatta kalabilecek agent hesaplanır; hedef servis seviyesini bozmadan taşınabilecek en yüksek yarım saat çağrısı ikili aramayla bulunur. `Tepe kapasite farkı`, bu değer ile beklenen tepe çağrı arasındaki farktır.')
    fig=px.line(table,x='Ay',y='Gerekli personel',color='Senaryo',markers=True,color_discrete_map={'İyi':'#269d89','Normal':'#6983bb','Kötü':'#c96f72'});st.plotly_chart(fig,use_container_width=True)
    fig=px.line(table,x='Ay',y='Simüle SL (%)',color='Senaryo',markers=True);fig.add_hline(y=sl,line_dash='dash',annotation_text='Hedef SL');st.plotly_chart(fig,use_container_width=True)
    st.download_button('Tüm Senaryo Aylarını CSV İndir',table.to_csv(index=False).encode('utf-8-sig'),'simulasyon_senaryolari.csv','text/csv',key='sim_scenarios_csv')

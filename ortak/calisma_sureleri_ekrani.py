# Ortak / Calisma Sureleri Ekrani — bu ekranın / servisin uygulama kodu.
import calendar
import pandas as pd
import streamlit as st
from ortak.personel import WORK_LABELS,planner_people
from ortak.calisma_sureleri import personnel_hours,save_target
from ortak.calisma_alani_deposu import save_keys


def render_hours_summary(state,people):
    st.divider();st.markdown('### Çalışma Süresi ve Kalan Kapasite');left,right=st.columns([1,1.3])
    with left.container(border=True):render_targets(state)
    with right.container(border=True):
        today=pd.Timestamp.now(tz='Europe/Istanbul').date();ctx=state.get('plan_ctx') or {};start=pd.Timestamp(ctx.get('start',today.replace(day=1))).date();end=pd.Timestamp(ctx.get('end',today)).date();dates=st.date_input('İncelenecek çalışma dönemi',(start,end),key='hours_history_range')
        if len(dates)!=2:return
        agents=[x for x in people if x.get('position','agent')=='agent'];df=personnel_hours(state,agents,*dates,published_only=True)
        if df.empty:st.info('Personel veya çalışma kaydı yok.');return
        st.bar_chart(df.groupby('Grup')['Toplam saat'].mean().rename(index=WORK_LABELS),color='#2c98a2')
        from html import escape
        for group in sorted(df.Grup.unique()):
            used=float(df.loc[df.Grup==group,'Toplam saat'].mean());targets=[x for x in state.get('group_hour_targets',[]) if x['group']==group and x['start']<=str(dates[1]) and str(dates[0])<=x['end']]
            st.markdown('<div style="padding:15px;background:#f0f7fb;border-left:4px solid #358d9e;border-radius:13px;margin:12px 0"><b>'+escape(WORK_LABELS.get(group,group))+'</b><div style="font-size:23px;margin:10px 0;color:#267b8b">'+f'{used:.1f} saat / kişi</div><small>Seçilen aralıkta yayınlanmış çalışma</small></div>',unsafe_allow_html=True)
            if targets:
                target=targets[0];used_all=personnel_hours(state,[p for p in agents if p['work_type']==group],target['start'],target['end']);amount=float(used_all['Toplam saat'].mean()) if not used_all.empty else 0;remaining=max(0,target['hours']-amount);st.progress(min(1.,amount/target['hours']) if target['hours'] else 1.,text=f"Hedef dönemi {target['start']} – {target['end']} · {amount:.1f} / {target['hours']:.1f} sa · Kalan {remaining:.1f} sa / kişi")
            else:st.caption('Bu aralıkla eşleşen çalışma saati üst sınırı henüz tanımlı değil.')


def render_targets(state):
    st.markdown('### Gruplara Çalışma Süresi Tanımla')
    st.caption('Her hedef, gruptaki her kişi için dönem boyunca çalışma saati üst sınırıdır. Motor ihtiyacı aşmak için bu süreyi doldurmaz; kalan saatleri burada görürsün.')
    mode=st.radio('Hedef dönemi',['Aylık','Özel dönem'],horizontal=True,key='hour_target_mode')
    ctx=state.get('plan_ctx') or {};anchor=pd.Timestamp(ctx.get('start',pd.Timestamp.today())).date()
    if mode=='Aylık':
        month=st.date_input('Hedef ayından bir tarih',value=anchor,key='hour_target_month')
        start=month.replace(day=1);end=month.replace(day=calendar.monthrange(month.year,month.month)[1])
    else:
        dates=st.date_input('Hedef tarih aralığı',value=(anchor,pd.Timestamp(ctx.get('end',anchor)).date()),key='hour_target_dates')
        if len(dates)!=2:st.info('İki tarihi seçin.');return
        start,end=dates
    group=st.selectbox('Çalışma grubu',list(WORK_LABELS),format_func=WORK_LABELS.get,key='hour_target_group')
    hours=st.number_input('Kişi başına dönem saati',min_value=0.,max_value=10000.,value=180.,step=.5,key='hour_target_hours')
    if st.button('Süreyi Kaydet ve Uygula',key='hour_target_save',type='primary'):
        try:save_target(state,group,start,end,hours);st.success('Süre hedefi kaydedildi. Otomatik taslağı yeniden oluşturun.')
        except ValueError as exc:st.error(str(exc))
    targets=state.get('group_hour_targets',[])
    if not targets:st.info('Henüz çalışma süresi hedefi tanımlanmadı.');return
    people=planner_people(state);rows=[]
    for t in targets:
        df=personnel_hours(state,[e for e in people if e['work_type']==t['group']],t['start'],t['end'])
        actual=df['Toplam saat'].mean() if not df.empty else 0
        rows.append({'Grup':WORK_LABELS.get(t['group'],t['group']),'Başlangıç':t['start'],'Bitiş':t['end'],'Kişi başı hedef':t['hours'],'Kişi başı planlanan':round(actual,1),'Kişi başı kalan':round(max(0,t['hours']-actual),1)})
    st.dataframe(rows,hide_index=True,use_container_width=True)
    selected=st.multiselect('Silinecek süre hedefleri',list(range(len(targets))),format_func=lambda i:f"{WORK_LABELS[targets[i]['group']]} · {targets[i]['start']} – {targets[i]['end']}",key='hour_target_delete_selection')
    if st.button('Seçilen Süre Hedeflerini Sil',disabled=not selected,key='hour_target_delete'):
        state['group_hour_targets']=[t for i,t in enumerate(targets) if i not in selected];save_keys(state);st.rerun()

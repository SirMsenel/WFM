import calendar
import pandas as pd
import streamlit as st
from core.personnel import WORK_LABELS,planner_people
from core.work_hours import personnel_hours,save_target
from core.workspace_store import save_keys


def render_hours_summary(state,people):
    ctx=state.get('plan_ctx')
    if not ctx:return
    st.markdown('### Seçili Dönemde Çalışma Saatleri')
    st.caption(f"{pd.Timestamp(ctx['start']):%d.%m.%Y} – {pd.Timestamp(ctx['end']):%d.%m.%Y} · Takvim günü başına ortalama; izin ve boş günler 0 saat sayılır. Gece vardiyaları gerçek tarih sınırlarından bölünür.")
    agents=[e for e in people if e.get('position','agent')=='agent']
    if not agents:st.info('Personel bulunamadı.');return
    df=personnel_hours(state,agents,ctx['start'],ctx['end'])
    table=df.groupby('Grup',as_index=False).agg(**{'Personel':('Personel','size'),'Toplam saat':('Toplam saat','sum'),'Kişi başı dönem ortalaması':('Toplam saat','mean'),'Kişi başı günlük ortalama':('Günlük ortalama saat','mean')})
    table.Grup=table.Grup.map(lambda g:WORK_LABELS.get(g,g))
    st.dataframe(table.style.format({c:'{:.1f}' for c in table if c not in {'Grup','Personel'}}),hide_index=True,use_container_width=True)
    st.bar_chart(table.set_index('Grup')[['Kişi başı dönem ortalaması']],color='#118aa1')
    with st.expander('Personel bazında çalışma saatleri'):
        df.Grup=df.Grup.map(lambda g:WORK_LABELS.get(g,g));st.dataframe(df,hide_index=True,use_container_width=True)
    st.caption('Çalışma Süreleri bölümünden grup için kişi başına aylık veya özel dönem saat hedefi tanımlayabilirsin.')


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

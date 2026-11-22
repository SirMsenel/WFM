# Ortak / Calisma Sureleri Ekrani — bu ekranın / servisin uygulama kodu.
import calendar
import pandas as pd
import streamlit as st
from ortak.personel import WORK_LABELS,planner_people
from ortak.calisma_sureleri import personnel_hours,save_target
from ortak.calisma_alani_deposu import save_keys


def render_hours_summary(state,people):
    st.divider();st.markdown('### Çalışma Süresi ve Kalan Kapasite')
    agents=[x for x in people if x.get('position','agent')=='agent'];targets=state.get('group_hour_targets',[])
    if not targets:
        ctx=state.get('plan_ctx') or {};today=pd.Timestamp.now(tz='Europe/Istanbul').date();start=pd.Timestamp(ctx.get('start',today.replace(day=1))).date();end=pd.Timestamp(ctx.get('end',today)).date()
        groups=sorted({p.get('work_type') for p in agents if p.get('work_type')});group=st.selectbox('İncelenecek grup',groups,format_func=lambda value:WORK_LABELS.get(value,value),key='capacity_review_group')
        dates=st.date_input('Grafikte incelenecek tarih aralığı',(start,end),key='hours_history_range')
        if len(dates)==2:
            generic=personnel_hours(state,[p for p in agents if p.get('work_type')==group],*dates,published_only=False)
            if not generic.empty:
                from ortak.modern_kartlar import metric_cards
                metric_cards([('Aktif personel',len(generic)),('Kişi başı ortalama',f'{generic["Toplam saat"].mean():.1f} saat'),('Toplam planlanan',f'{generic["Toplam saat"].sum():.1f} saat')]);st.bar_chart(generic.set_index('Personel')['Toplam saat'],color='#4b95a3')
        st.info('Kalan kapasite ve doluluk halkaları için bu gruba bir dönem çalışma hedefi tanımlayın.')
        with st.expander('Çalışma süresi hedefi tanımla',expanded=True):render_targets(state)
        return
    st.markdown('<div style="padding:14px 17px;border-radius:16px;background:linear-gradient(120deg,#edf7f8,#f4f1fa);border:1px solid #d9e7ec"><b style="color:#315f70">Tüm Çalışma Süresi Hedefleri</b><br><small>Her kart hedef dönemin kişi başı doluluğunu ve kalan kapasitesini gösterir.</small></div>',unsafe_allow_html=True)
    for offset in range(0,len(targets),3):
        for col,target in zip(st.columns(3),targets[offset:offset+3]):
            group_people=[p for p in agents if p.get('work_type')==target['group']]
            frame=personnel_hours(state,group_people,target['start'],target['end'],published_only=False)
            used=float(frame['Toplam saat'].mean()) if not frame.empty else 0.;goal=float(target['hours']);left=max(0,goal-used);rate=min(100,100*used/goal) if goal else 0
            rule=(state.get('shift_rules') or {}).get('work_type',{}).get(target['group'],{});day_hours=float(rule.get('shift_total_hours',rule.get('shift_total_hours_max',8)) or 8)
            col.markdown(f'<div style="min-height:190px;padding:17px;border-radius:17px;border:1px solid #d8e6ec;border-top:4px solid #398d95;background:#f8fbfc"><small style="color:#5c7681">{target["start"]} → {target["end"]}</small><h4 style="margin:5px 0 12px;color:#315e6e">{WORK_LABELS.get(target["group"],target["group"])}</h4><div style="font-size:26px;font-weight:800;color:#2d8490">%{rate:.1f}</div><div style="height:7px;background:#e4edef;border-radius:9px;margin:8px 0"><div style="height:7px;width:{rate:.1f}%;background:#398d95;border-radius:9px"></div></div><div style="font-size:12px;line-height:1.8;color:#647983">Kişi başı: <b>{used:.1f} / {goal:.1f} saat</b><br>Kalan: <b>{left:.1f} saat</b> · Yaklaşık <b>{left/day_hours if day_hours else 0:.1f} gün</b><br>Personel: <b>{len(group_people)}</b></div></div>',unsafe_allow_html=True)
    labels={i:f"{WORK_LABELS.get(t['group'],t['group'])} · {t['start']} → {t['end']} · {t['hours']:g} saat/kişi" for i,t in enumerate(targets)}
    chosen=st.selectbox('İncelenecek çalışma hedefi',list(labels),format_func=labels.get,key='capacity_target_detail_pick')
    target=targets[chosen]
    group_people=[p for p in agents if p.get('work_type')==target['group']]
    left,right=st.columns([1,1.35],vertical_alignment='top')
    with left:
        st.markdown(f'<div style="padding:18px;border:1px solid #d8e7ec;border-radius:18px;background:linear-gradient(145deg,#f2fafb,#fff)"><small style="color:#52717f;font-weight:750">SEÇİLİ HEDEF</small><h3 style="margin:6px 0;color:#2f6674">{WORK_LABELS.get(target["group"],target["group"])}</h3><div style="font-size:13px;color:#68808a">{target["start"]} → {target["end"]}</div><div style="font-size:28px;font-weight:800;color:#218698;margin-top:13px">{target["hours"]:g} saat <small style="font-size:12px">/ kişi</small></div></div>',unsafe_allow_html=True)
        dates=st.date_input('Grafikte incelenecek tarih aralığı',(pd.Timestamp(target['start']).date(),pd.Timestamp(target['end']).date()),min_value=pd.Timestamp(target['start']).date(),max_value=pd.Timestamp(target['end']).date(),key='hours_history_range')
        if len(dates)!=2:return
        selected=personnel_hours(state,group_people,*dates,published_only=False)
        full=personnel_hours(state,group_people,target['start'],target['end'],published_only=False)
        if full.empty:st.info('Bu hedefte aktif personel bulunamadı.');return
        avg_selected=float(selected['Toplam saat'].mean()) if not selected.empty else 0.;avg_used=float(full['Toplam saat'].mean());avg_left=max(0,float(target['hours'])-avg_used)
        shift_rule=(state.get('shift_rules') or {}).get('work_type',{}).get(target['group'],{});day_hours=float(shift_rule.get('shift_total_hours',shift_rule.get('shift_total_hours_max',8)) or 8)
        possible_days=avg_left/day_hours if day_hours else 0
        st.markdown(f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:12px"><div style="padding:12px;border-radius:13px;background:#eef7f9"><small>Seçili aralık / kişi</small><br><b>{avg_selected:.1f} saat</b></div><div style="padding:12px;border-radius:13px;background:#f3f0fa"><small>Aktif personel</small><br><b>{len(group_people)} kişi</b></div><div style="padding:12px;border-radius:13px;background:#f7f5ec"><small>Kalan / kişi</small><br><b>{avg_left:.1f} saat</b></div><div style="padding:12px;border-radius:13px;background:#eef7f1"><small>Yazılabilir ort. gün</small><br><b>{possible_days:.1f} gün</b></div></div>',unsafe_allow_html=True)
    with right:
        import altair as alt
        count=max(1,len(group_people));total_target=float(target['hours'])*count;total_used=float(full['Toplam saat'].sum());total_left=max(0,total_target-total_used)
        def ring(label,used,total,color,center,note):
            ratio=min(1.,used/total) if total else 0.;data=pd.DataFrame({'Tür':['Planlanan','Kalan'],'Değer':[ratio,1-ratio]})
            arc=alt.Chart(data).mark_arc(innerRadius=63,outerRadius=82,cornerRadius=5).encode(theta='Değer:Q',color=alt.Color('Tür:N',scale=alt.Scale(domain=['Planlanan','Kalan'],range=[color,'#e8eef2']),legend=None))
            text=alt.Chart(pd.DataFrame({'Yazı':[center]})).mark_text(fontSize=22,fontWeight='bold',color='#294e5f').encode(text='Yazı:N')
            st.markdown(f'<div style="text-align:center;font-weight:750;color:#315b6b">{label}</div>',unsafe_allow_html=True);st.altair_chart((arc+text).properties(height=190),use_container_width=True);st.markdown(f'<div style="text-align:center;font-size:12px;color:#6d818b;margin-top:-18px">{note}</div>',unsafe_allow_html=True)
        a,b=st.columns(2)
        with a:ring('Kişi başı ortalama',avg_used,float(target['hours']),'#258e9d',f'%{100*min(1,avg_used/float(target["hours"])):.1f}' if target['hours'] else '%0',f'{avg_used:.1f} sa planlandı · {avg_left:.1f} sa kaldı')
        with b:ring('Toplam grup kapasitesi',total_used,total_target,'#7768ad',f'%{100*min(1,total_used/total_target):.1f}' if total_target else '%0',f'{total_used:.1f} / {total_target:.1f} kişi-saat · {total_left:.1f} sa kaldı')
        chart=selected.set_index('Personel')['Toplam saat'].sort_values() if not selected.empty else pd.Series(dtype=float)
        if not chart.empty:st.bar_chart(chart,color='#4b95a3',height=250)
    with st.expander('Çalışma süresi hedeflerini yönet'):render_targets(state)


def render_targets(state):
    st.markdown('### Gruplara Çalışma Süresi Tanımla')
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

# Vardiya Plani / Donem Secimi — bu ekranın / servisin uygulama kodu.
import streamlit as st
import pandas as pd
from datetime import date, timedelta


def _week_range(d: date):
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start, end


def _clamp_range(start: date, end: date, min_date: date, max_date: date):
    s = max(start, min_date)
    e = min(end, max_date)
    if s > e:
        s, e = min_date, max_date
    return s, e


def _init_ctx(min_date: date):
    start, end = _week_range(min_date)
    st.session_state.setdefault("plan_ctx", {"start": start, "end": end})
    st.session_state.setdefault("plan_ctx_confirmed", False)


def _load_staffing_df():
    df_all = st.session_state.get("sp_staffing_result_df")
    if df_all is None or not isinstance(df_all, pd.DataFrame) or df_all.empty:
        return None
    df = df_all.copy()
    df["Tarih"] = pd.to_datetime(df["Tarih"]).dt.date
    return df



def render():
    from ortak.calisma_alani_deposu import save_keys
    from ortak.cagri_tahmin_servisi import DAY_NAMES
    from ortak.grafikler import daily_chart
    st.subheader('Plan Dönemi')
    df=_load_staffing_df()
    if df is None:
        st.info('Önce Mesai Planı → Personel Hesap ekranında ihtiyacı hesaplayın.');return
    dates=sorted(df.Tarih.unique());minimum,maximum=dates[0],dates[-1]
    _init_ctx(minimum)
    ctx=st.session_state['plan_ctx']
    current_start,current_end=_clamp_range(pd.Timestamp(ctx['start']).date(),pd.Timestamp(ctx['end']).date(),minimum,maximum)
    with st.container(border=True):
        st.markdown('#### Planlayacağın aralığı seç')
        a,b=st.columns(2)
        with a.container(border=True):
            st.markdown('**BAŞLANGIÇ TARİHİ**');start=st.date_input('Başlangıç',value=current_start,min_value=minimum,max_value=maximum,key=f'vp_start_{minimum}_{maximum}',format='DD.MM.YYYY',label_visibility='collapsed')
        with b.container(border=True):
            st.markdown('**BİTİŞ TARİHİ**');end=st.date_input('Bitiş',value=current_end,min_value=minimum,max_value=maximum,key=f'vp_end_{minimum}_{maximum}',format='DD.MM.YYYY',label_visibility='collapsed')
        if end<start:st.error('Bitiş tarihi başlangıçtan önce olamaz.');return
        if (end-start).days>92:st.error('Tek plan dönemi en fazla 93 gün olabilir.');return
        if (ctx['start'],ctx['end'])!=(start,end):
            st.session_state['plan_ctx_confirmed']=False
        st.session_state['plan_ctx']={'start':start,'end':end}
        confirmed=st.session_state.get('plan_ctx_confirmed',False)
        st.markdown(f"### {start:%d.%m.%Y} → {end:%d.%m.%Y}")
        st.caption(f'{(end-start).days+1} gün · İhtiyaç verisi {minimum:%d.%m.%Y} – {maximum:%d.%m.%Y} aralığında hazır.')
        if confirmed:
            st.success('Dönem onaylı · Vardiya Saatleri ve Oluştur ekranları bu aralığı kullanır.')
        else:
            st.info('Bu dönemi onaylayarak planlamaya devam et.')
        c1,c2,_=st.columns([1,1,2])
        def confirm(value):
            st.session_state['plan_ctx_confirmed']=value;save_keys(st.session_state)
        c1.button('Dönemi Onayla',type='primary',key='vp_confirm',on_click=confirm,args=(True,))
        c2.button('Onayı Kaldır',disabled=not confirmed,key='vp_unconfirm',on_click=confirm,args=(False,))
    base=df[df.Tarih.between(start,end)].copy()
    if base.empty:
        st.warning('Seçilen dönemde ihtiyaç yok.');return
    import html
    columns=st.columns(5)
    metrics=[('Planlanacak gün',str((end-start).days+1)),('Min. ihtiyaç',str(int(base['Planlanan Agent'].min()))),('Ort. ihtiyaç',f"{base['Planlanan Agent'].mean():.1f}"),('En yoğun dilim',str(int(base['Planlanan Agent'].max()))),('Tahmini çağrı',f"{base.get('Tahmin Çağrı',pd.Series(dtype=float)).sum():,.0f}")]
    for col,(label,value) in zip(columns,metrics):
        with col:st.markdown(f'<div class="period-kpi"><div>{html.escape(label)}</div><strong>{value}</strong></div>',unsafe_allow_html=True)
    st.markdown('<style>.period-kpi{border:1px solid #d9e3ec;border-radius:15px;padding:14px;height:112px;text-align:center;background:#f9fbfd;color:#234252}.period-kpi>div{font-size:13px;font-weight:650;height:35px}.period-kpi strong{font-size:25px}.day-card{height:144px;border:1px solid #d9e3ec;border-radius:14px;padding:12px;text-align:center;color:#234252;background:#f8fbfd}.day-card b{display:block;font-size:15px}.day-card .date{font-size:17px;font-weight:750;margin:5px}.day-card small{font-size:11px;display:block;line-height:21px}</style>',unsafe_allow_html=True)
    daily=base.groupby('Tarih',as_index=False).agg(**{'Zirve ihtiyaç':('Planlanan Agent','max'),'Ortalama ihtiyaç':('Planlanan Agent','mean'),'Min. ihtiyaç':('Planlanan Agent','min')})
    st.markdown('### Haftanın İhtiyaç Görünümü')
    from ortak.grafikler import daily_chart
    daily_chart(daily,'Tarih',['Min. ihtiyaç','Ortalama ihtiyaç','Zirve ihtiyaç'],height=260,y_title='Personel ihtiyacı')
    for offset in range(0,len(daily),7):
        cols=st.columns(7)
        for col,record in zip(cols,daily.iloc[offset:offset+7].to_dict('records')):
            day=record['Tarih']
            col.markdown(f'<div class="day-card"><b>{DAY_NAMES[day.weekday()]}</b><div class="date">{day:%d.%m.%Y}</div><small>Min: {record["Min. ihtiyaç"]:.0f}</small><small>Ort: {record["Ortalama ihtiyaç"]:.1f}</small><small>Zirve: {record["Zirve ihtiyaç"]:.0f}</small></div>',unsafe_allow_html=True)
        st.markdown('')
    with st.expander('30 dakikalık ihtiyaç tablosu'):
        from ortak.saat_etiketleri import slot_label
        days=sorted(base.Tarih.unique())
        for offset in range(0,len(days),3):
            columns=st.columns(3)
            for col,day in zip(columns,days[offset:offset+3]):
                with col:
                    with st.container(border=True):
                        st.markdown(f"**{day:%d.%m.%Y} {DAY_NAMES[day.weekday()]}**")
                    view=base[base.Tarih==day].copy().sort_values('Slot');view['Saat aralığı']=view.Slot.map(slot_label)
                    st.dataframe(view[['Saat aralığı']+[c for c in ['Planlanan Agent','Net Agent','Tahmin Çağrı'] if c in view]],hide_index=True,use_container_width=True,height=400)

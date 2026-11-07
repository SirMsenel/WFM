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
    from core.workspace_store import save_keys
    from core.forecast_service import DAY_NAMES
    from core.charts import daily_chart
    st.subheader('Plan Dönemi')
    df=_load_staffing_df()
    if df is None:
        st.info('Önce Mesai Planı → Personel Hesap ekranında ihtiyacı hesaplayın.');return
    dates=sorted(df.Tarih.unique());minimum,maximum=dates[0],dates[-1]
    _init_ctx(minimum)
    ctx=st.session_state['plan_ctx']
    current_start,current_end=_clamp_range(ctx['start'],ctx['end'],minimum,maximum)
    with st.container(border=True):
        a,b=st.columns([1,2])
        mode=a.radio('Planlama aralığı',['Haftalık','Özel Aralık'],horizontal=True,key='vp_period_mode_v2')
        if mode=='Haftalık':
            anchor=b.date_input('Planlamak istediğin haftadan bir gün seç',value=current_start,min_value=minimum,max_value=maximum,key='vp_week_anchor_v2')
            start,end=_clamp_range(*_week_range(anchor),minimum,maximum)
        else:
            picked=b.date_input('Başlangıç – bitiş',value=(current_start,current_end),min_value=minimum,max_value=maximum,key='vp_custom_range_v2')
            if len(picked)!=2:
                st.info('Başlangıç ve bitiş tarihini seçin.');return
            start,end=picked
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
        if c1.button('Dönemi Onayla',type='primary',key='vp_confirm'):
            st.session_state['plan_ctx_confirmed']=True
            save_keys(st.session_state);st.rerun()
        if c2.button('Onayı Kaldır',disabled=not confirmed,key='vp_unconfirm'):
            st.session_state['plan_ctx_confirmed']=False
            save_keys(st.session_state);st.rerun()
    base=df[df.Tarih.between(start,end)].copy()
    if base.empty:
        st.warning('Seçilen dönemde ihtiyaç yok.');return
    a,b,c=st.columns(3)
    a.metric('Planlanacak gün',(end-start).days+1)
    b.metric('En yoğun dilimde ihtiyaç',int(base['Planlanan Agent'].max()))
    c.metric('Tahmini çağrı',f"{base.get('Tahmin Çağrı',pd.Series(dtype=float)).sum():,.0f}")
    daily=base.groupby('Tarih',as_index=False).agg(**{'Zirve ihtiyaç':('Planlanan Agent','max'),'Ortalama ihtiyaç':('Planlanan Agent','mean')})
    st.markdown('### Haftanın İhtiyaç Görünümü')
    daily_chart(daily,'Tarih',['Zirve ihtiyaç','Ortalama ihtiyaç'],height=220,y_title='Personel ihtiyacı')
    if len(daily)<=7:
        columns=st.columns(len(daily))
        for col,record in zip(columns,daily.to_dict('records')):
            day=record['Tarih']
            with col.container(border=True):
                st.caption(DAY_NAMES[day.weekday()]);st.write(f'**{day:%d.%m}**')
                st.metric('Zirve',int(record['Zirve ihtiyaç']))
    with st.expander('30 dakikalık ihtiyaç tablosu'):
        st.dataframe(base[[c for c in ['Tarih','Gün','Aralık','Planlanan Agent','Net Agent','Tahmin Çağrı'] if c in base]],hide_index=True,use_container_width=True)

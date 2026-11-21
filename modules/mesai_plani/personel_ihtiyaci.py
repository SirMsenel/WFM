# Mesai Plani / Personel Ihtiyaci — bu ekranın / servisin uygulama kodu.
import math
import pandas as pd
import streamlit as st


# ==========================================================
# Erlang C Fonksiyonları
# ==========================================================

def erlang_c_probability(a: float, m: int) -> float:
    if m <= 0:
        return 1.0
    if m <= a:
        return 1.0

    # Stable Erlang-B recurrence, then B -> C; avoids factorial overflow.
    b = 1.0
    for k in range(1, m+1):
        b = a*b/(k+a*b)
    rho = a/m
    return float(b/(1-rho+rho*b))


def erlang_c_metrics_for_m(
    calls: float,
    aht_sec: float,
    interval_sec: float,
    m: int,
    target_time_sec: float,
) -> tuple[float, float, float]:
    if calls <= 0 or aht_sec <= 0 or interval_sec <= 0:
        return (0.0, 1.0, 0.0)

    arrival_rate = calls / interval_sec
    a = arrival_rate * aht_sec

    if m <= 0:
        return (a, 0.0, 1.0)

    if m<=a:return (a,0.0,1.0)
    pw = erlang_c_probability(a, m)

    if aht_sec > 0:
        sl = 1 - pw * math.exp(-(m - a) * (target_time_sec / aht_sec))
    else:
        sl = 0.0

    occ = (a / m) if m > 0 else 1.0
    return (float(a), float(sl), float(occ))


def erlang_c_required_agents(
    calls: float,
    aht_sec: float,
    interval_sec: float,
    target_sl: float,
    target_time_sec: float,
    occ_target: float,
) -> dict:
    if calls <= 0:
        return {"m": 0, "traffic_a": 0.0, "sl": 1.0, "occupancy": 0.0}

    arrival_rate = calls / interval_sec
    a = arrival_rate * aht_sec

    m = max(1, int(math.ceil(a)))

    while True:
        traffic_a, sl, occ = erlang_c_metrics_for_m(
            calls=calls,
            aht_sec=aht_sec,
            interval_sec=interval_sec,
            m=m,
            target_time_sec=target_time_sec,
        )

        if (sl >= target_sl) and (occ <= occ_target):
            return {"m": m, "traffic_a": traffic_a, "sl": sl, "occupancy": occ}

        m += 1


# ==========================================================
# UI
# ==========================================================

def calculate_staffing(forecast_df, ratio_df, aht=300, target_sl=.8,
                       target_time=20, shrinkage=.3, occ_target=.85, slot_shrinkage=None):
    from ortak.cagri_tahmin_servisi import validate_forecast, DAY_NAMES
    forecast=validate_forecast(forecast_df)
    if not (0 < aht <= 3600 and 0 < target_sl < 1 and 0 <= shrinkage < 1 and 0 < occ_target < 1 and target_time>0):
        raise ValueError("Geçersiz personel hesaplama parametreleri.")
    if not {'Gün','Slot','Oran(%)'} <= set(ratio_df):
        raise ValueError("Oran profilinde Gün, Slot ve Oran(%) gerekli.")
    if ratio_df.duplicated(['Tarih','Slot'] if 'Tarih' in ratio_df else ['Gün','Slot']).any():
        raise ValueError("Oran profilinde aynı gün/slot birden fazla kez var.")
    rows=[]
    for row in forecast.itertuples(index=False):
        day=DAY_NAMES[row.tarih.weekday()]
        profile=ratio_df[ratio_df['Gün']==day]
        if 'Tarih' in ratio_df:
            profile=profile[pd.to_datetime(profile.Tarih).dt.normalize()==row.tarih.normalize()]
        if len(profile)!=48 or set(profile.Slot)!=set(range(1,49)):
            raise ValueError(f"{day} için 48 slotun tamamı gerekli.")
        ratios=pd.to_numeric(profile['Oran(%)'],errors='raise')
        if not math.isfinite(float(ratios.sum())) or ratios.isna().any() or (ratios<0).any() or abs(float(ratios.sum())-100)>.05:
            raise ValueError(f"{day} oranlarının toplamı %100 olmalı.")
        for (_,r),percent in zip(profile.iterrows(),ratios):
            calls=float(row.y_pred)*float(percent)/100
            from ortak.statuler import shrinkage_for
            loss=shrinkage_for({"slot_shrinkage":slot_shrinkage or []},row.tarih,int(r["Slot"]),shrinkage)
            met=erlang_c_required_agents(calls,aht,1800,target_sl,target_time,occ_target)
            slot=int(r['Slot'])
            label=r.get('Aralık',f'{(slot-1)//2:02d}:{((slot-1)%2)*30:02d}')
            rows.append({'Tarih':row.tarih.date(),'Gün':day,'Slot':slot,'Aralık':label,
                         'Tahmin Çağrı':round(calls,2),'Trafik (Erlang)':round(met['traffic_a'],3),
                         'Doluluk (%)':round(met['occupancy']*100,1),'SL (model) (%)':round(met['sl']*100,1),
                         'Net Agent':met['m'],'Shrinkage (%)':loss*100,'AHT (sn)':aht,'Hedef SL (%)':target_sl*100,'Hedef süre (sn)':target_time,'Planlanan Agent':math.ceil(met['m']/(1-loss))})
    return pd.DataFrame(rows)

def render():
    st.subheader("👥 Personel Tahmin (Erlang C)")
    st.markdown("---")

    # Gerekli veriler
    if st.session_state.get("sp_forecast_df") is None:
        st.warning("Önce Tahmin Kaynağı ekranında bir model seçin veya elle tahmin girin.")
        return

    if "sp_active_ratio_profile_df" not in st.session_state or st.session_state["sp_active_ratio_profile_df"] is None:
        st.warning("Önce aktif bir 30 dk oran profili seçmelisin (Kayıt Seçim ekranından).")
        return

    forecast_df = st.session_state["sp_forecast_df"].copy()
    ratio_df=st.session_state['sp_active_ratio_profile_df'].copy()
    first=pd.to_datetime(forecast_df.tarih).min().date();last=pd.to_datetime(forecast_df.tarih).max().date()
    st.markdown('#### Interval profilinin uygulanacağı dönem')
    a,b=st.columns(2)
    start=a.date_input('Başlangıç',value=first,min_value=first,max_value=last,key=f'staffing_start_{first}_{last}',format='DD.MM.YYYY')
    end=b.date_input('Bitiş',value=last,min_value=first,max_value=last,key=f'staffing_end_{first}_{last}',format='DD.MM.YYYY')
    if start is None or end is None:st.warning('Başlangıç ve bitiş tarihlerini seçin.');return
    if end<start:st.error('Bitiş tarihi başlangıçtan önce olamaz.');return
    forecast_df=forecast_df[pd.to_datetime(forecast_df.tarih).dt.date.between(start,end)].copy()
    if 'Tarih' in ratio_df:ratio_df=ratio_df.sort_values('Tarih').drop(columns='Tarih').drop_duplicates(['Gün','Slot'],keep='last')

    if forecast_df.empty or ratio_df.empty:
        st.error("Tahmin veya oran profili boş.")
        return

    # ======================================================
    # Parametreler
    # ======================================================
    st.markdown("### ⚙️ Parametreler")

    default_mode='30 dk kuralları' if st.session_state.get('slot_shrinkage') else 'Genel oran'
    # Kalıcı ayar ile widget anahtarını ayır. Aynı anahtarın hem servis hem
    # Streamlit widget'ı tarafından yazılması WidgetAlreadyInstantiated
    # hatasına yol açıyordu.
    persisted_mode=st.session_state.get('staffing_shrinkage_mode',default_mode)
    pending_mode=st.session_state.pop('_staffing_shrinkage_mode_pending',None)
    if pending_mode in {'Genel oran','30 dk kuralları','Geçmiş öneri'}:st.session_state['staffing_shrinkage_mode_input']=pending_mode
    st.session_state.setdefault('staffing_shrinkage_mode_input',persisted_mode)
    shrinkage_mode=st.segmented_control('Shrinkage kaynağı',['Genel oran','30 dk kuralları','Geçmiş öneri'],key='staffing_shrinkage_mode_input') or persisted_mode
    st.session_state['staffing_shrinkage_mode']=shrinkage_mode
    active_slot_rules=shrinkage_mode!='Genel oran'
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        aht = st.slider("AHT (sn)", 60, 600, 300, 5)
    with c2:
        sl_percent = st.slider("Service Level (%)", 50, 95, 80, 5)
    with c3:
        target_time = st.slider("Hedef Süre (sn)", 5, 60, 20, 5)
    with c4:
        configured=[float(item.get('rate',0))*100 for item in st.session_state.get('slot_shrinkage',[])]
        fallback=max(0,min(50,int(round(sum(configured)/len(configured))) if configured else 30))
        shrinkage_percent = st.slider("Shrinkage (%)", 0, 50, fallback, 5,disabled=active_slot_rules)
        if active_slot_rules:st.caption('Yarım saatlik shrinkage kuralları aktif; genel oran yalnızca kuralı olmayan dilimlerde yedek değerdir.')

    with st.expander('Geçmiş statü kullanımına göre Shrinkage önerisi'):
        from datetime import date,timedelta
        from ortak.statu_gecmisi import suggested_shrinkage
        # Örnek veri tarihini değil, uygulamanın açıldığı güne kadar oluşan geçmişi
        # kullan. Böylece demo ilerleyen tarihlerde de öneri üretmeye devam eder.
        end_hist=pd.Timestamp.now(tz='Europe/Istanbul').date()-timedelta(days=1)
        history_range=st.date_input('Öneri için geçmiş aralık',(end_hist-timedelta(days=183),end_hist),key='shrinkage_history_dates')
        if len(history_range)==2:
            if st.button('Geçmiş Kullanımı İncele',key='shrinkage_suggest'):
                with st.spinner('Yemek, mola ve koçluk süreleri ölçülüyor…'):table,overall,synthetic=suggested_shrinkage(st.session_state,*history_range,by_weekday=True)
                st.session_state['shrinkage_history_proposal']=(table,overall,synthetic)
            proposal=st.session_state.get('shrinkage_history_proposal')
            if proposal:
                table,overall,synthetic=proposal
                if synthetic:st.info('Öneri sentetik statü gerçekleşmelerine dayanır; gerçek kurum kaybı değildir.')
                st.metric('Önerilen ortalama shrinkage',f'%{overall:.2f}' if overall is not None else 'Veri yok')
                st.caption('Bu oran, geçmişte yemek + mola + koçluğa ayrılan sürenin toplam vardiya süresindeki payıdır. Hafta sonu gibi daha az personelin çalıştığı günler kendi geçmişiyle değerlendirilir; her hafta günü ve yarım saat için ayrı öneri oluşur.')
                if 'Gün' in table:
                    daily=table.groupby('Gün',sort=False)[['Çalışma kişi-saat','Statü kişi-saat']].sum()
                    daily['Kayıp (%)']=100*daily['Statü kişi-saat']/daily['Çalışma kişi-saat'].replace(0,float('nan'))
                    st.bar_chart(daily['Kayıp (%)'],color='#259c99')
                    pick=st.selectbox('İncelenecek gün',list(table.Gün.unique()),key='shrinkage_review_weekday');view=table[table.Gün==pick]
                else:view=table
                st.dataframe(view.drop(columns=['Slot','Haftanın günü'],errors='ignore').rename(columns={'Shrinkage (%)':'Önerilen toplam kayıp (%)','Çalışma kişi-saat':'Toplam vardiya süresi (saat)','Statü kişi-saat':'Statülere ayrılan süre (saat)'}).style.format(precision=2,na_rep='Çalışma yok'),hide_index=True,use_container_width=True)
                st.caption('Öneri yalnızca kayıtlı statü kullanımını kapsar. Eğitim, devamsızlık ve benzeri dış kayıplar kurum verisiyle ayrıca eklenmelidir. Öneriyi aşağıdaki yarım saatlik kurallara aktarabilir, sonra istediğin dilimi elle değiştirebilirsin.')
                if st.button('Öneriyi Dilim Oranlarına Aktar',disabled=overall is None,key='shrinkage_adopt'):
                    st.session_state['slot_shrinkage']=[{'start_slot':int(r['Slot']),'end_slot':int(r['Slot']),'rate':min(.95,float(r['Shrinkage (%)'])/100),**({'weekdays':[int(r['Haftanın günü'])]} if 'Haftanın günü' in r else {})} for r in table.to_dict('records') if pd.notna(r['Shrinkage (%)'])];st.session_state.pop('slot_loss_editor_clock',None)
                    st.session_state['staffing_shrinkage_mode']='Geçmiş öneri'
                    st.session_state['_staffing_shrinkage_mode_pending']='Geçmiş öneri'
                    from ortak.calisma_alani_deposu import save_keys
                    save_keys(st.session_state);st.rerun()
    with st.expander('30 dakikalık shrinkage kuralları'):
        st.markdown('<div style="padding:14px 16px;border-radius:15px;background:linear-gradient(120deg,#edf7f8,#f5f2fb);border:1px solid #dce8ed"><b style="color:#315d6e">Yarım Saatlik Kayıp Tasarımı</b><div style="font-size:12px;color:#657a85;margin-top:5px">Gün ve saat aralığına göre yemek, mola, koçluk ve diğer planlı kayıpların toplam oranını belirle.</div></div>',unsafe_allow_html=True)
        existing=st.session_state.get('slot_shrinkage',[])
        clock=lambda n:f'{n//2:02d}:{30*(n%2):02d}'
        starts=[clock(i) for i in range(48)];ends=[clock(i) for i in range(1,49)]
        table=pd.DataFrame([{'Başlangıç':clock(r['start_slot']-1),'Bitiş':clock(r['end_slot']),'Shrinkage (%)':r['rate']*100,'Gün':('Tüm günler' if not r.get('weekdays') else __import__('ortak.cagri_tahmin_servisi',fromlist=['DAY_NAMES']).DAY_NAMES[r['weekdays'][0]])} for r in existing],columns=['Başlangıç','Bitiş','Shrinkage (%)','Gün'])
        if existing:
            avg=sum(float(r.get('rate',0)) for r in existing)/len(existing)*100
            a,b,c=st.columns(3);a.metric('Tanımlı kural',len(existing));b.metric('Ortalama kayıp',f'%{avg:.1f}');c.metric('Kapsanan gün tipi',len({tuple(r.get('weekdays',[])) for r in existing}))
        with st.container(border=True):
            edited=st.data_editor(table,num_rows='dynamic',hide_index=True,use_container_width=True,height=min(420,max(180,74+len(table)*35)),key='slot_loss_editor_clock',column_config={'Gün':st.column_config.SelectboxColumn('Uygulanacak gün',options=['Tüm günler']+list(__import__('ortak.cagri_tahmin_servisi',fromlist=['DAY_NAMES']).DAY_NAMES),required=True,width='medium'),'Başlangıç':st.column_config.SelectboxColumn('Başlangıç',options=starts,required=True,width='small'),'Bitiş':st.column_config.SelectboxColumn('Bitiş',options=ends,required=True,width='small'),'Shrinkage (%)':st.column_config.NumberColumn('Toplam kayıp (%)',min_value=0,max_value=99,step=1,required=True,width='medium')})
            st.caption('Yeni satır ekleyebilir veya gereksiz satırı seçip silebilirsin. Çakışan kurallarda en alttaki satır uygulanır.')
        if st.button('Dilim Oranlarını Kaydet',key='save_slot_loss'):
            try:
                rows=[]
                if edited.isna().any().any():raise ValueError('Shrinkage tablosu boş kalamaz. Başlangıç, bitiş ve kayıp yüzdesini doldurun veya eksik satırı silin.')
                for r in edited.to_dict('records'):
                    a,b=starts.index(r['Başlangıç'])+1,ends.index(r['Bitiş'])+1;rate=float(r['Shrinkage (%)'])/100
                    if not 1<=a<=b<=48 or not 0<=rate<1:raise ValueError('Bitiş başlangıçtan sonra, kayıp %0–99 arasında olmalı.')
                    rows.append({'start_slot':a,'end_slot':b,'rate':rate,**({'weekdays':[list(__import__('ortak.cagri_tahmin_servisi',fromlist=['DAY_NAMES']).DAY_NAMES).index(r['Gün'])]} if r['Gün']!='Tüm günler' else {})})
                st.session_state['slot_shrinkage']=rows
                st.session_state['staffing_shrinkage_mode']='30 dk kuralları'
                st.session_state['_staffing_shrinkage_mode_pending']='30 dk kuralları'
                from ortak.calisma_alani_deposu import save_keys
                save_keys(st.session_state);st.success('Dilim kayıpları kaydedildi. Genel shrinkage oranı devre dışı bırakıldı.');st.rerun()
            except ValueError as e:st.error(str(e))
    occ_percent = st.slider("Doluluk / Occupancy Hedefi (%)", 50, 95, 85, 5)
    st.caption("Doluluk = Trafik (Erlang) / Agent. Hedef %85 ise, sistem doluluk %85’i aşmayacak şekilde agent artırır.")

    st.markdown("---")

    # ======================================================
    # Hesap
    # ======================================================
    interval_sec = 1800
    target_sl = sl_percent / 100
    shrinkage = shrinkage_percent / 100
    occ_target = occ_percent / 100

    forecast_df["tarih"] = pd.to_datetime(forecast_df["tarih"])

    # Gün adı (TR)
    day_map = {
        "Monday": "Pazartesi",
        "Tuesday": "Salı",
        "Wednesday": "Çarşamba",
        "Thursday": "Perşembe",
        "Friday": "Cuma",
        "Saturday": "Cumartesi",
        "Sunday": "Pazar",
    }
    forecast_df["Gün"] = forecast_df["tarih"].dt.day_name().map(day_map)

    if st.button("🚀 Personel İhtiyacını Hesapla ve Kaydet", use_container_width=True):
        from ortak.donem_uyarisi import popup
        if popup(st.session_state,start,end):return
        try:
            with st.spinner("Personel ihtiyacı hesaplanıyor..."):
                active_rules=st.session_state.get("slot_shrinkage",[]) if shrinkage_mode!='Genel oran' else []
                result_df=calculate_staffing(forecast_df,ratio_df,aht=float(aht),target_sl=target_sl,
                                            target_time=float(target_time),shrinkage=shrinkage,occ_target=occ_target,slot_shrinkage=active_rules)
            st.session_state["staffing_parameters"]={"aht":float(aht),"target_sl":target_sl,"target_time":float(target_time),"shrinkage":shrinkage,"occ_target":occ_target}
            st.session_state["sp_staffing_result_df"] = result_df
            from ortak.interval_servisi import record_used_profile
            record_used_profile(st.session_state,forecast_df,ratio_df)
            from ortak.calisma_alani_deposu import save_keys
            save_keys(st.session_state)
        except ValueError as exc:
            st.error(str(exc))
            return
        st.success("✅ Personel tahmini hesaplandı ve kaydedildi.")

    # ======================================================
    # Slot Bazlı Görünüm (Seçim + Özet + Grafik + Tablo)
    # ======================================================
    st.markdown("---")
    st.subheader("📈 Gün İçi Personel Görünümü")

    df_all = st.session_state.get("sp_staffing_result_df")
    if df_all is None or not isinstance(df_all, pd.DataFrame) or df_all.empty:
        st.info("Grafik ve tablo için önce hesaplama yapmalısın.")
        return

    df_all = df_all.copy()
    df_all["Tarih"] = pd.to_datetime(df_all["Tarih"])

    all_dates = sorted(df_all["Tarih"].dt.date.unique().tolist())
    if not all_dates:
        st.info("Tarih bulunamadı.")
        return

    # Tarih label
    date_labels, date_map2 = [], {}
    for d in all_dates:
        d_ts = pd.to_datetime(d)
        gun_tr = day_map.get(d_ts.day_name(), d_ts.day_name())
        label = f"{d} • {gun_tr}"
        date_labels.append(label)
        date_map2[label] = d

    with st.container(border=True):
        a,b,c=st.columns([1.45,2.2,1.2],vertical_alignment='bottom')
        picked_label=a.selectbox('İncelenecek gün',date_labels,index=0,key='sp_staff_pick_date')
        picked_date=date_map2[picked_label]
        metric_choice=b.segmented_control('Ana grafik metriği',['Planlanan Agent','Net Agent','Tahmin Çağrı'],default='Planlanan Agent',key='sp_staff_metric_choice') or 'Planlanan Agent'
        show_calls_overlay=c.toggle('Çağrıyı birlikte göster',value=True,key='sp_staff_show_calls_overlay')

    dff=df_all[df_all['Tarih'].dt.date==picked_date].copy().sort_values('Slot')
    if dff.empty:
        st.info('Seçilen tarihte veri yok.');return
    dff['SlotLabel']=dff['Aralık'].astype(str)
    total_calls=float(dff['Tahmin Çağrı'].sum());max_plan=int(dff['Planlanan Agent'].max());max_net=int(dff['Net Agent'].max())
    avg_occ=float(dff['Doluluk (%)'].mean());avg_sl=float(dff['SL (model) (%)'].mean());peak=dff.sort_values('Planlanan Agent',ascending=False).iloc[0]
    from html import escape
    cards=[('Toplam çağrı',f'{total_calls:,.0f}','Günlük tahmin','#247f91'),('Tepe planlanan',str(max_plan),str(peak['Aralık']),'#6c68a9'),('Tepe net ihtiyaç',str(max_net),'Erlang C','#327e67'),('Ortalama doluluk',f'%{avg_occ:.1f}','Occupancy','#b67b36'),('Ortalama SL',f'%{avg_sl:.1f}','Servis seviyesi','#b05d72')]
    for col,(label,value,note,color) in zip(st.columns(5),cards):
        col.markdown(f'<div style="min-height:116px;padding:16px 17px;border:1px solid {color}35;border-top:4px solid {color};border-radius:17px;background:linear-gradient(145deg,{color}12,#fff);color:#294d5e"><small style="font-weight:750;color:{color}">{escape(label.upper())}</small><div style="font-size:26px;font-weight:800;margin:9px 0 2px">{escape(value)}</div><span style="font-size:12px;color:#6a7f8a">{escape(note)}</span></div>',unsafe_allow_html=True)

    graph_tab,table_tab=st.tabs(['Gün İçi Grafik','30 Dakikalık Detay'])
    with graph_tab:
        with st.container(border=True):
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            fig=make_subplots(specs=[[{'secondary_y':True}]])
            colors={'Planlanan Agent':'#5c6fb1','Net Agent':'#248b78','Tahmin Çağrı':'#c07c38'};main_color=colors[metric_choice]
            fig.add_trace(go.Scatter(x=dff['SlotLabel'],y=dff[metric_choice],mode='lines',line=dict(color=main_color,width=3,shape='spline'),fill='tozeroy',fillcolor=main_color+'20',name=metric_choice,hovertemplate='%{x}<br>%{y:.2f}<extra></extra>'),secondary_y=False)
            if show_calls_overlay and metric_choice!='Tahmin Çağrı':fig.add_trace(go.Bar(x=dff['SlotLabel'],y=dff['Tahmin Çağrı'],name='Tahmin Çağrı',marker_color='#d9a55b',opacity=.32),secondary_y=True)
            fig.update_layout(height=410,margin=dict(l=18,r=18,t=48,b=30),title=dict(text=f'{picked_label} · Kapasite Eğrisi',font=dict(size=18)),plot_bgcolor='#fbfdfe',paper_bgcolor='rgba(0,0,0,0)',legend=dict(orientation='h',y=1.12),hovermode='x unified')
            fig.update_xaxes(title='Yarım saat aralığı',tickangle=-45,showgrid=False,nticks=16)
            fig.update_yaxes(title=metric_choice,gridcolor='#e8eef2',secondary_y=False);fig.update_yaxes(title='Tahmin çağrı',showgrid=False,secondary_y=True)
            st.plotly_chart(fig,use_container_width=True)
    with table_tab:
        show_cols=['Aralık','Tahmin Çağrı','Trafik (Erlang)','Doluluk (%)','SL (model) (%)','Net Agent','Shrinkage (%)','Planlanan Agent']
        styled=dff[show_cols].style.format({'Tahmin Çağrı':'{:.2f}','Trafik (Erlang)':'{:.2f}','Doluluk (%)':'{:.2f}','SL (model) (%)':'{:.2f}','Shrinkage (%)':'{:.2f}'}).background_gradient(subset=['Planlanan Agent'],cmap='PuBu').background_gradient(subset=['SL (model) (%)'],cmap='BuGn')
        st.dataframe(styled,use_container_width=True,hide_index=True,height=520)

    # ======================================================
    # Tüm Sonuç Tablosu (Search + Sayfalama)
    # ======================================================
    st.markdown("---")
    st.subheader("📚 Tüm Sonuç Tablosu")

    toolbar1, toolbar2, toolbar3 = st.columns([2.2, 1.2, 1.2], vertical_alignment="center")
    with toolbar1:
        q = st.text_input("🔎 Ara (tüm kolonlarda)", value="", key="sp_staff_search")
    with toolbar2:
        page_size = st.selectbox("Satır", [24, 48, 72, 96, 144, 192], index=1, key="sp_staff_pagesize")
    with toolbar3:
        st.caption("")

    df_view = df_all.copy()

    if q.strip():
        qq = q.strip().lower()
        mask = df_view.astype(str).apply(lambda s: s.str.lower().str.contains(qq, na=False)).any(axis=1)
        df_view = df_view[mask].copy()

    total_rows = len(df_view)
    total_pages = max(1, int(math.ceil(total_rows / page_size)))

    bar1, bar2 = st.columns([1.2, 2.8], vertical_alignment="center")
    with bar1:
        page = st.number_input("Sayfa", min_value=1, max_value=total_pages, value=1, step=1, key="sp_staff_page")
    with bar2:
        start_i = (page - 1) * page_size
        end_i = min(start_i + page_size, total_rows)
        st.caption(f"Gösterilen: {start_i+1 if total_rows else 0}–{end_i} / {total_rows}")

    df_page = df_view.iloc[start_i:end_i].copy()

    st.dataframe(df_page, use_container_width=True, hide_index=True)

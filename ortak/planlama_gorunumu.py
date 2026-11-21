# Ortak / Planlama Gorunumu — bu ekranın / servisin uygulama kodu.
import math
import pandas as pd
import streamlit as st
from ortak.planlama import shortage_summary


def period_banner(state):
    ctx=state.get('plan_ctx') or {}
    if not ctx.get('start') or not ctx.get('end'):
        st.info('Plan Dönem Seçimi ekranında tarih aralığını belirleyin.');return None
    start,end=pd.Timestamp(ctx['start']),pd.Timestamp(ctx['end'])
    st.markdown(f'<div style="display:inline-block;background:#edf6f9;border:1px solid #cbdfe9;border-radius:12px;padding:10px 18px;font-weight:650;color:#244b60;margin:4px 0 16px">{start:%d.%m.%Y} → {end:%d.%m.%Y} · {(end-start).days+1} gün</div>',unsafe_allow_html=True)
    if not state.get('plan_ctx_confirmed'):
        st.warning('Bu dönem henüz onaylı değil. Plan Dönem Seçimi ekranından onaylayın.')
    return ctx


def coverage_controls(state):
    from ortak.calisma_alani_deposu import save_keys
    state['planning_exclude_early_hours']=st.toggle('03:00–08:00 aralığını ihtiyaç sayacından çıkar',value=state.get('planning_exclude_early_hours',False),key='planning_early_toggle')
    st.caption('Açıldığında bu aralıktaki ihtiyaç eksik/fazla hesabına ve otomatik doldurma hedefine katılmaz. Gece vardiyası ve 07:00 girişleri takvimde korunur; çalışma ve dinlenme saatleri gerçek süreden hesaplanır.')
    save_keys(state)


def _ring(column,label,value,portion,color,note=''):
    with column:
        from html import escape
        portion=max(0.,min(1.,portion))
        degree=round(portion*360,1)
        st.markdown(f'<div style="min-height:226px;padding:15px 11px;border:1px solid {color}2f;border-radius:18px;background:linear-gradient(145deg,{color}0c,#fff);text-align:center"><div style="font-weight:750;font-size:13px;min-height:38px;display:flex;align-items:center;justify-content:center;color:#315363">{escape(label)}</div><div style="width:118px;height:118px;margin:6px auto 10px;border-radius:50%;background:conic-gradient({color} 0deg {degree}deg,#e9eef2 {degree}deg 360deg);display:grid;place-items:center"><div style="width:86px;height:86px;border-radius:50%;background:#fff;display:grid;place-items:center;padding:5px;font-size:17px;font-weight:800;color:#294b5b">{escape(str(value))}</div></div><div style="font-size:11px;color:#71828b;min-height:32px">{escape(note)}</div></div>',unsafe_allow_html=True)


def coverage_summary(result,title='Yerleştirmelerin İhtiyaca Etkisi'):
    coverage=result['coverage']
    if 'Sayaca Dahil' in coverage:coverage=coverage[coverage['Sayaca Dahil']]
    needed=float(pd.to_numeric(coverage['İhtiyaç'],errors='coerce').fillna(0).clip(lower=0).sum())
    assigned=pd.to_numeric(coverage['Atanan'],errors='coerce').fillna(0).clip(lower=0)
    required=pd.to_numeric(coverage['İhtiyaç'],errors='coerce').fillna(0).clip(lower=0)
    served=float(pd.concat([assigned,required],axis=1).min(axis=1).sum());left=max(0.,needed-served)
    excess=float((assigned-required).clip(lower=0).sum());missing=(required-assigned).clip(lower=0);active=required>1e-8
    slots=int(((missing>1e-8)&active).sum());excess_slots=int(((assigned-required)>1e-8).sum());covered_slots=int(((missing<=1e-8)&active).sum());total=int(active.sum());rate=served/needed if needed else 1.
    st.markdown('### '+title)
    first=st.columns(3);second=st.columns(3)
    _ring(first[0],'İhtiyaç karşılama oranı',f'%{100*rate:.1f}',rate,'#14977f','Tüm yarım saatlerde karşılanan toplam ihtiyaç')
    _ring(first[1],'Karşılanan 30 dk ihtiyacı',f'{served:.0f} kişi',rate,'#287f9c',f'Toplam {served/2:.1f} personel-saat')
    _ring(first[2],'Eksik kalan 30 dk ihtiyacı',f'{left:.0f} kişi',left/needed if needed else 0,'#d86c60',f'Toplam {left/2:.1f} personel-saat')
    _ring(second[0],'Tam karşılanan yarım saat',f'{covered_slots} dilim',covered_slots/total if total else 1,'#5588b0',f'Toplam {total} dilim')
    _ring(second[1],'Eksik yarım saat',f'{slots} dilim',slots/total if total else 0,'#e8a33d',f'En yüksek eksik {missing.max():.0f} kişi' if total else '')
    _ring(second[2],'Fazladan planlanan',f'{excess:.0f} kişi',excess/(needed+excess) if needed+excess else 0,'#3d9a6b',f'{excess_slots} yarım saat · {excess/2:.1f} personel-saat')
    if excess:st.info('Yeşil + hücreler ihtiyacın üzerinde planlanan kapasiteyi gösterir. Yeni otomatik atamalar tanımlı fazla personel sınırını korur.')
    if result.get('breaks') is not None and result.get('staff'):
        from ortak.statu_haklari import balance
        rights=balance(st.session_state,result.get('plan',[]),result['staff'],result['breaks'])
        meal=[r for r in result['breaks'] if r.get('kind')=='Yemek']
        breaks=[r for r in result['breaks'] if r.get('kind')=='Mola']
        coaching=[r for r in result['breaks'] if r.get('kind')=='Koçluk Alanı']
        def minutes(items):return sum((pd.Timestamp(r['end'])-pd.Timestamp(r['start'])).total_seconds()/60 for r in items if r.get('start') and r.get('end'))
        st.markdown('#### Planlanan Statüler ve Kalan Kapasite')
        status_values=[('Yemek planı',len({str(r['employee_id']) for r in meal}),minutes(meal),'#258f94','kişi'),('Mola planı',len({str(r['employee_id']) for r in breaks}),minutes(breaks),'#7c69b0','kişi'),('Shrinkage açığı','—' if any(r.get('Kural hatası') for r in rights) else f"{sum(r['Eksik (dk)'] for r in rights):.0f}",sum(r['Eksik (dk)'] for r in rights),'#c07845','dk'),('Açık koçluk',sum(int(x.get('remaining_capacity',1)) for x in coaching),minutes(coaching),'#398a60','adet')]
        for col,(label,count,total,color,unit) in zip(st.columns(4),status_values):
            second_label='Kural düzeltilmeli' if count=='—' else (f'{total:.0f} dakika' if unit!='dk' else 'dağıtılamayan süre')
            col.markdown(f'<div style="min-height:154px;padding:16px;border-radius:17px;border:1px solid {color}36;border-top:4px solid {color};background:{color}0d"><b style="color:{color};font-size:13px">{label}</b><div style="font-size:27px;font-weight:800;color:#294c5b;margin-top:13px">{count} <small style="font-size:12px">{unit}</small></div><div style="margin-top:8px;color:#6c7f89;font-size:12px">{second_label}</div></div>',unsafe_allow_html=True)
        missing_rights=[r for r in rights if r['Eksik (dk)'] or r['Fazla (dk)'] or r.get('Kural hatası')]
        if missing_rights:st.dataframe(pd.DataFrame(missing_rights).drop(columns=['employee_id']).rename(columns={'date':'Tarih'}),hide_index=True,use_container_width=True)
    if 'Shrinkage statü bütçesi' in coverage and 'Mola kaybı' in coverage:
        from ortak.modern_kartlar import metric_cards
        budget_units=float(coverage['Shrinkage statü bütçesi'].sum());planned_units=float(coverage['Mola kaybı'].sum())
        over=(coverage['Mola kaybı']-coverage['Shrinkage statü bütçesi']).clip(lower=0)
        st.markdown('#### Statüler Seçilen Kayıp Bütçesine Sığıyor mu?')
        metric_cards([('Statüler için ayrılan kapasite',f'{math.ceil(budget_units)} yarım saatlik birim'),('Yemek ve molanın kullandığı kapasite',f'{math.ceil(planned_units)} yarım saatlik birim'),('Kapasitenin aşıldığı zaman aralığı',f'{int((over>1e-8).sum())} yarım saat')])
        st.caption('Yarım saatlik birim, ilgili 30 dakikada statüye ayrılabilecek bir personellik kapasitedir. Bu değer çalışma süresi veya kişi-saat toplamı değildir.')
        if (over>1e-8).any():st.warning('Bazı yarım saatlerde statü süresi shrinkage bütçesini aşıyor. Bu aşım kapasiteden ayrıca düşüldü; yukarıdaki eksik hesabına dahildir.')
        else:st.caption('Planlanan statüler seçilen shrinkage bütçesi içinde; kapasiteden ikinci kez düşülmez.')


def roster_summary(result,title='Grup Bazlı Plan Özeti'):
    """Taslak ve onay ekranlarında aynı sayım tanımını kullan."""
    from ortak.personel import WORK_LABELS
    from modules.vardiya_plani.vardiya_motoru import bounds
    staff=result.get('staff',[]);rows=result.get('plan',[]);people={str(p['employee_id']):p for p in staff}
    groups=list(dict.fromkeys([p.get('work_type') for p in staff if p.get('work_type')]))
    table=[]
    for group in groups:
        ids={str(p['employee_id']) for p in staff if p.get('work_type')==group};chosen=[r for r in rows if str(r.get('employee_id')) in ids]
        table.append({'Grup':WORK_LABELS.get(group,group),'Aktif kapasite':len(ids),'Planlanan kişi':len({str(r['employee_id']) for r in chosen if bounds(r) is not None}),'Çalışma kaydı':sum(bounds(r) is not None for r in chosen),'OFF':sum(r.get('shift_code')=='OFF' for r in chosen),'Gece':sum(r.get('shift_code')=='GECE' for r in chosen),'Yıllık izin':sum(r.get('shift_code')=='YILLIK_IZIN' for r in chosen),'Rapor':sum(r.get('shift_code')=='RAPOR' for r in chosen)})
    if not table:return
    st.markdown('### '+title)
    totals={key:sum(int(r[key]) for r in table) for key in ['Aktif kapasite','Planlanan kişi','OFF','Gece','Yıllık izin','Rapor']}
    from ortak.modern_kartlar import metric_cards
    metric_cards([(label,totals[label]) for label in ['Aktif kapasite','Planlanan kişi','OFF','Gece','Yıllık izin','Rapor']])
    view=pd.DataFrame(table).style.format(precision=0).background_gradient(subset=['Çalışma kaydı'],cmap='BuGn').background_gradient(subset=['OFF'],cmap='Blues').background_gradient(subset=['Gece'],cmap='Purples')
    st.dataframe(view,hide_index=True,use_container_width=True)


def daily_gap_summary(result,title='Günlük Eksik ve Fazla Özeti'):
    """Onay ekranlarında her günün eksik ve fazla 30 dk kapasitesini göster."""
    from html import escape
    from ortak.cagri_tahmin_servisi import DAY_NAMES
    coverage=result.get('coverage',pd.DataFrame()).copy()
    if coverage.empty:return
    if 'Sayaca Dahil' in coverage:coverage=coverage[coverage['Sayaca Dahil']]
    coverage['Tarih']=pd.to_datetime(coverage['Tarih']).dt.normalize()
    st.markdown('### '+title)
    days=sorted(coverage['Tarih'].unique())
    for offset in range(0,len(days),7):
        for col,raw_day in zip(st.columns(min(7,len(days[offset:offset+7]))),days[offset:offset+7]):
            day=pd.Timestamp(raw_day);frame=coverage[coverage['Tarih']==day]
            need=pd.to_numeric(frame['İhtiyaç'],errors='coerce').fillna(0);assigned=pd.to_numeric(frame['Atanan'],errors='coerce').fillna(0)
            missing=float((need-assigned).clip(lower=0).sum());excess=float((assigned-need).clip(lower=0).sum());scale=max(1.,float(need.sum())+excess)
            missing_deg=min(360.,360*missing/scale);excess_deg=min(360.-missing_deg,360*excess/scale);end=missing_deg+excess_deg
            col.markdown(f'<div style="min-height:215px;padding:13px 8px;border:1px solid #dce7ec;border-radius:17px;background:#fbfdfe;text-align:center"><b style="font-size:13px;color:#365a69">{escape(DAY_NAMES[day.weekday()])}</b><div style="font-size:11px;color:#71828b">{day:%d.%m.%Y}</div><div style="width:112px;height:112px;margin:9px auto;border-radius:50%;background:conic-gradient(#d66c63 0deg {missing_deg:.1f}deg,#3d9a6b {missing_deg:.1f}deg {end:.1f}deg,#e9eef2 {end:.1f}deg 360deg);display:grid;place-items:center"><div style="width:80px;height:80px;border-radius:50%;background:#fff;display:grid;place-items:center;font-size:12px;font-weight:800;color:#36515d"><span><span style="color:#b9524b">−{math.ceil(missing)}</span><br><span style="color:#2d8659">+{math.ceil(excess)}</span></span></div></div><div style="font-size:10px;color:#71828b">Kırmızı eksik · Yeşil fazla<br>30 dakikalık personel toplamı</div></div>',unsafe_allow_html=True)



def shortage_matrix(coverage,start,signed=False):
    from ortak.cagri_tahmin_servisi import DAY_NAMES
    week=pd.Timestamp(start).normalize()
    days=pd.date_range(week,periods=7)
    df=coverage.copy()
    if signed:df['Eksik']=df['Eksik']-df['Fazla']
    if 'Sayaca Dahil' in df:df.loc[~df['Sayaca Dahil'],'Eksik']=float('nan')
    df['Tarih']=pd.to_datetime(df.Tarih).dt.normalize()
    table=df.pivot_table(index='Slot',columns='Tarih',values='Eksik',aggfunc=lambda v:v.sum(min_count=1)).reindex(index=range(1,49),columns=days)
    table.columns=[d.strftime('%d.%m')+' '+DAY_NAMES[d.weekday()] for d in days]
    table.index=[f'{(s-1)//2:02d}:{((s-1)%2)*30:02d}–{s//2:02d}:{(s%2)*30:02d}' for s in range(1,49)]
    table.index.name='Yarım saat';return table


def styled_shortage_matrix(matrix,excess=False,human=False):
    positive=float(matrix.where(matrix>0).max().max()) if (matrix>0).any().any() else 0
    negative=abs(float(matrix.where(matrix<0).min().min())) if (matrix<0).any().any() else 0
    def color(value):
        if pd.isna(value):return 'background-color:#eef2f6;color:#64748b;text-align:center'
        if abs(float(value))<1e-9:return 'background-color:#f4f6f8;color:#657681;text-align:center;font-weight:600'
        if excess and value>0:
            intensity=min(1.,float(value)/max(1.,positive));return f'background-color:rgb({int(235-205*intensity)},{int(250-120*intensity)},{int(240-150*intensity)});color:{"white" if intensity>.5 else "#17533d"};text-align:center'
        if value<0:
            intensity=min(1.,abs(float(value))/max(1.,negative));return f'background-color:rgb({int(228-190*intensity)},{int(248-115*intensity)},{int(232-135*intensity)});color:{"white" if intensity>.5 else "#17533d"};text-align:center;font-weight:650'
        ratio=min(1,float(value)/positive) if positive else 0
        red=255;green=int(247-120*ratio);blue=int(245-120*ratio)
        return f'background-color:rgb({red},{green},{blue});color:{"white" if ratio>.58 else "#6d2424"};text-align:center;font-weight:650'
    styles=matrix.map(color)
    # Staffing is shown as whole people in screens. The optional legacy format
    # stays available for exports/tests that explicitly rely on raw decimals.
    if human:
        display=matrix.map(lambda v:'—' if pd.isna(v) else ('+'+str(math.ceil(abs(float(v)))) if v<0 else str(math.ceil(float(v)))))
    else:
        display=matrix.map(lambda v:'—' if pd.isna(v) else ('+'+f'{abs(v):.2f}' if v<0 else f'{v:.2f}'))
    return display.style.apply(lambda _:styles,axis=None)


def render_shortages(result,key='gap',actions=True):
    coverage=result['coverage'];missing,daily=shortage_summary(coverage)
    st.markdown('### Haftalık Eksik Personel')
    if coverage.empty:st.info('İhtiyaç verisi bulunamadı.');return
    dates=pd.to_datetime(coverage.Tarih)
    first=dates.min().normalize()-pd.Timedelta(days=dates.min().weekday())
    weeks=list(pd.date_range(first,dates.max(),freq='7D'))
    week=st.selectbox('Gösterilecek hafta',weeks,format_func=lambda d:f'{d:%d.%m.%Y} – {d+pd.Timedelta(days=6):%d.%m.%Y}',key=key+'_week') if len(weeks)>1 else first
    selected_days=pd.date_range(week,periods=7);daily_cols=st.columns(7)
    for col,day in zip(daily_cols,selected_days):
        frame=coverage[pd.to_datetime(coverage.Tarih).dt.normalize()==day.normalize()]
        if 'Sayaca Dahil' in frame:frame=frame[frame['Sayaca Dahil']]
        need=float(frame['İhtiyaç'].sum()) if not frame.empty else 0.;served=float(pd.concat([frame['Atanan'],frame['İhtiyaç']],axis=1).min(axis=1).sum()) if not frame.empty else 0.;rate=served/need if need else 1.
        from ortak.cagri_tahmin_servisi import DAY_NAMES
        _ring(col,DAY_NAMES[day.weekday()],f'%{100*rate:.0f}',rate,'#278b83',day.strftime('%d.%m'))
    matrix=shortage_matrix(coverage,week,signed=True)
    st.caption('Kırmızı: eksik kişi · Yeşil +: fazla kişi · 0: ihtiyaç karşılanmış · —: sayaca dahil değil, veri yok veya seçili dönem dışında.')
    st.dataframe(styled_shortage_matrix(matrix,human=True),height=540,use_container_width=True)
    if missing.empty:st.success('Seçili dönemde tüm yarım saatlik ihtiyaç karşılanmış.');return
    if 'Aralık' not in missing:
        missing['Aralık']=missing.Slot.map(lambda s:f'{(s-1)//2:02d}:{((s-1)%2)*30:02d}–{s//2:02d}:{(s%2)*30:02d}')
    cols=[c for c in ['Tarih','Gün','Aralık','İhtiyaç','Atanan','Eksik'] if c in missing]
    view=missing[cols].rename(columns={'İhtiyaç':'Gereken personel','Atanan':'Yerleştirilen','Eksik':'Eksik personel'})
    if actions and (st.session_state.get('profile') or {}).get('position') in {'wfm','manager','assistant_manager','moderator','planning_manager'}:
        from ortak.eksik_aksiyonlari import render_actions
        render_actions(st.session_state,result,key)
    st.download_button('Eksik Dilimleri CSV İndir',view.to_csv(index=False).encode('utf-8-sig'),'eksik_dilimler.csv','text/csv',key=key+'_csv')


def blocking_issues(result):
    return [r for r in result.get('issues',[]) if r.get('severity')!='warning' and not (str(r.get('Sorun','')).startswith('Gece ') and 'kesin kayıt var' in str(r.get('Sorun','')))]


def issue_help(reason):
    if reason.startswith('Gece ') and 'kesin kayıt var' in reason:return ('Gece personel sayısı','O gün için dil bazında tanımlanan gece sayısı ile kayıtlı kişi sayısı farklı.','Gece Kontrolü ekranında kayıtları tamamlayın veya Mesai Kuralları içindeki dil sayısını düzeltin.')
    if 'dinlenme' in reason:return ('11 saat dinlenme','Personelin iki vardiyası arasında yeterli dinlenme yok.','Vardiyalardan birinin başlangıç/bitişini değiştirin; her kişi için en az 11 saat bırakın.')
    if 'Ders/sınav' in reason:return ('Okul takvimiyle çakışma','Çalışma saati ders veya sınav kaydına denk geliyor.','Vardiyayı uygun bir saate/güne taşıyın.')
    if 'süre sınırı' in reason:return ('Vardiya süresi','Kayıt, kişinin grubuna tanımlanan günlük süreyi aşıyor.','Vardiya süresini veya Mesai Kuralları içindeki ilgili süreyi kontrol edin.')
    if 'günü sınırı' in reason:return ('Haftalık gün sınırı','Personel haftalık izin verilen gün sayısından fazla çalışıyor.','İlgili hafta içindeki çalışma günlerini azaltın.')
    if 'çakış' in reason or 'aynı' in reason.casefold():return ('Çakışan kayıt','Aynı personelin kayıtları birbiriyle çakışıyor.','Vardiya Saatleri ve talep kaynaklarında aynı günün kayıtlarını kontrol edin.')
    return ('Kayıt/kural kontrolü',reason,'İlgili personel ve tarihin kaydını Vardiya Saatleri veya Mesai Kuralları ekranında düzeltin.')


def issue_table(result):
    from ortak.personel import WORK_LABELS
    from ortak.planlama import SHIFT_LABELS
    from modules.vardiya_plani.vardiya_motoru import bounds
    staff={str(e['employee_id']):e for e in result.get('staff',[])}
    by_key={(str(r['employee_id']),str(r['date'])):r for r in result.get('plan',[])}
    rows=[];rules=result.get('rules',{})
    for r in result.get('issues',[]):
        eid=str(r.get('employee_id',''));person=staff.get(eid,{})
        group=person.get('work_type','');rule=rules.get('work_type',{}).get(group,{})
        record={**by_key.get((eid,str(r.get('date'))),{}),**{k:v for k,v in r.items() if v is not None}}
        code=record.get('shift_code','');shift=SHIFT_LABELS.get(code,code) or 'Kayıt bulunamadı'
        if record.get('start') and record.get('end'):shift+=f" {record['start']}–{record['end']}"
        reason=str(r.get('Sorun',''));_,_,expected=issue_help(reason)
        if 'dinlenme' in reason:expected=f"İki vardiya arasında en az {max(11,rule.get('min_rest_hours',11)):g} saat dinlenme."
        elif 'Üst üste' in reason:expected=f"En fazla {rule.get('max_consecutive_days',rule.get('max_days_per_week',rule.get('max_days_per_week_default',6)))} gün üst üste çalışma; ardından izin günü."
        elif 'günü sınırı' in reason:expected=f"Pazartesi–Pazar içinde en fazla {rule.get('max_days_per_week',rule.get('max_days_per_week_default',5))} çalışma günü."
        elif 'Günlük süre' in reason:
            hours=rule.get('shift_total_hours',rule.get('shift_total_hours_max'))
            if code=='GECE':expected='Gece aralığı: '+rules.get('general',{}).get('night_window_start','00:00')+'–'+rules.get('general',{}).get('night_window_end','08:00')
            else:expected=f'Günlük en fazla {hours} saat.'
        elif 'Sabit vardiya süresi' in reason:expected=f"Tam vardiya {rule.get('shift_total_hours')} saat olmalı."
        elif 'Gece ' in reason and 'kesin kayıt var' in reason:
            expected=reason.split(':',1)[-1].strip();shift='Gece personel sayısı'
        elif 'Genel başlangıç' in reason:expected='En erken giriş: '+rules.get('general',{}).get('weekday_general_start','08:00')
        elif 'bitiş sınırı' in reason:expected='En geç çıkış: '+str(rule.get('max_end_time') or rules.get('general',{}).get('global_latest_end','03:00'))
        rows.append({'Personel':person.get('full_name',eid or reason.split(':')[0]),'Sicil no':person.get('sicil_no') or eid or '—','Kullanıcı adı':person.get('username','—'),'Grup':WORK_LABELS.get(group,group) or '—',
                     'Tarih':r.get('date'),'Mevcut vardiya':shift,'Uygunsuzluk':reason,'Olması gereken':expected})
    return pd.DataFrame(rows)


def render_issues(result):
    if not result.get('issues'):return
    hard=blocking_issues(result);warning=len(result['issues'])-len(hard)
    st.warning(f'{len(hard)} kayıt düzeltilmeli · {warning} esnek kural / gece sayısı uyarısı. Her satırda mevcut vardiya ve karşılaması gereken kural gösterilir.')
    st.dataframe(issue_table(result),hide_index=True,use_container_width=True)

# Ortak / Planlama Gorunumu — bu ekranın / servisin uygulama kodu.
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


def _ring(column,label,value,portion,color):
    import altair as alt
    with column:
        from html import escape
        st.markdown('<div style="text-align:center;font-weight:600">'+escape(label)+'</div>',unsafe_allow_html=True)
        portion=max(0.,min(1.,portion))
        data=pd.DataFrame({'Tür':['Değer','Kalan'],'Pay':[portion,1-portion]})
        arc=alt.Chart(data).mark_arc(innerRadius=45,outerRadius=59).encode(theta='Pay:Q',color=alt.Color('Tür:N',scale=alt.Scale(domain=['Değer','Kalan'],range=[color,'#e9eef4']),legend=None))
        text=alt.Chart(pd.DataFrame({'Değer':[value]})).mark_text(fontSize=19,fontWeight='bold',color='#24445b').encode(text='Değer:N')
        st.altair_chart((arc+text).properties(height=145),use_container_width=True)


def coverage_summary(result,title='Yerleştirmelerin İhtiyaca Etkisi'):
    coverage=result['coverage']
    if 'Sayaca Dahil' in coverage:coverage=coverage[coverage['Sayaca Dahil']]
    needed=float(coverage['İhtiyaç'].sum());left=float(coverage['Eksik'].sum())
    excess=float(coverage.Fazla.sum());slots=int((coverage.Eksik>0).sum());total=len(coverage)
    st.markdown('### '+title)
    a,b,c,d=st.columns(4)
    _ring(a,'İhtiyacın karşılanan oranı',f'%{100*(needed-left)/needed:.1f}' if needed else '%100',1-left/needed if needed else 1,'#14977f')
    _ring(b,'Eksik çalışma süresi (kişi-saat)',f'{left/2:,.1f}',left/needed if needed else 0,'#e8a33d')
    _ring(c,'Personel açığı bulunan yarım saat',str(slots),slots/total if total else 0,'#dc7760')
    _ring(d,'Fazladan planlanan kişi-saat',f'{excess/2:,.1f}',excess/(needed+excess) if needed+excess else 0,'#8574bf')
    if excess:st.info('Yeşil + hücreler ihtiyacın üzerinde planlanan kapasiteyi gösterir. Yeni otomatik atamalar tanımlı fazla personel sınırını korur.')
    if result.get('breaks') is not None and result.get('staff'):
        from ortak.statu_haklari import balance
        from ortak.modern_kartlar import metric_cards
        rights=balance(st.session_state,result.get('plan',[]),result['staff'],result['breaks'])
        st.markdown('#### Yemek → Tüm Molalar → Operasyon Rezervi → Koçluk')
        metric_cards([('Yemek / mola eksik hakkı',f"{sum(r['Eksik (dk)'] for r in rights):.0f} dk"),('Operasyon rezervi',f"{coverage.get('Operasyon rezervi',pd.Series(dtype=float)).sum()*.5:.2f} kişi-saat"),('Açık koçluk kontenjanı',sum(int(x.get('remaining_capacity',1)) for x in result['breaks'] if x['kind']=='Koçluk Alanı'))])
        missing_rights=[r for r in rights if r['Eksik (dk)'] or r['Fazla (dk)']]
        if missing_rights:st.dataframe(pd.DataFrame(missing_rights).drop(columns=['employee_id']).rename(columns={'date':'Tarih'}),hide_index=True,use_container_width=True)
    if 'Shrinkage statü bütçesi' in coverage and 'Mola kaybı' in coverage:
        from ortak.modern_kartlar import metric_cards
        budget=float(coverage['Shrinkage statü bütçesi'].sum())*.5;planned=float(coverage['Mola kaybı'].sum())*.5
        over=(coverage['Mola kaybı']-coverage['Shrinkage statü bütçesi']).clip(lower=0)
        st.markdown('#### Statüler Seçilen Kayıp Bütçesine Sığıyor mu?')
        metric_cards([('Shrinkage ile ayrılan süre',f'{budget:.2f} kişi-saat'),('Yemek, mola ve koçluk alanları',f'{planned:.2f} kişi-saat'),('Bütçeyi aşan yarım saat',str(int((over>1e-8).sum())))])
        if (over>1e-8).any():st.warning('Bazı yarım saatlerde statü süresi shrinkage bütçesini aşıyor. Bu aşım kapasiteden ayrıca düşüldü; yukarıdaki eksik hesabına dahildir.')
        else:st.caption('Planlanan statüler seçilen shrinkage bütçesi içinde; kapasiteden ikinci kez düşülmez.')



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


def styled_shortage_matrix(matrix,excess=False):
    peak=float(matrix.max().max()) if matrix.notna().any().any() else 0
    def color(value):
        if pd.isna(value):return 'background-color:#eef2f6;color:#64748b;text-align:center'
        if excess and value>=0:
            intensity=min(1.,float(value)/max(1.,peak));return f'background-color:rgb({int(235-205*intensity)},{int(250-120*intensity)},{int(240-150*intensity)});color:{"white" if intensity>.5 else "#17533d"};text-align:center'
        if value<0:
            intensity=min(1.,abs(float(value))/max(1.,abs(float(matrix.min().min()))));return f'background-color:rgb({int(220-190*intensity)},{int(245-115*intensity)},{int(225-135*intensity)});color:{"white" if intensity>.5 else "#17533d"};text-align:center'
        ratio=min(1,float(value)/peak) if peak else 0
        red=255;green=int(247-120*ratio);blue=int(245-120*ratio)
        return f'background-color:rgb({red},{green},{blue});color:#6d2424;text-align:center'
    styles=matrix.map(color)
    display=matrix.map(lambda v:'—' if pd.isna(v) else ('+'+f'{abs(v):.2f}' if v<0 else f'{v:.2f}'))
    return display.style.apply(lambda _:styles,axis=None)


def render_shortages(result,key='gap'):
    coverage=result['coverage'];missing,daily=shortage_summary(coverage)
    st.markdown('### Haftalık Eksik Personel')
    if coverage.empty:st.info('İhtiyaç verisi bulunamadı.');return
    dates=pd.to_datetime(coverage.Tarih)
    first=dates.min().normalize()-pd.Timedelta(days=dates.min().weekday())
    weeks=list(pd.date_range(first,dates.max(),freq='7D'))
    week=st.selectbox('Gösterilecek hafta',weeks,format_func=lambda d:f'{d:%d.%m.%Y} – {d+pd.Timedelta(days=6):%d.%m.%Y}',key=key+'_week') if len(weeks)>1 else first
    matrix=shortage_matrix(coverage,week,signed=True)
    st.caption('Kırmızı: eksik kişi · Yeşil +: fazla kişi · 0: ihtiyaç karşılanmış · —: sayaca dahil değil, veri yok veya seçili dönem dışında.')
    st.dataframe(styled_shortage_matrix(matrix),height=540,use_container_width=True)
    if missing.empty:st.success('Seçili dönemde tüm yarım saatlik ihtiyaç karşılanmış.');return
    if 'Aralık' not in missing:
        missing['Aralık']=missing.Slot.map(lambda s:f'{(s-1)//2:02d}:{((s-1)%2)*30:02d}–{s//2:02d}:{(s%2)*30:02d}')
    cols=[c for c in ['Tarih','Gün','Aralık','İhtiyaç','Atanan','Eksik'] if c in missing]
    view=missing[cols].rename(columns={'İhtiyaç':'Gereken personel','Atanan':'Yerleştirilen','Eksik':'Eksik personel'})
    if (st.session_state.get('profile') or {}).get('position') in {'wfm','manager','assistant_manager','moderator','planning_manager'}:
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

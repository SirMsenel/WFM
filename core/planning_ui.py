import pandas as pd
import streamlit as st
from core.planning import shortage_summary


def period_banner(state):
    ctx=state.get('plan_ctx') or {}
    if not ctx.get('start') or not ctx.get('end'):
        st.info('Plan Dönem Seçimi ekranında tarih aralığını belirleyin.');return None
    start,end=pd.Timestamp(ctx['start']),pd.Timestamp(ctx['end'])
    st.caption(f'Seçili dönem · {start:%d.%m.%Y} – {end:%d.%m.%Y} · {(end-start).days+1} gün')
    if not state.get('plan_ctx_confirmed'):
        st.warning('Bu dönem henüz onaylı değil. Plan Dönem Seçimi ekranından onaylayın.')
    return ctx


def coverage_controls(state):
    from core.workspace_store import save_keys
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
    _ring(a,'Karşılanan ihtiyaç',f'%{100*(needed-left)/needed:.1f}' if needed else '%100',1-left/needed if needed else 1,'#14977f')
    _ring(b,'Kalan personel-saat',f'{left/2:,.1f}',left/needed if needed else 0,'#e8a33d')
    _ring(c,'Eksik olan yarım saat',str(slots),slots/total if total else 0,'#dc7760')
    _ring(d,'Fazla personel-saat',f'{excess/2:,.1f}',excess/(needed+excess) if needed+excess else 0,'#8574bf')
    if excess:st.warning('Kesin veya elle girilmiş kayıtlar bazı saatlerde ihtiyacı aşıyor. Otomatik atama bu saatlere personel eklemez.')
    st.caption('Halkalar sırasıyla karşılanan ihtiyacın, kalan saatlerin, eksik dilimlerin ve fazla saatlerin payını gösterir. Personel-saat = kişi sayısı × 0,5 saat.')


def shortage_matrix(coverage,start):
    from core.forecast_service import DAY_NAMES
    week=pd.Timestamp(start).normalize()
    days=pd.date_range(week,periods=7)
    df=coverage.copy()
    if 'Sayaca Dahil' in df:df.loc[~df['Sayaca Dahil'],'Eksik']=float('nan')
    df['Tarih']=pd.to_datetime(df.Tarih).dt.normalize()
    table=df.pivot_table(index='Slot',columns='Tarih',values='Eksik',aggfunc=lambda v:v.sum(min_count=1)).reindex(index=range(1,49),columns=days)
    table.columns=[d.strftime('%d.%m')+' '+DAY_NAMES[d.weekday()] for d in days]
    table.index=[f'{(s-1)//2:02d}:{((s-1)%2)*30:02d}–{s//2:02d}:{(s%2)*30:02d}' for s in range(1,49)]
    table.index.name='Yarım saat';return table


def styled_shortage_matrix(matrix):
    peak=float(matrix.max().max()) if matrix.notna().any().any() else 0
    def color(value):
        if pd.isna(value):return 'background-color:#eef2f6;color:#64748b;text-align:center'
        ratio=min(1,float(value)/peak) if peak else 0
        red=255;green=int(247-120*ratio);blue=int(245-120*ratio)
        return f'background-color:rgb({red},{green},{blue});color:#6d2424;text-align:center'
    styles=matrix.map(color)
    display=matrix.map(lambda v:'—' if pd.isna(v) else str(int(v)))
    return display.style.apply(lambda _:styles,axis=None)


def render_shortages(result,key='gap'):
    coverage=result['coverage'];missing,daily=shortage_summary(coverage)
    st.markdown('### Haftalık Eksik Personel · 7 gün × 48 dilim')
    if coverage.empty:st.info('İhtiyaç verisi bulunamadı.');return
    dates=pd.to_datetime(coverage.Tarih)
    first=dates.min().normalize()-pd.Timedelta(days=dates.min().weekday())
    weeks=list(pd.date_range(first,dates.max(),freq='7D'))
    week=st.selectbox('Gösterilecek hafta',weeks,format_func=lambda d:f'{d:%d.%m.%Y} – {d+pd.Timedelta(days=6):%d.%m.%Y}',key=key+'_week') if len(weeks)>1 else first
    matrix=shortage_matrix(coverage,week)
    st.caption('Hücrelerde o yarım saatte eksik olan kişi sayısı bulunur. 0: ihtiyaç karşılanmış · —: sayaca dahil değil, veri yok veya seçili dönem dışında.')
    st.dataframe(styled_shortage_matrix(matrix),height=540,use_container_width=True)
    if missing.empty:st.success('Seçili dönemde tüm yarım saatlik ihtiyaç karşılanmış.');return
    if 'Aralık' not in missing:
        missing['Aralık']=missing.Slot.map(lambda s:f'{(s-1)//2:02d}:{((s-1)%2)*30:02d}–{s//2:02d}:{(s%2)*30:02d}')
    cols=[c for c in ['Tarih','Gün','Aralık','İhtiyaç','Atanan','Eksik'] if c in missing]
    view=missing[cols].rename(columns={'İhtiyaç':'Gereken personel','Atanan':'Yerleştirilen','Eksik':'Eksik personel'})
    with st.expander('Eksiklerin ayrıntılı listesi'):
        st.dataframe(view,hide_index=True,use_container_width=True)
    st.download_button('Eksik Dilimleri CSV İndir',view.to_csv(index=False).encode('utf-8-sig'),'eksik_dilimler.csv','text/csv',key=key+'_csv')


def blocking_issues(result):
    return [r for r in result.get('issues',[]) if not (str(r.get('Sorun','')).startswith('Gece ') and 'kesin kayıt var' in str(r.get('Sorun','')))]


def issue_help(reason):
    if reason.startswith('Gece ') and 'kesin kayıt var' in reason:return ('Gece personel sayısı','O gün için dil bazında tanımlanan gece sayısı ile kayıtlı kişi sayısı farklı.','Gece Kontrolü ekranında kayıtları tamamlayın veya Mesai Kuralları içindeki dil sayısını düzeltin.')
    if 'dinlenme' in reason:return ('11 saat dinlenme','Personelin iki vardiyası arasında yeterli dinlenme yok.','Vardiyalardan birinin başlangıç/bitişini değiştirin; her kişi için en az 11 saat bırakın.')
    if 'Ders/sınav' in reason:return ('Okul takvimiyle çakışma','Çalışma saati ders veya sınav kaydına denk geliyor.','Vardiyayı uygun bir saate/güne taşıyın.')
    if 'süre sınırı' in reason:return ('Vardiya süresi','Kayıt, kişinin grubuna tanımlanan günlük süreyi aşıyor.','Vardiya süresini veya Mesai Kuralları içindeki ilgili süreyi kontrol edin.')
    if 'günü sınırı' in reason:return ('Haftalık gün sınırı','Personel haftalık izin verilen gün sayısından fazla çalışıyor.','İlgili hafta içindeki çalışma günlerini azaltın.')
    if 'çakış' in reason or 'aynı' in reason.casefold():return ('Çakışan kayıt','Aynı personelin kayıtları birbiriyle çakışıyor.','Vardiya Saatleri ve talep kaynaklarında aynı günün kayıtlarını kontrol edin.')
    return ('Kayıt/kural kontrolü',reason,'İlgili personel ve tarihin kaydını Vardiya Saatleri veya Mesai Kuralları ekranında düzeltin.')


def issue_table(result):
    from core.personnel import WORK_LABELS
    from core.planning import SHIFT_LABELS
    from modules.shift_planing.engine import bounds
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
        rows.append({'Personel':person.get('full_name',eid or reason.split(':')[0]),'Personel No':eid or '—','Grup':WORK_LABELS.get(group,group) or '—',
                     'Tarih':r.get('date'),'Mevcut vardiya':shift,'Uygunsuzluk':reason,'Olması gereken':expected})
    return pd.DataFrame(rows)


def render_issues(result):
    if not result.get('issues'):return
    hard=blocking_issues(result);warning=len(result['issues'])-len(hard)
    st.warning(f'{len(hard)} kayıt düzeltilmeli · {warning} gece sayısı uyarısı. Her satırda mevcut vardiya ve karşılaması gereken kural gösterilir.')
    st.dataframe(issue_table(result),hide_index=True,use_container_width=True)

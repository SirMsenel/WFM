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


def _ring(column,label,value,portion,color):
    import altair as alt
    with column:
        st.markdown('**'+label+'**')
        portion=max(0.,min(1.,portion))
        data=pd.DataFrame({'Tür':['Değer','Kalan'],'Pay':[portion,1-portion]})
        arc=alt.Chart(data).mark_arc(innerRadius=45,outerRadius=59).encode(theta='Pay:Q',color=alt.Color('Tür:N',scale=alt.Scale(domain=['Değer','Kalan'],range=[color,'#e9eef4']),legend=None))
        text=alt.Chart(pd.DataFrame({'Değer':[value]})).mark_text(fontSize=19,fontWeight='bold',color='#24445b').encode(text='Değer:N')
        st.altair_chart((arc+text).properties(height=145),use_container_width=True)


def coverage_summary(result,title='Yerleştirmelerin İhtiyaca Etkisi'):
    coverage=result['coverage'];needed=float(coverage['İhtiyaç'].sum());left=float(coverage['Eksik'].sum())
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
    df=coverage.copy();df['Tarih']=pd.to_datetime(df.Tarih).dt.normalize()
    table=df.pivot_table(index='Slot',columns='Tarih',values='Eksik',aggfunc='sum').reindex(index=range(1,49),columns=days)
    table.columns=[d.strftime('%d.%m')+' '+DAY_NAMES[d.weekday()] for d in days]
    table.index=[f'{(s-1)//2:02d}:{((s-1)%2)*30:02d}–{s//2:02d}:{(s%2)*30:02d}' for s in range(1,49)]
    table.index.name='Yarım saat';return table


def render_shortages(result,key='gap'):
    coverage=result['coverage'];missing,daily=shortage_summary(coverage)
    st.markdown('### Haftalık Eksik Personel · 7 gün × 48 dilim')
    if coverage.empty:st.info('İhtiyaç verisi bulunamadı.');return
    dates=pd.to_datetime(coverage.Tarih)
    first=dates.min().normalize()-pd.Timedelta(days=dates.min().weekday())
    weeks=list(pd.date_range(first,dates.max(),freq='7D'))
    week=st.selectbox('Gösterilecek hafta',weeks,format_func=lambda d:f'{d:%d.%m.%Y} – {d+pd.Timedelta(days=6):%d.%m.%Y}',key=key+'_week') if len(weeks)>1 else first
    matrix=shortage_matrix(coverage,week)
    st.caption('Hücrelerde o yarım saatte eksik olan kişi sayısı bulunur. 0: ihtiyaç karşılanmış · —: ihtiyaç verisi yok veya seçili dönem dışında.')
    st.dataframe(matrix.style.format('{:.0f}',na_rep='—').background_gradient(cmap='Reds',axis=None,vmin=0).set_properties(**{'text-align':'center'}),height=540,use_container_width=True)
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


def render_issues(result):
    if not result.get('issues'):return
    names={str(e['employee_id']):e.get('full_name',str(e['employee_id'])) for e in result.get('staff',[])}
    hard=blocking_issues(result);warning=len(result['issues'])-len(hard)
    st.warning(f'{len(hard)} kayıt düzeltilmeli · {warning} gece sayısı uyarısı. Gece sayısı uyarıları incelenerek yayınlanabilir; kayıt ve dinlenme ihlalleri düzeltilmelidir.')
    rows=[]
    for r in result['issues']:
        category,meaning,action=issue_help(str(r.get('Sorun','')))
        rows.append({'Personel':names.get(str(r.get('employee_id')),str(r.get('employee_id') or 'Dil/grup geneli')),
                     'Tarih':r.get('date'),'Konu':category,'Ne anlama geliyor?':meaning,'Yapılacak işlem':action,'Kayıt ayrıntısı':r.get('Sorun')})
    st.dataframe(rows,hide_index=True,use_container_width=True)

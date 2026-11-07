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


def coverage_summary(result,title='Yerleştirmelerin İhtiyaca Etkisi'):
    coverage=result['coverage'];needed=float(coverage['İhtiyaç'].sum());left=float(coverage['Eksik'].sum())
    st.markdown('### '+title)
    a,b,c,d=st.columns(4)
    a.metric('Karşılanan ihtiyaç',f'%{100*(needed-left)/needed:.1f}' if needed else '%100')
    b.metric('Kalan personel-saat',f'{left/2:,.1f}')
    c.metric('Eksik olan yarım saat',int((coverage.Eksik>0).sum()))
    d.metric('Fazla personel-saat',f'{coverage.Fazla.sum()/2:,.1f}')
    if coverage.Fazla.sum()>0:
        st.warning('Kesin veya elle yerleştirilmiş kayıtlarda ihtiyacın üstüne çıkan dilimler var. Otomatik tamamlama bu dilimlere ek personel yazmaz.')
    st.caption('Personel-saat: her yarım saatte eksik/fazla kişi sayısı × 0,5. İzin ve sınav kayıtları personelin çalışmasını engeller; ihtiyacı karşılamış sayılmaz.')


def render_shortages(result,key='gap'):
    missing,daily=shortage_summary(result['coverage'])
    st.markdown('### Nerede Personel Eksik?')
    if missing.empty:
        st.success('Seçili dönemde tüm yarım saatlik ihtiyaç karşılanmış.');return
    st.bar_chart(daily.assign(Tarih=daily.Tarih.astype(str)).set_index('Tarih')[['Eksik personel-saat']])
    if 'Aralık' not in missing:
        missing['Aralık']=missing.Slot.map(lambda s:f'{(s-1)//2:02d}:{((s-1)%2)*30:02d}–{s//2:02d}:{(s%2)*30:02d}')
    days=sorted(missing.Tarih.astype(str).unique())
    day=st.selectbox('Eksiklerin gösterileceği gün',['Tüm günler']+days,key=key+'_day')
    if day!='Tüm günler':missing=missing[missing.Tarih.astype(str)==day]
    cols=[c for c in ['Tarih','Gün','Aralık','İhtiyaç','Atanan','Eksik'] if c in missing]
    view=missing[cols].rename(columns={'İhtiyaç':'Gereken personel','Atanan':'Yerleştirilen','Eksik':'Eksik personel'})
    st.dataframe(view.style.background_gradient(cmap='Reds',subset=['Eksik personel']).format({'Gereken personel':'{:.0f}','Yerleştirilen':'{:.0f}','Eksik personel':'{:.0f}'}),hide_index=True,use_container_width=True,height=min(460,70+len(view)*30))
    st.download_button('Eksik Dilimleri CSV İndir',view.to_csv(index=False).encode('utf-8-sig'),'eksik_dilimler.csv','text/csv',key=key+'_csv')


def render_issues(result):
    if not result.get('issues'):
        return
    names={str(e['employee_id']):e.get('full_name',str(e['employee_id'])) for e in result.get('staff',[])}
    issues=[{'Personel':names.get(str(r.get('employee_id')),str(r.get('employee_id') or 'Genel')),
             'Tarih':r.get('date'),'Kontrol':r.get('Sorun')} for r in result['issues']]
    st.warning('Düzeltilmesi gereken kayıt veya kural uyuşmazlıkları var.')
    st.dataframe(issues,hide_index=True,use_container_width=True)

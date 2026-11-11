import streamlit as st
from ortak.yayin_onaylari import proposals,vote
from ortak.takvim_gorunumu import render_calendar


def render():
    s=st.session_state;st.subheader('Plan Yayın Onayları');items=proposals(s)
    if s.get('approval_notice'):st.success(s.pop('approval_notice'))
    if not items:st.info('Henüz onaya gönderilmiş taslak yok.');return
    byid={r['id']:r for r in items};ident=st.selectbox('Plan',[r['id'] for r in items],format_func=lambda i:f"{byid[i]['result']['period']['start']} – {byid[i]['result']['period']['end']} · {byid[i]['status']} · %{byid[i]['rate']:.1f} eksik",key='approval_pick');item=byid[ident]
    from ortak.modern_kartlar import metric_cards
    metric_cards([('Planlama onayı',f"{len(item['votes'])}/2"),('Eksik ihtiyaç',f"%{item['rate']:.2f}"),('Yönetici onayı','Alındı' if item['manager'] else 'Gerekli' if item['rate']>5 else 'Gerekmiyor')])
    result=item['result']
    from ortak.planlama_gorunumu import coverage_summary,shortage_matrix,styled_shortage_matrix
    coverage_summary(result,'Planın Doluluk ve Açık Özeti')
    with st.expander('Yarım saatlerde eksik / fazla personel',expanded=True):
        import pandas as pd
        starts=list(pd.date_range(result['period']['start'],result['period']['end'],freq='7D'));chosen=st.selectbox('İncelenecek hafta',starts,format_func=lambda d:d.strftime('%d.%m.%Y'),key='approval_coverage_week') if len(starts)>1 else starts[0]
        a,b=st.columns(2)
        with a:st.markdown('**Eksik personel**');st.dataframe(styled_shortage_matrix(shortage_matrix(result['coverage'],chosen)),use_container_width=True,height=300)
        with b:
            extra=result['coverage'].copy();extra['Eksik']=extra['Fazla'];st.markdown('**Fazla personel**');st.dataframe(styled_shortage_matrix(shortage_matrix(extra,chosen),excess=True),use_container_width=True,height=300)
    with st.expander('Yemek, Mola ve Koçluk Dağılımı',expanded=False):
        from modules.statu_analizi import render_data
        render_data(result.get('breaks',[]),result['period']['start'],result['period']['end'],'approval_statuses')
    st.info('Son gerekli onay verildiğinde vardiyalar otomatik yayınlanır; Tüm Vardiyalar ve Takip ekranlarında görünür.')
    approvals=item['votes']+([item['manager']] if item.get('manager') else [])
    if approvals:
        from html import escape
        for col,v in zip(st.columns(len(approvals)),approvals):
            col.markdown('<div style="border:1px solid #b9e2d4;background:#eaf8f1;border-radius:15px;padding:16px"><b>✓ '+escape(v.get('name') or v.get('as') or v['actor'])+'</b><div style="font-size:12px;margin-top:10px">'+escape(v['at'][:16].replace('T',' '))+'</div></div>',unsafe_allow_html=True)
    else:st.caption('Henüz onay veren yok.')
    if item['status']=='Yayınlandı':st.success('Vardiya otomatik yayınlandı. Tüm Vardiyalar ekranından inceleyebilirsin.')
    if item['status']!='Bekliyor':return
    if s['profile'].get('position') not in {'wfm','planning_manager'}:st.info('Bu hesap bu aşamada yalnızca görüntüleyebilir.');return
    from ortak.yayin_onaylari import is_current
    fresh=is_current(s,item)
    if not fresh:st.warning('Bu taslak kontrol edildikten sonra kaynaklar değişmiş. Reddedip güncel planı yeniden oluşturun.')
    reason=st.text_input('Ret gerekçesi',key='approval_reason');a,b=st.columns(2)
    if a.button('İnceledim ve Yayına Onay Veriyorum',key='approval_yes',disabled=not fresh):
        try:
            completed=vote(s,ident);s['approval_notice']='Plan yayınlandı.' if completed else 'Onay kaydedildi; diğer onaylar bekleniyor.';st.rerun()
        except ValueError as e:st.error(str(e))
    if b.button('Taslağı Reddet',key='approval_no'):
        try:vote(s,ident,False,reason);st.rerun()
        except ValueError as e:st.error(str(e))


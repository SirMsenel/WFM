import streamlit as st
from ortak.yayin_onaylari import proposals,vote
from ortak.takvim_gorunumu import render_calendar


def render():
    s=st.session_state;st.subheader('Plan Yayın Onayları');items=proposals(s)
    if s.get('approval_notice'):st.success(s.pop('approval_notice'))
    if not items:st.info('Henüz onaya gönderilmiş taslak yok.');return
    byid={r['id']:r for r in items};ident=st.selectbox('Plan',[r['id'] for r in items],format_func=lambda i:f"{byid[i]['result']['period']['start']} – {byid[i]['result']['period']['end']} · {byid[i]['status']} · %{byid[i]['rate']:.1f} eksik",key='approval_pick');item=byid[ident]
    a,b,c=st.columns(3);a.metric('Planlama onayı',f"{len(item['votes'])}/2");b.metric('Eksik ihtiyaç',f"%{item['rate']:.2f}");c.metric('Yönetici onayı','Alındı' if item['manager'] else 'Gerekli' if item['rate']>5 else 'Gerekmiyor')
    result=item['result'];render_calendar(result['plan'],result['staff'],result['period']['start'],result['period']['end'],key='approval_calendar')
    st.dataframe(item['votes'],hide_index=True,use_container_width=True)
    if item['status']!='Bekliyor':return
    if s['profile'].get('position') not in {'wfm','planning_manager'}:st.info('Bu hesap bu aşamada yalnızca görüntüleyebilir.');return
    reason=st.text_input('Ret gerekçesi',key='approval_reason');a,b=st.columns(2)
    if a.button('İnceledim ve Yayına Onay Veriyorum',key='approval_yes'):
        try:
            completed=vote(s,ident);s['approval_notice']='Plan yayınlandı.' if completed else 'Onay kaydedildi; diğer onaylar bekleniyor.';st.rerun()
        except ValueError as e:st.error(str(e))
    if b.button('Taslağı Reddet',key='approval_no'):
        try:vote(s,ident,False,reason);st.rerun()
        except ValueError as e:st.error(str(e))


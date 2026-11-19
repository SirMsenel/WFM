"""Yönetici ve liderler için tek yerden yetki kapsamındaki onaylar."""
import streamlit as st
from ortak.gezinme import sections


def personnel():
    from ortak.personel_is_akisi import proposals,decide
    s=st.session_state;p=s['profile'];items=proposals(s);role=p.get('position')
    relevant=[r for r in items if (r['stage']=='Yönetici onayı' and role in {'manager','assistant_manager','moderator'} and (role=='moderator' or r.get('manager')==p.get('full_name'))) or (r['stage']=='Planlama onayı' and role=='wfm')]
    if not relevant:st.info('Hesabında bekleyen personel onayı yok.');return
    for r in relevant:
        with st.container(border=True):
            st.markdown('#### '+r['kind']+' · '+r['values'].get('full_name','Personel'));st.caption(r['stage']+' · '+r['values'].get('effective_date',''));st.write(r['reason']);note=st.text_input('Karar notu',key='hr_note_'+r['id']);a,b=st.columns(2)
            for col,label,yes in [(a,'Onayla',True),(b,'Reddet',False)]:
                if col.button(label,key='hr_central_'+r['id']+str(yes)):
                    try:decide(s,r,yes,note);st.rerun()
                    except ValueError as e:st.warning(str(e))


def render():
    s=st.session_state;st.title('📥 Onay Merkezi');role=s['profile'].get('position')
    if role not in {'tl','manager','assistant_manager','wfm','planning_manager','moderator'}:st.info('Bu ekran yönetim rolleri içindir.');return
    from modules.yayin_onay_ekrani import render as publications
    from modules.statu_degisimi import render_requests
    from ortak.talep_gorunumu import render_center
    pages={'Personel İşlemleri':personnel,'Personel Talepleri':lambda:render_center('all','central_requests'),'Statü Değişimleri':lambda:render_requests(s)}
    if role in {'wfm','planning_manager','manager','assistant_manager','moderator'}:pages={'Plan Yayın Onayları':publications,'Statü Yönetimi':__import__('modules.statu_yonetimi',fromlist=['render']).render,**pages}
    sections('nav_approval_center',pages)

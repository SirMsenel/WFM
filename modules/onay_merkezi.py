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


def simulation_actions():
    from ortak.simulasyon_aksiyonlari import list_actions,decide
    s=st.session_state;items=list_actions(s);waiting=[item for item in items if item.get('status')=='Onay bekliyor']
    if not waiting:st.info('Bekleyen simülasyon aksiyonu yok.');return
    for item in waiting:
        with st.container(border=True):
            from html import escape
            st.markdown(f'<div style="padding:15px 17px;border-radius:16px;background:linear-gradient(135deg,#eef7f8,#f5f1fb);border:1px solid #dce7ed"><div style="display:flex;justify-content:space-between;gap:12px"><span><small style="color:#b27a2f">ONAY BEKLİYOR</small><h4 style="margin:4px 0">{escape(item["kind"])} · {escape(item["month"])}</h4></span><span style="text-align:right"><b>{escape(item.get("actor_name",item.get("actor","—")))}</b><br><small>{escape(item.get("created_at","")[:16].replace("T"," "))}</small></span></div><div style="margin-top:9px;color:#5d707c">{escape(item["reason"])}</div></div>',unsafe_allow_html=True)
            scenario=item.get('scenario') or []
            if scenario:
                frame=__import__('pandas').DataFrame(scenario);month_rows=frame[frame['Ay'].astype(str)==str(item['month'])] if 'Ay' in frame else frame.head(3)
                if not month_rows.empty:st.dataframe(month_rows[[c for c in ['Senaryo','Mevcut personel','Gerekli personel','Önerilen alım','Simüle SL (%)'] if c in month_rows]],hide_index=True,use_container_width=True)
            note=st.text_input('Karar notu',key='sim_approval_note_'+str(item['id']));detail,x,y=st.columns([1.25,1,1])
            if detail.button('Simülasyon Detayına Git',key='sim_approval_detail_'+str(item['id']),use_container_width=True):
                from ortak.gezinme import navigate
                navigate(s,'🧮 Similasyon');s['sim_section']='Senaryo Özeti';s['sim_section_control']='Senaryo Özeti';st.rerun()
            if x.button('Aksiyonu Onayla',type='primary',key='sim_approval_yes_'+str(item['id'])):
                try:decide(s,item['id'],True,note);st.rerun()
                except ValueError as exc:st.warning(str(exc))
            if y.button('Aksiyonu Reddet',key='sim_approval_no_'+str(item['id'])):
                try:decide(s,item['id'],False,note);st.rerun()
                except ValueError as exc:st.warning(str(exc))


def render():
    s=st.session_state;st.title('📥 Onay Merkezi');role=s['profile'].get('position')
    if role not in {'tl','manager','assistant_manager','wfm','planning_manager','moderator'}:st.info('Bu ekran yönetim rolleri içindir.');return
    from modules.yayin_onay_ekrani import render as publications
    from modules.statu_degisimi import render_requests
    from ortak.talep_gorunumu import render_center
    pages={'Personel İşlemleri':personnel,'Personel Talepleri':lambda:render_center('all','central_requests'),'Statü Değişimleri':lambda:render_requests(s)}
    if role in {'wfm','planning_manager','manager','assistant_manager','moderator'}:pages={'Plan Yayın Onayları':publications,'Simülasyon Aksiyonları':simulation_actions,'Statü Yönetimi':__import__('modules.statu_yonetimi',fromlist=['render']).render,**pages}
    sections('nav_approval_center',pages)

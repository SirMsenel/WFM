"""Otomatik taslak sonrası açık kapatma, vardiya inceleme ve onaya gönderme."""
import pandas as pd
import streamlit as st

from ortak.planlama_gorunumu import period_banner,coverage_summary,render_shortages,render_issues,blocking_issues,roster_summary
from modules.vardiya_plani.planlama_verileri import fingerprint


def _calendar(result):
    from ortak.planlama import calendar_grid
    from ortak.vardiya_gorunumu import cell_style
    grid=calendar_grid({**result,'source_rows':result['plan'],'exam_keys':set()},result['period'])
    styled=grid.style.map(cell_style,subset=[c for c in grid if c not in {'Personel','Sicil no','Kullanıcı adı'}])
    st.dataframe(styled,hide_index=True,use_container_width=True,height=520)


def _publish(state,result,stale):
    hard=blocking_issues(result);warnings=len(result.get('issues',[]))-len(hard);has_gaps=bool(result['coverage'].Eksik.sum())
    soft=any(r.get('severity')=='warning' and r.get('override_required',True) for r in result.get('issues',[]));reasons=[]
    if soft:
        state['planning_accept_soft']=st.checkbox('Esnek kural uyarılarını inceledim ve onaylıyorum',value=state.get('planning_accept_soft',False),key='draft_actions_soft')
        if not state['planning_accept_soft']:reasons.append('Esnek kural uyarıları onaylanmalı.')
    if stale:reasons.append('Kurallar veya kayıtlar değişti; otomatik taslağı yeniden oluşturun.')
    if hard:reasons.append(f'{len(hard)} kesin kural ihlali düzeltilmeli.')
    if reasons:st.warning('Yayın onayı için kalanlar: '+' · '.join(reasons))
    approvals=state.get('shift_rules',{}).get('publication_approvals',{}).get('enabled')
    label='Taslağı Yayın Onayına Gönder' if approvals else ('Eksikleri Kabul Et ve Planı Yayınla' if has_gaps or warnings else 'Kontrol Edilen Planı Yayınla')
    if st.button(label,key='draft_actions_publish',type='primary',disabled=bool(reasons),use_container_width=True):
        try:
            if approvals:
                from ortak.yayin_onaylari import submit
                ident=submit(state,result);st.success('Taslak onaya gönderildi: '+ident)
            else:
                from ortak.yayin_servisi import publish_plan
                publish_plan(state,result);st.success('Plan yayınlandı ve kayıt merkezine işlendi.')
        except (ValueError,OSError) as exc:st.error(str(exc))


def render():
    state=st.session_state;st.subheader('Taslak Aksiyonları ve Yayına Hazırlık')
    if (state.get('profile') or {}).get('position') not in {'wfm','manager','assistant_manager','moderator','planning_manager'}:
        st.info('Bu alan planlama ve yönetim rolleri içindir.');return
    if not period_banner(state):return
    result=state.get('planning_result')
    if result is None:
        st.info('Önce Oluştur & Kontrol ekranında otomatik vardiya taslağı oluşturun.');return
    stale=state.get('planning_result_fingerprint')!=fingerprint(state)
    if stale:st.warning('Taslak oluşturulduktan sonra kaynak kayıt veya kural değişmiş.')
    roster_summary(result,'Taslakta Kullanılan Kapasite')
    st.markdown('### Personel Vardiya Taslağı')
    st.caption('Aşağıdaki vardiyaları inceleyebilir; uygun aksiyonu uyguladıktan sonra güncel sonucu yeniden oluşturabilirsin.')
    _calendar(result)
    if st.button('Vardiya Hücrelerini Düzenle',key='draft_actions_open_shift_hours'):
        from ortak.gezinme import select_section
        select_section(state,'nav_roster','Vardiya Saatleri');st.rerun()
    coverage_summary(result,'Taslağın İhtiyaç Sonucu')
    render_shortages(result,'draft_action_gaps')
    render_issues(result)
    st.divider();st.markdown('### Yayın Kararı')
    _publish(state,result,stale)

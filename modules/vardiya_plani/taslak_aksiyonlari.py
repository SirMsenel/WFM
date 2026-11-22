"""Otomatik taslak sonrası açık kapatma, vardiya inceleme ve onaya gönderme."""
import pandas as pd
import streamlit as st

from ortak.planlama_gorunumu import period_banner,render_shortages,render_issues,blocking_issues
from modules.vardiya_plani.planlama_verileri import fingerprint


def _calendar(result):
    from ortak.planlama import calendar_grid
    from ortak.vardiya_gorunumu import cell_style
    grid=calendar_grid({**result,'source_rows':result['plan'],'exam_keys':set()},result['period'])
    styled=grid.style.map(cell_style,subset=[c for c in grid if c not in {'Personel','Sicil no','Kullanıcı adı'}])
    st.dataframe(styled,hide_index=True,use_container_width=True,height=520)


def _shift_editor(state,result):
    from modules.vardiya_plani.vardiya_motoru import bounds
    from ortak.personel import WORK_LABELS
    editable=[r for r in result.get('plan',[]) if r.get('source') not in {'fixed_external','approved_request','published_fixed','foreign_language_plan'}]
    if not editable:return
    with st.expander('Shift Üzerinden Personel / Saat Düzelt',expanded=bool(result.get('issues'))):
        staff={str(p['employee_id']):p for p in result.get('staff',[])}
        options=list(range(len(editable)))
        choice=st.selectbox('Düzenlenecek vardiya',options,format_func=lambda i:f"{editable[i].get('full_name') or staff.get(str(editable[i]['employee_id']),{}).get('full_name',editable[i]['employee_id'])} · {editable[i]['date']} · {editable[i].get('start') or editable[i].get('shift_code')}–{editable[i].get('end') or ''}",key='draft_shift_edit_pick')
        old=editable[choice];current=str(old['employee_id']);people=[eid for eid,p in staff.items() if p.get('work_type')==staff.get(current,{}).get('work_type') and p.get('language','tr')==staff.get(current,{}).get('language','tr')]
        replacement=st.selectbox('Personel',people,index=people.index(current) if current in people else 0,format_func=lambda eid:f"{staff[eid].get('full_name',eid)} · {WORK_LABELS.get(staff[eid].get('work_type'),staff[eid].get('work_type'))}",key='draft_shift_edit_person')
        codes=['WORK','MESAI','GECE','OFF'];code=st.selectbox('Statü',codes,index=codes.index(old.get('shift_code')) if old.get('shift_code') in codes else 0,key='draft_shift_edit_code')
        times=[f'{m//60:02d}:{m%60:02d}' for m in range(0,1440,30)]
        left,right=st.columns(2);start=left.selectbox('Başlangıç',times,index=times.index(old.get('start')) if old.get('start') in times else 16,key='draft_shift_edit_start',disabled=code=='OFF');end=right.selectbox('Bitiş',times,index=times.index(old.get('end')) if old.get('end') in times else 34,key='draft_shift_edit_end',disabled=code=='OFF')
        if st.button('Değişikliği Taslağa Uygula',key='draft_shift_edit_apply',type='primary'):
            from ortak.taslak_degisimleri import edit_shifts
            row={**old,'employee_id':replacement,'full_name':staff[replacement].get('full_name',replacement),'group':staff[replacement].get('work_type'),'shift_code':code,'start':None if code=='OFF' else start,'end':None if code=='OFF' else end,'source':'manual_single','note':'Taslak Aksiyonları ekranında planlama düzeltmesi'}
            try:
                edit_shifts(state,[row],[(current,old['date'])] if replacement!=current else ());state.pop('planning_result',None);state.pop('planning_result_fingerprint',None)
                st.success('Değişiklik taslağa işlendi. Kural ve ihtiyaç sonucunu doğrulamak için otomatik taslağı yeniden oluştur.');st.rerun()
            except ValueError as exc:st.error(str(exc))


def _publish(state,result,stale):
    hard=blocking_issues(result);warnings=len(result.get('issues',[]))-len(hard);has_gaps=bool(result['coverage'].Eksik.sum())
    soft=any(r.get('severity')=='warning' and r.get('override_required',True) for r in result.get('issues',[]));reasons=[]
    if soft:
        state['planning_accept_soft']=st.checkbox('Esnek kural uyarılarını inceledim ve onaylıyorum',value=state.get('planning_accept_soft',False),key='draft_actions_soft')
        if not state['planning_accept_soft']:reasons.append('Esnek kural uyarıları onaylanmalı.')
    if stale:reasons.append('Kurallar veya kayıtlar değişti; otomatik taslağı yeniden oluşturun.')
    if hard:
        state['planning_accept_hard']=st.checkbox('Kesin kural ihlallerini gördüm; planlama onayıyla devam etmek istiyorum',value=state.get('planning_accept_hard',False),key='draft_actions_hard')
        if not state['planning_accept_hard']:reasons.append(f'{len(hard)} kesin kural ihlali düzeltilmeli veya planlama sorumluluğuyla açıkça onaylanmalı.')
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
    st.markdown('### Taslak Üzerinde Düzeltme')
    _calendar(result)
    _shift_editor(state,result)
    st.markdown('### Sistem Önerileri ve Açık Kapatma')
    render_shortages(result,'draft_action_gaps')
    st.markdown('### Kural Uyuşmazlıkları ve Düzeltme Alanı')
    render_issues(result)
    st.divider();st.markdown('### Yayın Kararı')
    _publish(state,result,stale)

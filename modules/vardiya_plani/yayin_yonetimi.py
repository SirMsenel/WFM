# Vardiya Plani / Yayin Yonetimi — bu ekranın / servisin uygulama kodu.
import streamlit as st
import pandas as pd
from ortak.yayin_servisi import publications,withdraw
from ortak.personel import LANG_LABELS
from ortak.planlama import calendar_grid
from ortak.vardiya_gorunumu import cell_style


def render():
    state=st.session_state;st.subheader('Yayın Yönetimi · Düzenle veya Geri Al')
    if (state.get('profile') or {}).get('position') not in {'wfm','manager','assistant_manager','moderator','planning_manager'}:st.info('Yayın yönetimi planlama rollerine açıktır.');return
    batches=publications(state);active=[b for b in batches if b['status']=='active']
    if not active:st.info('Yayında bir dönem yok.');return
    ident=st.selectbox('Yayınlanmış dönem',[b['id'] for b in active],format_func=lambda i:next(f"{b['start']} – {b['end']} · {', '.join(LANG_LABELS.get(l,l) for l in b['languages'])} · {i}" for b in active if b['id']==i),key='published_batch_pick')
    batch=next(b for b in active if b['id']==ident);ids={str(r['employee_id']) for r in batch['rows']}
    from ortak.personel_deposu import list_people
    directory={str(e['employee_id']):e for e in list_people(state,True)}
    directory.update({str(e['employee_id']):e for e in state.get('employees_cache',[])})
    people=[directory.get(eid,{'employee_id':eid,'full_name':eid}) for eid in sorted(ids)]
    if not state.get('employees_cache'):state['employees_cache']=[e for e in directory.values() if e.get('position','agent')=='agent']
    grid=calendar_grid({'staff':people,'source_rows':batch['rows'],'exam_keys':set()},batch)
    if state['profile'].get('position')=='wfm':
        edited=st.data_editor(grid.style.map(cell_style,subset=list(grid.columns)[1:]),disabled=['Personel'],hide_index=True,use_container_width=True,height=500,key='publication_grid_'+ident)
        st.caption('Hücreleri doğrudan düzenleyebilirsin: 08:00–17:00, Gece 00:00–08:00 veya OFF / izin adı. Kaydetmeden önce çalışma ve dinlenme kuralları kontrol edilir.')
        reason=st.text_input('Değişiklik gerekçesi',key='publication_cell_reason')
        if st.button('Değişiklikleri Kontrol Et ve Kaydet',key='publication_cells_apply'):
            try:
                from ortak.yayin_hucre_duzenleyici import changes_from_grid
                from ortak.vardiya_degisimleri import apply_changes
                changes=changes_from_grid(grid,edited,people,batch)
                if not changes:raise ValueError('Değişen hücre yok.')
                apply_changes(state,changes,'Planlama düzeltmesi',reason);st.success('Vardiya ve statüler güncellendi.');st.rerun()
            except (ValueError,TypeError) as e:st.warning(str(e))
    else:st.dataframe(grid.style.map(cell_style,subset=list(grid.columns)[1:]),hide_index=True,use_container_width=True,height=500)
    st.caption('Taslağa taşıma yayını kaldırır, mevcut atamaları elle düzenlenebilir taslak olarak korur. Geri alma ise yayını kaldırır. Her iki işlem de bu yayının dil/personel kapsamıyla sınırlıdır; eski yayın sürümü arşivde kalır.')
    from ortak.yayin_servisi import publication_today
    past=str(batch['start'])<publication_today().isoformat()
    if past:st.info('Geçmiş günleri içeren bu yayın korunur; geri alınamaz veya taslağa taşınamaz.')
    a,b=st.columns(2)
    for col,label,reopen,key in [(a,'Yayını Geri Al ve Düzenlemek İçin Taslağa Taşı',True,'publication_reopen'),(b,'Yayını Geri Al',False,'publication_withdraw')]:
        if col.button(label,key=key,disabled=past):
            try:withdraw(state,batch,reopen);state['publication_notice']='Yayın geri alındı. '+('Vardiya Saatleri ekranında elle girişleri silip yeniden düzenleyebilirsin.' if reopen else 'Bu dönem yeniden planlanabilir.');st.rerun()
            except ValueError as exc:st.error(str(exc))

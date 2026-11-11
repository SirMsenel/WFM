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
    people=[e for e in state.get('employees_cache',[]) if str(e['employee_id']) in ids]
    grid=calendar_grid({'staff':people,'source_rows':batch['rows'],'exam_keys':set()},batch)
    st.dataframe(grid.style.map(cell_style,subset=[c for c in grid if c not in {'Personel','Sicil no','Kullanıcı adı'}]),hide_index=True,use_container_width=True,height=500)
    if state['profile'].get('position')=='wfm':
        with st.expander('Yayınlanan Hücreleri Doğrudan Düzenle',expanded=False):
            st.caption('Yalnızca değiştirdiğin günler uygulanır. Çalışma/dinlenme kuralları kontrol edilir; statüler yeniden planlanır ve personele bildirim düşer.')
            days=sorted({r['date'] for r in batch['rows']});chosen_day=st.selectbox('Düzenlenecek gün',days,key='published_edit_day_'+ident);query=st.text_input('Düzenlenecek personeli ara',key='published_edit_search_'+ident)
            from ortak.planlama import SHIFT_LABELS
            lookup={str(p['employee_id']):p for p in people};table=pd.DataFrame([{'Personel':lookup.get(str(r['employee_id']),{}).get('full_name',r['employee_id']),'Sicil':str(r['employee_id']),'Tarih':r['date'],'Statü':r['shift_code'],'Başlangıç':r.get('start') or '', 'Bitiş':r.get('end') or ''} for r in batch['rows'] if r['date']==chosen_day and (not query or query.casefold() in lookup.get(str(r['employee_id']),{}).get('full_name',str(r['employee_id'])).casefold())])
            edited=st.data_editor(table,disabled=['Personel','Sicil','Tarih'],hide_index=True,key='publication_cells_'+ident+'_'+chosen_day+'_'+query,column_config={'Statü':st.column_config.SelectboxColumn(options=[k for k in SHIFT_LABELS if k!='RAPOR'],required=True)})
            reason=st.text_input('Hücre değişikliği gerekçesi',key='publication_cell_reason')
            if st.button('Değişen Hücreleri Kontrol Et ve Uygula',key='publication_cells_apply'):
                try:
                    changes=[]
                    for old,new in zip(table.to_dict('records'),edited.to_dict('records')):
                        if old!=new:changes.append({'employee_id':new['Sicil'],'date':new['Tarih'],'shift_code':new['Statü'],'start':new['Başlangıç'] or None,'end':new['Bitiş'] or None})
                    from ortak.vardiya_degisimleri import apply_changes
                    apply_changes(state,changes,'Planlama düzeltmesi',reason);st.success('Vardiya ve statüler güncellendi.');st.rerun()
                except (ValueError,TypeError) as e:st.warning(str(e))
    st.caption('Taslağa taşıma yayını kaldırır, mevcut atamaları elle düzenlenebilir taslak olarak korur. Geri alma ise yayını kaldırır. Her iki işlem de bu yayının dil/personel kapsamıyla sınırlıdır; eski yayın sürümü arşivde kalır.')
    from ortak.yayin_servisi import publication_today
    past=str(batch['start'])<publication_today().isoformat()
    if past:st.info('Geçmiş günleri içeren bu yayın korunur; geri alınamaz veya taslağa taşınamaz.')
    a,b=st.columns(2)
    for col,label,reopen,key in [(a,'Yayını Geri Al ve Düzenlemek İçin Taslağa Taşı',True,'publication_reopen'),(b,'Yayını Geri Al',False,'publication_withdraw')]:
        if col.button(label,key=key,disabled=past):
            try:withdraw(state,batch,reopen);state['publication_notice']='Yayın geri alındı. '+('Vardiya Saatleri ekranında elle girişleri silip yeniden düzenleyebilirsin.' if reopen else 'Bu dönem yeniden planlanabilir.');st.rerun()
            except ValueError as exc:st.error(str(exc))

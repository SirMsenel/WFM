# Vardiya Plani / Yayin Yonetimi — bu ekranın / servisin uygulama kodu.
import streamlit as st
import pandas as pd
from ortak.yayin_servisi import publications,withdraw
from ortak.personel import LANG_LABELS
from ortak.planlama import calendar_grid
from ortak.vardiya_gorunumu import cell_style


def render():
    state=st.session_state;st.subheader('Yayın Yönetimi · Düzenle veya Geri Al')
    if (state.get('profile') or {}).get('position') not in {'wfm','manager','moderator'}:st.info('Yayın yönetimi planlama rollerine açıktır.');return
    batches=publications(state);active=[b for b in batches if b['status']=='active']
    if not active:st.info('Yayında bir dönem yok.');return
    ident=st.selectbox('Yayınlanmış dönem',[b['id'] for b in active],format_func=lambda i:next(f"{b['start']} – {b['end']} · {', '.join(LANG_LABELS.get(l,l) for l in b['languages'])} · {i}" for b in active if b['id']==i),key='published_batch_pick')
    batch=next(b for b in active if b['id']==ident);ids={str(r['employee_id']) for r in batch['rows']}
    people=[e for e in state.get('employees_cache',[]) if str(e['employee_id']) in ids]
    grid=calendar_grid({'staff':people,'source_rows':batch['rows'],'exam_keys':set()},batch)
    st.dataframe(grid.style.map(cell_style,subset=[c for c in grid if c not in {'Personel','Sicil no','Kullanıcı adı'}]),hide_index=True,use_container_width=True,height=500)
    st.caption('Taslağa taşıma yayını kaldırır, mevcut atamaları elle düzenlenebilir taslak olarak korur. Geri alma ise yayını kaldırır. Her iki işlem de bu yayının dil/personel kapsamıyla sınırlıdır; eski yayın sürümü arşivde kalır.')
    a,b=st.columns(2)
    for col,label,reopen,key in [(a,'Yayını Geri Al ve Düzenlemek İçin Taslağa Taşı',True,'publication_reopen'),(b,'Yayını Geri Al',False,'publication_withdraw')]:
        if col.button(label,key=key):
            try:withdraw(state,batch,reopen);state['publication_notice']='Yayın geri alındı. '+('Vardiya Saatleri ekranında elle girişleri silip yeniden düzenleyebilirsin.' if reopen else 'Bu dönem yeniden planlanabilir.');st.rerun()
            except ValueError as exc:st.error(str(exc))

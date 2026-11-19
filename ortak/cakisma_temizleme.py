# Ortak / Cakisma Temizleme — bu ekranın / servisin uygulama kodu.
import streamlit as st
from ortak.taslak_degisimleri import edit_shifts


def propose_cleanup(state,keys,prefix):
    keys=set((str(a),str(b)) for a,b in keys)
    rows=[r for r in state.get('draft_shift_plan',[]) if (str(r['employee_id']),str(r['date'])) in keys and r.get('source') in {'auto','manual','manual_single','manual_template'}]
    if not rows:return
    labels={str(e['employee_id']):e.get('full_name',str(e['employee_id'])) for e in state.get('employees_cache',[])}
    with st.expander('Dolu / uyuşmayan taslak kayıtlarını kaldırmayı değerlendir'):
        st.caption('Yalnızca seçtiğin elle/otomatik taslak kayıtları silinir. Kesin gece/izin ve onaylı talepler kendi kaynaklarından düzeltilir.')
        selected=st.multiselect('Silinmesini istediğin taslak atamalar',list(range(len(rows))),format_func=lambda i:f"{labels.get(str(rows[i]['employee_id']))} · {rows[i]['date']} · {rows[i].get('start') or rows[i].get('shift_code')}–{rows[i].get('end') or ''}",key=prefix+'_cleanup_pick')
        if st.button('Seçilen Atamaları Sil',disabled=not selected,key=prefix+'_cleanup_apply'):
            try:
                edit_shifts(state,deletions=[(rows[i]['employee_id'],rows[i]['date']) for i in selected]);state['shift_notice']='Seçili atamalar silindi. Boş günleri yeniden yerleştirebilir veya otomatik taslak oluşturabilirsin.';st.rerun()
            except ValueError as exc:st.error(str(exc))

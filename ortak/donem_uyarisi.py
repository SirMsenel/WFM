import pandas as pd

def existing_range(state,start,end):
    languages=state.get('planning_languages') or {'tr':True,'en':True,'ar':True};lookup={str(p['employee_id']):p.get('language','tr') for p in state.get('employees_cache',[])}
    return [r for r in state.get('published_shift_plan',[]) if str(start)<=r['date']<=str(end) and languages.get(r.get('language') or lookup.get(str(r['employee_id']),'tr'),True)]

def popup(state,start,end):
    import streamlit as st
    rows=existing_range(state,start,end)
    if not rows:return False
    state['_notification_intro_pending']=False
    @st.dialog('Bu Dönemin Vardiyası Yayında')
    def show():
        st.warning('Seçilen tarihler ve dil kapsamı zaten yayınlanmış. Yeni ihtiyaç/plan kaydı oluşturulmadı. Günlük düzenlemeler için Yayın Yönetimi ekranını kullanın.')
        st.caption(f'{start} – {end} · {len(rows)} personel-gün kaydı')
        if st.button('Anladım',key='existing_range_ack'):st.rerun()
    show();return True

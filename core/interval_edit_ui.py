import hashlib
import streamlit as st
from core.interval_editing import rebalance_profile


def edit_distribution(profile):
    from modules.shift_planner.intraday_ratio import matrix_table
    state=st.session_state;signature=hashlib.sha1(profile.to_json(date_format='iso').encode()).hexdigest()[:12]
    key='interval_edit_'+signature;cache=state.get(key,{'frame':profile,'pins':[],'version':0})
    current=cache['frame'];matrix=matrix_table(current)
    with st.expander('Yarım saat paylarını elle düzenle'):
        st.caption('Değiştirdiğin hücreler sabitlenir. Artış önce 03:00–08:00 paylarından, yetmezse diğer serbest dilimlerden düşülür. Azalışın boşalttığı pay önce 03:00–08:00 dilimlerine eklenir. Her gün yine %100 olur.')
        edited=st.data_editor(matrix,use_container_width=True,key=key+'_editor_'+str(cache['version']),column_config={c:st.column_config.NumberColumn(c,min_value=0.,max_value=100.,step=.01,format='%.2f') for c in matrix})
        summary=[{'Gün':c,'Girilen toplam (%)':round(edited[c].sum(),3),'Dengelenmesi gereken (%)':round(100-edited[c].sum(),3)} for c in edited]
        st.dataframe(summary,hide_index=True,use_container_width=True)
        a,b=st.columns(2)
        if a.button('Payları Dengele ve Uygula',key=key+'_apply'):
            try:
                frame,pins=rebalance_profile(current,edited,cache['pins'])
                state[key]={'frame':frame,'pins':pins,'version':cache['version']+1};st.rerun()
            except ValueError as exc:st.error(str(exc))
        if b.button('Elle Değişiklikleri Sıfırla',key=key+'_reset'):
            state[key]={'frame':profile,'pins':[],'version':cache['version']+1};st.rerun()
    return current,{'manual_adjusted':bool(cache['pins']),'pinned_cells':cache['pins']}

import streamlit as st
from ._common import month_selector_this_year, render_edit_placeholder, render_period_card


def render():
    st.subheader("🏖️ Yıllık İzin")
    year, month = month_selector_this_year("annual_leave")
    render_period_card(year, month)

    tab1, tab2, tab3 = st.tabs(["Akademi", "Arapça", "İngilizce"])

    with tab1:
        with st.container(border=True):
            st.markdown("#### Akademi Yıllık İzin")
            st.info("Akademi grubuna ait yıllık izinler burada listelenecek.")

    with tab2:
        with st.container(border=True):
            st.markdown("#### Arapça Yıllık İzin")
            st.info("Arapça dil grubuna ait yıllık izinler burada listelenecek.")

    with tab3:
        with st.container(border=True):
            st.markdown("#### İngilizce Yıllık İzin")
            st.info("İngilizce dil grubuna ait yıllık izinler burada listelenecek.")

    render_edit_placeholder("Yıllık İzin Düzenleme")

import streamlit as st
from ._common import month_selector_this_year, render_edit_placeholder, render_period_card


def render():
    st.subheader("🌙 Gece Vardiyası")
    year, month = month_selector_this_year("night")
    render_period_card(year, month)

    with st.container(border=True):
        st.markdown("#### Gece Vardiyası Kayıtları")
        st.info("Bu ekranı bir sonraki aşamada vardiya planından gelen gece kodlarıyla dolduracağız.")

    render_edit_placeholder("Gece Vardiyası Düzenleme")

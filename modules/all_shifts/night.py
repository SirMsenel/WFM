import streamlit as st
from ._common import month_selector_this_year, render_edit_placeholder, render_period_card
from ._fixed_records import render_fixed_records


def render():
    st.subheader("🌙 Gece Vardiyası")
    year, month = month_selector_this_year("night")
    render_period_card(year, month)

    with st.container(border=True):
        st.markdown("#### Gece Vardiyası Kayıtları")
        render_fixed_records("GECE", year, month)

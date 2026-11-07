import streamlit as st
from ._common import month_selector_this_year, render_edit_placeholder, render_period_card
from ._fixed_records import render_fixed_records


def render():
    st.subheader("🏖️ Yıllık İzin")
    year, month = month_selector_this_year("annual_leave")
    render_period_card(year, month)

    render_fixed_records("YILLIK_IZIN", year, month)

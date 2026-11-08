# Tum Vardiyalar / Gece — bu ekranın / servisin uygulama kodu.
import streamlit as st
from modules.tum_vardiyalar.ortak import month_selector_this_year, render_edit_placeholder, render_period_card
from modules.tum_vardiyalar.kesin_kayitlar import render_fixed_records


def render():
    st.subheader("🌙 Gece Vardiyası")
    year, month = month_selector_this_year("night")
    render_period_card(year, month)

    with st.container(border=True):
        st.markdown("#### Gece Vardiyası Kayıtları")
        render_fixed_records("GECE", year, month)

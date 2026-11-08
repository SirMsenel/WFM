# Tum Vardiyalar / Yillik Izin — bu ekranın / servisin uygulama kodu.
import streamlit as st
from modules.tum_vardiyalar.ortak import month_selector_this_year, render_edit_placeholder, render_period_card
from modules.tum_vardiyalar.kesin_kayitlar import render_fixed_records


def render():
    st.subheader("🏖️ Yıllık İzin")
    year, month = month_selector_this_year("annual_leave")
    render_period_card(year, month)

    render_fixed_records("YILLIK_IZIN", year, month)

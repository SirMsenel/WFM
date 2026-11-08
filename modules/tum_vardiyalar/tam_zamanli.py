# Tum Vardiyalar / Tam Zamanli — bu ekranın / servisin uygulama kodu.
import streamlit as st
from modules.tum_vardiyalar.ortak import month_selector_this_year, fetch_agents, render_edit_placeholder, render_period_card
from modules.tum_vardiyalar.takvim import render_shift_grid


def render():
    st.subheader("✅ Full Time")
    year, month = month_selector_this_year("fulltime")
    render_period_card(year, month)

    with st.container(border=True):
        q = st.text_input("Ara", key="ft_search", placeholder="isim...")
        agents = fetch_agents(work_type="fulltime", search=q or None)

        render_shift_grid(
            employees=agents,
            year=year,
            month=month,
            title="Full Time Vardiya Planı",
        )

    render_edit_placeholder("Full Time Düzenleme")

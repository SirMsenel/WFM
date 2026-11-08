# Tum Vardiyalar / Dis Kaynak — bu ekranın / servisin uygulama kodu.
import streamlit as st
from modules.tum_vardiyalar.ortak import (
    month_selector_this_year,
    fetch_agents,
    get_locations_by_work_type,
    render_edit_placeholder,
    render_period_card,
)
from modules.tum_vardiyalar.takvim import render_shift_grid


def render():
    st.subheader("🏢 Dış Kaynak")
    year, month = month_selector_this_year("outsource")
    render_period_card(year, month)

    locations = get_locations_by_work_type("dis_kaynak")
    if not locations:
        st.info("Dış kaynak lokasyon tanımı yok.")
        return

    tabs = st.tabs([loc.replace("Diyarbakir", "Diyarbakır") for loc in locations])

    for tab, loc in zip(tabs, locations):
        with tab:
            q = st.text_input(f"Ara - {loc}", key=f"out_{loc}_search", placeholder="isim...")
            agents = fetch_agents(work_type="dis_kaynak", location=loc, search=q or None)

            render_shift_grid(
                employees=agents,
                year=year,
                month=month,
                title=f"{loc} Dış Kaynak Vardiya Planı",
            )

    render_edit_placeholder("Dış Kaynak Düzenleme")

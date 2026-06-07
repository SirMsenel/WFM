import streamlit as st
from ._common import (
    month_selector_this_year,
    fetch_agents,
    get_locations_by_work_type,
    render_edit_placeholder,
    render_period_card,
)
from ._shift_grid import render_shift_grid


def render():
    st.subheader("🏫 Akademi")
    year, month = month_selector_this_year("academy")
    render_period_card(year, month)

    locations = get_locations_by_work_type("akademi")
    if not locations:
        st.info("Akademi lokasyon tanımı yok.")
        return

    tabs = st.tabs(locations)

    for tab, loc in zip(tabs, locations):
        with tab:
            q = st.text_input(f"Ara - {loc}", key=f"acad_{loc}_search", placeholder="isim...")
            agents = fetch_agents(work_type="akademi", location=loc, language="tr", search=q or None)

            render_shift_grid(
                employees=agents,
                year=year,
                month=month,
                title=f"{loc} Akademi Vardiya Planı",
            )

    render_edit_placeholder("Akademi Düzenleme")

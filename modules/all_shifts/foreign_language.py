import streamlit as st
from ._common import (
    month_selector_this_year,
    fetch_agents,
    render_edit_placeholder,
    render_period_card,
)
from ._shift_grid import render_shift_grid


LANG_LABELS = {
    "ar": "Arapça",
    "en": "İngilizce",
}


def render():
    st.subheader("🌍 Yabancı Dil")
    year, month = month_selector_this_year("foreign")
    render_period_card(year, month)

    tabs = st.tabs([LANG_LABELS["ar"], LANG_LABELS["en"]])

    for tab, lang in zip(tabs, ["ar", "en"]):
        with tab:
            q = st.text_input(f"Ara - {LANG_LABELS[lang]}", key=f"foreign_{lang}_search", placeholder="isim...")
            agents = fetch_agents(language=lang, search=q or None)

            render_shift_grid(
                employees=agents,
                year=year,
                month=month,
                title=f"{LANG_LABELS[lang]} Vardiya Planı",
            )

    render_edit_placeholder("Yabancı Dil Düzenleme")

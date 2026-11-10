# Tum Vardiyalar / Yabanci Dil — bu ekranın / servisin uygulama kodu.
import streamlit as st
from modules.tum_vardiyalar.ortak import (
    month_selector_this_year,
    fetch_agents,
    render_edit_placeholder,
    render_period_card,
)
from modules.tum_vardiyalar.takvim import render_shift_grid


LANG_LABELS = {
    "ar": "Arapça",
    "en": "İngilizce",
}


def render():
    from modules.tum_vardiyalar.ortak import roster_heading
    roster_heading('Yabancı Dil Vardiya Planı','🌍')
    year, month = month_selector_this_year("foreign")
    render_period_card(year, month)

    languages=sorted({e.get("language") for e in fetch_agents(limit=100000) if e.get("language") and e.get("language")!="tr"})
    if not languages:st.info("Yabancı dil personeli yok.");return
    tabs = st.tabs([LANG_LABELS.get(lang,lang) for lang in languages])

    for tab, lang in zip(tabs, languages):
        with tab:
            q = st.session_state.get('all_compact_search','')
            agents = fetch_agents(language=lang, search=q or None)

            render_shift_grid(
                employees=agents,
                year=year,
                month=month,
                title=f"{LANG_LABELS.get(lang,lang)} Vardiya Planı",
            )

    render_edit_placeholder("Yabancı Dil Düzenleme")

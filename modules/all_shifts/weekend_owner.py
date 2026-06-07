import streamlit as st
import pandas as pd
from ._common import month_selector_this_year, render_edit_placeholder, render_period_card


def render():
    st.subheader("📌 Hafta Sonu Sorumlusu")
    year, month = month_selector_this_year("weekend_owner")
    render_period_card(year, month)

    with st.container(border=True):
        st.markdown("#### Hafta Sonu Sorumlu Listesi")

        demo = pd.DataFrame(
            [
                {
                    "Tarih": "",
                    "Gün": "",
                    "Sorumlu Takım Lideri": "",
                    "Sorumlu Personel": "",
                    "08:00-17:00 Personel": "",
                    "17:00-00:00 Personel": "",
                    "Hat Sorumlusu": "",
                }
            ]
        )

        st.data_editor(
            demo,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            key="weekend_owner_editor",
        )

    render_edit_placeholder("Hafta Sonu Sorumlu Düzenleme")

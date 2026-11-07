import streamlit as st


def sections(key, pages):
    """Render only the selected sub-page; st.tabs eagerly executes every tab."""
    labels=list(pages)
    if st.session_state.get(key) not in labels:
        st.session_state[key]=labels[0]
    selected=st.segmented_control('Alt ekran',labels,key=key,selection_mode='single',default=labels[0])
    pages[selected or labels[0]]()

from copy import deepcopy
import streamlit as st


@st.cache_data(ttl=60,show_spinner=False)
def cached_calls(path,interval=False):
    from core.workspace_store import load_calls
    return load_calls(interval,path)


@st.cache_resource(show_spinner=False,max_entries=4)
def _reference_models(history):
    from core.forecast_service import reference_models
    result={}
    reference_models(result,history)
    return result


def demo_model_snapshot(history):
    # UI training must not mutate a model shared by another Streamlit session.
    return deepcopy(_reference_models(history))

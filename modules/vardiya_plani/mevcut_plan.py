# Vardiya Plani / Mevcut Plan — bu ekranın / servisin uygulama kodu.
import os
import requests
import streamlit as st
from datetime import time

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8001")


def _api_get(path: str, token: str | None = None, params: dict | None = None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(f"{BACKEND_URL}{path}", params=params, headers=headers, timeout=20)
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail")
        except Exception:
            detail = r.text
        raise RuntimeError(detail)
    return r.json()


def render(profile=None):
    profile = profile or st.session_state.get("profile") or {}
    token = st.session_state.get("auth_token")

    part=st.segmented_control('Mevcut plan bölümü',['Personel Özeti','Mesai Kuralları','Statü Kuralları'],default='Personel Özeti',key='nav_current_plan_v2',label_visibility='collapsed')
    if part=='Personel Özeti':
        from ortak.personel import get_people,personnel_summary
        from ortak.personel_grafikleri import render_summary
        render_summary(personnel_summary(get_people(st.session_state)))
        from ortak.calisma_sureleri_ekrani import render_hours_summary
        render_hours_summary(st.session_state,get_people(st.session_state))

    if part=='Statü Kuralları':
        from modules.statu_kurallari import render
        render()
    if part=='Mesai Kuralları':
        from modules.vardiya_kurallari import render
        render()

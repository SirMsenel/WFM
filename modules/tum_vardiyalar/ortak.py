# Tum Vardiyalar / Ortak — bu ekranın / servisin uygulama kodu.
# modules/all_shifts/_common.py
import os
import calendar
from datetime import datetime

import requests
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8001")

ACA_LOCS_DEFAULT = ["Ankara", "Konya", "Izmir"]
OUTSOURCE_LOCS_DEFAULT = ["Adana", "Diyarbakir"]
FOREIGN_LANGS = ["ar", "en"]


def api_get(path: str, token: str | None = None, params: dict | None = None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(f"{BACKEND_URL}{path}", params=params, headers=headers, timeout=15)
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail")
        except Exception:
            detail = r.text
        raise RuntimeError(detail)
    return r.json()


def get_profile() -> dict:
    return st.session_state.get("profile") or {}


def role() -> str:
    return (get_profile().get("position") or "").lower().strip()


def can_edit() -> bool:
    from ortak.roller_ve_yetkiler import permissions
    return 'vardiya_degistir' in permissions(st.session_state)


def month_selector_this_year(key_prefix="allshifts"):
    now=datetime.now()
    years={now.year+i for i in range(-3,4)}
    years.update(int(r['date'][:4]) for r in st.session_state.get('published_shift_plan',[]) if r.get('date'))
    a,b,_=st.columns([1,1.6,3])
    year=a.selectbox('Yıl',sorted(years),index=sorted(years).index(now.year),key='all_period_year')
    months=['Ocak','Şubat','Mart','Nisan','Mayıs','Haziran','Temmuz','Ağustos','Eylül','Ekim','Kasım','Aralık']
    month=b.selectbox('Ay',list(range(1,13)),index=now.month-1,format_func=lambda m:months[m-1],key='all_period_month')
    return year,month


def render_period_card(year,month):
    return



def fetch_agents(
    work_type: str | None = None,
    location: str | None = None,
    language: str | None = None,
    search: str | None = None,
    limit: int | None = None,
):
    from ortak.personel import get_people
    from ortak.personel_deposu import list_people
    people=list_people(st.session_state,True) if st.session_state.get('all_include_inactive') else get_people(st.session_state)
    rows=[r for r in people if r.get('position')=='agent'
          and (not work_type or r.get('work_type')==work_type)
          and (not location or (r.get('location') or 'Belirtilmemiş')==location)
          and (not language or r.get('language')==language)
          and (not search or search.casefold() in ' '.join(str(r.get(k,'')) for k in ['full_name','sicil_no','username']).casefold())]
    return rows if limit is None else rows[:limit]


def get_locations_by_work_type(work_type):
    return sorted({str(r.get('location') or 'Belirtilmemiş') for r in fetch_agents(work_type=work_type,limit=100000)})


def render_edit_placeholder(title):
    return

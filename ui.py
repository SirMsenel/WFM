import os
import requests
import streamlit as st

# ---------------- Page Config ----------------
st.set_page_config(page_title="WFM", layout="wide")

# ---------------- Login Screen ----------------
from modules.auth.login_screen import require_login

# ---------------- Call Forecast ----------------
from modules.call_forecast.data_source import render as render_call_forecast_data
from modules.call_forecast.feature_engineering import render as render_feature_engineering
from modules.call_forecast.outlier_iqr import render as render_outlier_iqr
from modules.call_forecast.monitoring import render as render_monitoring
from modules.call_forecast.data_quality import render as render_data_quality
from modules.call_forecast.modeling import render as render_modeling
from modules.call_forecast.model_report import render as render_model_report
from modules.call_forecast.predict_ui import render as render_predict_ui

# ---------------- Shift Planner ----------------
from modules.shift_planner.forecast_view import render as render_forecast_view
from modules.shift_planner.intraday_ratio import render as render_intraday_ratio
from modules.shift_planner.ratio_profile_select import render as render_profile_select
from modules.shift_planner.staffing_forecast import render as render_staffing_forecast

# ---------------- Shift Planning ----------------
from modules.shift_planing.period import render as render_plan_period
from modules.shift_planing.current_plan import render as render_current_plan
from modules.shift_planing.requests_tab import render as render_requests_tab
from modules.shift_planing.shift_hours import render as render_shift_hours
from modules.shift_planing.publish import render as render_publish

# ---------------- Tracking ----------------
from modules.tracking.my_shift import render as render_my_shift
from modules.tracking.class_schedule import render as render_class_schedule
from modules.tracking.requests_submit import render as render_requests_submit
from modules.tracking.requests_inbox import render as render_requests_inbox

# ---------------- All Shifts ----------------
from modules.all_shifts.fulltime import render as render_all_fulltime
from modules.all_shifts.academy import render as render_all_academy
from modules.all_shifts.outsource import render as render_all_outsource
from modules.all_shifts.night import render as render_all_night
from modules.all_shifts.annual_leave import render as render_all_annual_leave
from modules.all_shifts.weekend_owner import render as render_all_weekend_owner
from modules.all_shifts.foreign_language import render as render_all_foreign_language


# ---------------- Personel Takip ----------------
from modules.PersonelTakip.Personel_talep import render as render_personel_talep


# ---------------- Backend ----------------
BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8001")


# ---------------- API Helpers ----------------
def _api_post(path: str, payload: dict, token: str | None = None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    r = requests.post(
        f"{BACKEND_URL}{path}",
        json=payload,
        headers=headers,
        timeout=15,
    )

    if r.status_code >= 400:
        try:
            detail = r.json().get("detail")
        except Exception:
            detail = r.text
        raise RuntimeError(detail)

    return r.json()


def _api_get(path: str, token: str | None = None, params: dict | None = None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    r = requests.get(
        f"{BACKEND_URL}{path}",
        params=params,
        headers=headers,
        timeout=15,
    )

    if r.status_code >= 400:
        try:
            detail = r.json().get("detail")
        except Exception:
            detail = r.text
        raise RuntimeError(detail)

    return r.json()


# ---------------- Login Check ----------------
require_login(_api_get=_api_get, _api_post=_api_post)


# ---------------- Global Sidebar Style ----------------
st.markdown("""
<style>
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #ffffff 0%, #fcfcfd 45%, #f7f8fa 100%);
        border-right: 1px solid rgba(15, 23, 42, 0.06);
    }

    section[data-testid="stSidebar"] .block-container {
        padding-top: 1.2rem;
        padding-bottom: 1rem;
    }

    /* ---------- Profil Kartı ---------- */

    .sidebar-profile-card {
        background: rgba(255, 255, 255, 0.95);
        border: 1px solid rgba(15, 23, 42, 0.08);
        border-radius: 20px;
        padding: 18px;
        box-shadow: 0 10px 26px rgba(15, 23, 42, 0.07);
        margin-bottom: 14px;
    }

    .sidebar-profile-top {
        display: flex;
        align-items: center;
        gap: 14px;
    }

    .sidebar-avatar {
        width: 52px;
        height: 52px;
        min-width: 52px;
        border-radius: 16px;
        background: linear-gradient(135deg, #f3f4f6, #e5e7eb);
        border: 1px solid rgba(15, 23, 42, 0.08);
        display: flex;
        align-items: center;
        justify-content: center;
        color: #111827;
        font-size: 20px;
        font-weight: 700;
    }

    .sidebar-user-meta {
        line-height: 1.3;
    }

    .sidebar-user-name {
        color: #111827;
        font-size: 16px;
        font-weight: 700;
        margin-bottom: 5px;
    }

    .sidebar-user-username {
        color: #6b7280;
        font-size: 13px;
        margin-bottom: 6px;
    }

    .sidebar-role-badge {
        display: inline-block;
        padding: 5px 12px;
        border-radius: 999px;
        background: #f8fafc;
        border: 1px solid rgba(15, 23, 42, 0.08);
        color: #374151;
        font-size: 12px;
        font-weight: 600;
    }

    /* ---------- Divider ---------- */

    .sidebar-divider {
        height: 1px;
        background: linear-gradient(90deg, rgba(15,23,42,0.10), rgba(15,23,42,0.03));
        margin: 14px 0 16px 0;
        border-radius: 999px;
    }

    .sidebar-menu-title {
        color: #374151;
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.4px;
        margin: 0 0 12px 2px;
        text-transform: uppercase;
    }

    /* ---------- Aktif Menü ---------- */

    .active-menu-item {
        background: linear-gradient(90deg, #f3f4f6 0%, #eef2f7 100%);
        border: 1px solid rgba(15, 23, 42, 0.08);
        border-left: 5px solid #9ca3af;
        color: #111827;
        border-radius: 14px;
        padding: 14px 14px;
        font-size: 14px;
        font-weight: 700;
        margin-bottom: 10px;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
    }

    /* ---------- Menü Butonları ---------- */

    div.stButton > button {
        background: #ffffff !important;
        color: #374151 !important;
        border-radius: 14px !important;
        min-height: 50px !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        border: 1px solid rgba(15, 23, 42, 0.08) !important;
        box-shadow: 0 3px 10px rgba(15, 23, 42, 0.04) !important;
        transition: all 0.18s ease !important;
    }

    div.stButton > button:hover {
        background: #f9fafb !important;
        color: #111827 !important;
        border: 1px solid rgba(15, 23, 42, 0.12) !important;
        transform: translateY(-1px);
    }

    div.stButton > button p {
        font-size: 14px !important;
    }
</style>
""", unsafe_allow_html=True)


# ---------------- Role & Pages ----------------
PAGES = [
    "📞 Çağrı Tahmini",
    "📅 Mesai Planı",
    "🗓️ Vardiya Planı",
    "📊 İzleme",
    "👥 Personel Takip",
    "📌 Takip",
    "🗓️ Tüm Vardiyalar",
    "⚙️ Ayarlar",
]


def get_role(profile: dict) -> str:
    return (profile.get("position") or "").lower().strip()


def get_allowed_pages(profile: dict) -> set[str]:
    role = get_role(profile)
    base = {"📌 Takip", "🗓️ Tüm Vardiyalar", "⚙️ Ayarlar"}

    if role == "agent":
        return base

    if role == "tl":
        return base | {"📊 İzleme", "👥 Personel Takip"}

    return set(PAGES)


# ---------------- Main App ----------------
st.session_state.setdefault("main_page", "📌 Takip")

profile = st.session_state.get("profile") or {}
allowed_pages = get_allowed_pages(profile)

if st.session_state["main_page"] not in allowed_pages:
    st.session_state["main_page"] = "📌 Takip"

with st.sidebar:
    full_name = profile.get("full_name", "") or "Kullanıcı"
    username = profile.get("username", "") or "-"
    role = profile.get("position", "") or "-"
    initials = full_name[:1].upper() if full_name else "U"

    st.markdown(
        f"""
        <div class="sidebar-profile-card">
            <div class="sidebar-profile-top">
                <div class="sidebar-avatar">{initials}</div>
                <div class="sidebar-user-meta">
                    <div class="sidebar-user-name">{full_name}</div>
                    <div class="sidebar-user-username">@{username}</div>
                    <div class="sidebar-role-badge">{role}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Çıkış Yap", use_container_width=True):
        st.session_state["auth_token"] = None
        st.session_state["profile"] = None
        st.rerun()

    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-menu-title">Navigasyon</div>', unsafe_allow_html=True)

    for page in PAGES:
        if page not in allowed_pages:
            continue

        if st.session_state["main_page"] == page:
            st.markdown(
                f'<div class="active-menu-item">{page}</div>',
                unsafe_allow_html=True,
            )
        else:
            if st.button(page, use_container_width=True, key=f"menu_{page}"):
                st.session_state["main_page"] = page
                st.rerun()

main = st.session_state["main_page"]


# ---------------- Routing ----------------
if main == "📞 Çağrı Tahmini":
    st.title("📞 Çağrı Tahmini")
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
        [
            "1) Veri Kaynağı",
            "2) Feature Engineering",
            "3) Veri Kalitesi",
            "4) Aykırı Değer (IQR)",
            "5) Grafik İzleme",
            "6) Model Kur",
            "7) Model Raporu",
            "8) Tahmin",
        ]
    )
    with tab1:
        render_call_forecast_data()
    with tab2:
        render_feature_engineering()
    with tab3:
        render_data_quality()
    with tab4:
        render_outlier_iqr()
    with tab5:
        render_monitoring()
    with tab6:
        render_modeling()
    with tab7:
        render_model_report()
    with tab8:
        render_predict_ui()

elif main == "📅 Mesai Planı":
    st.title("📅 Mesai Planı")
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "1) Tahmin",
            "2) İnterval",
            "3) Kayıt Seçim",
            "4) Personel Hesap",
        ]
    )
    with tab1:
        render_forecast_view()
    with tab2:
        render_intraday_ratio()
    with tab3:
        render_profile_select()
    with tab4:
        render_staffing_forecast()

elif main == "🗓️ Vardiya Planı":
    st.title("🗓️ Vardiya Planı")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "1) Plan Dönem Seçimi",
            "2) Mevcut Plan",
            "3) Talepler",
            "4) Vardiya Saatleri",
            "5) Oluştur & Kontrol & Yayınla",
        ]
    )

    with tab1:
        render_plan_period()
    with tab2:
        render_current_plan()
    with tab3:
        render_requests_tab()
    with tab4:
        render_shift_hours()
    with tab5:
        render_publish()

elif main == "📊 İzleme":
    st.title("📊 İzleme")
    st.info("İzleme ekranı (yakında).")

elif main == "👥 Personel Takip":
    st.title("👥 Personel Takip")
    a1,a2 = st.tabs([
        "👤 Personel Talepleri",
        "Personel İzleme",
    ])

    with a1:
        render_personel_talep()

elif main == "📌 Takip":
    st.title("📌 Takip")
    st.caption("Vardiyalar ve talepler.")

    tab1, tab2, tab3, tab4 = st.tabs([
        "🧍 Benim Vardiyam",
        "📚 Ders Programı",
        "📝 Talep İlet",
        "📬 Talep Sonuç",
    ])

    with tab1:
        render_my_shift()
    with tab2:
        render_class_schedule()
    with tab3:
        render_requests_submit()
    with tab4:
        render_requests_inbox()

elif main == "🗓️ Tüm Vardiyalar":
    st.title("🗓️ Tüm Vardiyalar")
    st.caption("Agent izler. TL ve üzeri roller düzenleme yapabilir.")

    t1, t2, t3, t4, t5, t6, t7 = st.tabs([
        "✅ Full Time",
        "🏢 Dış Kaynak",
        "🌍 Yabancı Dil",
        "🏫 Akademi",
        "🌙 Gece",
        "🏖️ Yıllık İzin",
        "📌 Hafta Sonu Sorumlu",
    ])

    with t1:
        render_all_fulltime()
    with t2:
        render_all_outsource()
    with t3:
        render_all_foreign_language()
    with t4:
        render_all_academy()
    with t5:
        render_all_night()
    with t6:
        render_all_annual_leave()
    with t7:
        render_all_weekend_owner()


elif main == "⚙️ Ayarlar":
    st.title("⚙️ Ayarlar")
    st.info("Ayarlar ekranı (yakında).")
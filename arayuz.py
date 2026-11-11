# Arayuz — bu ekranın / servisin uygulama kodu.
import os
import requests
import streamlit as st

# ---------------- Page Config ----------------
st.set_page_config(page_title="WFM", layout="wide")

# ---------------- Login Screen ----------------
from modules.kimlik.giris_ekrani import require_login

# ---------------- Call Forecast ----------------
from modules.cagri_tahmini.veri_kaynagi import render as render_call_forecast_data
from modules.cagri_tahmini.etken_uretimi import render as render_feature_engineering
from modules.cagri_tahmini.aykiri_deger import render as render_outlier_iqr
from modules.cagri_tahmini.grafik_izleme import render as render_monitoring
from modules.cagri_tahmini.veri_kalitesi import render as render_data_quality
from modules.cagri_tahmini.model_kur import render as render_modeling
from modules.cagri_tahmini.model_raporu import render as render_model_report
from modules.cagri_tahmini.tahmin import render as render_predict_ui

# ---------------- Shift Planner ----------------
from modules.mesai_plani.tahmin_kaynagi import render as render_forecast_view
from modules.mesai_plani.interval_dagilimi import render as render_intraday_ratio
from modules.mesai_plani.kayit_secimi import render as render_profile_select
from modules.mesai_plani.personel_ihtiyaci import render as render_staffing_forecast

# ---------------- Shift Planning ----------------
from modules.vardiya_plani.donem_secimi import render as render_plan_period
from modules.vardiya_plani.mevcut_plan import render as render_current_plan
from modules.vardiya_plani.talepler import render as render_requests_tab
from modules.vardiya_plani.vardiya_saatleri import render as render_shift_hours
from modules.vardiya_plani.olustur_kontrol_yayinla import render as render_publish
from modules.vardiya_plani.yayin_yonetimi import render as render_publication_management

# ---------------- Tracking ----------------
from modules.takip.benim_vardiyam import render as render_my_shift
from modules.takip.ders_programi import render as render_class_schedule
from modules.takip.talep_ilet import render as render_requests_submit
from modules.takip.talep_sonuclari import render as render_requests_inbox

# ---------------- All Shifts ----------------
from modules.tum_vardiyalar.tam_zamanli import render as render_all_fulltime
from modules.tum_vardiyalar.akademi import render as render_all_academy
from modules.tum_vardiyalar.dis_kaynak import render as render_all_outsource
from modules.tum_vardiyalar.gece import render as render_all_night
from modules.tum_vardiyalar.yillik_izin import render as render_all_annual_leave
from modules.tum_vardiyalar.hafta_sonu_sorumlu import render as render_all_weekend_owner
from modules.tum_vardiyalar.yabanci_dil import render as render_all_foreign_language


# ---------------- Personel Takip ----------------
from modules.personel_takip.personel_talepleri import render as render_personel_talep
from modules.mesai_plani.gecmis_hafta_analizi import render as render_history_comparison
from modules.ornek_calisma_alani import render as render_demo_workspace
from modules.personel_takip.personel_listesi import render as render_personnel_list


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

from ortak.ornek_veri import bootstrap
bootstrap(st.session_state)


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
        padding: 14px;
        box-shadow: 0 10px 26px rgba(15, 23, 42, 0.07);
        margin-bottom: 14px;
    }

    .sidebar-profile-top {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .sidebar-avatar {
        width: 42px;
        height: 52px;
        min-width: 42px;
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
        min-width:0;flex:1;overflow-wrap:anywhere;
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
    "📈 Güncel Takip Analizi",
    "🗓️ Vardiya Planı",
    "📊 İzleme",
    "📆 Ajanda",
    "📥 Onay Merkezi",
    "🔮 Similasyon",
    "🧾 Fatura Mutabakat",
    "👥 Personel Takip",
    "📌 Takip",
    "🗓️ Tüm Vardiyalar",
    "🧪 Demo Veritabanı",
    "🗃️ Veri ve Kayıt Merkezi",
    "⚙️ Ayarlar",
]


def get_role(profile: dict) -> str:
    return (profile.get("position") or "").lower().strip()


def get_allowed_pages(profile):
    from ortak.erisim import allowed_pages
    return allowed_pages(profile,PAGES)


# ---------------- Main App ----------------
from ortak.erisim import landing_page
st.session_state.setdefault("main_page", landing_page(st.session_state.get("profile") or {}))

profile = st.session_state.get("profile") or {}
allowed_pages = get_allowed_pages(profile)

if st.session_state["main_page"] not in allowed_pages:
    st.session_state["main_page"] = landing_page(profile)

with st.sidebar:
    full_name = profile.get("full_name", "") or "Kullanıcı"
    username = profile.get("username", "") or "-"
    from ortak.roller_ve_yetkiler import ROLE_LABELS
    role = ROLE_LABELS.get(profile.get("position"),profile.get("position") or "-")
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

    from ortak.bildirimler import items as notification_items
    unseen=sum(not p['Okundu'] for p in notification_items(st.session_state))
    if st.button(f'🔔 Bildirimler ({unseen})',key='open_notifications',use_container_width=True):
        st.session_state['main_page']='⚙️ Ayarlar';st.session_state['nav_settings']='Bildirimler';st.rerun()
    from ortak.moderator_gecis import render as render_switch
    render_switch(st.session_state,_api_get,_api_post)
    if st.button("Çıkış Yap", use_container_width=True):
        from ortak.calisma_alani_deposu import save_keys
        save_keys(st.session_state)
        st.session_state["auth_token"] = None
        st.session_state["profile"] = None
        st.session_state.pop("_moderator_origin",None)
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
                from ortak.gezinme import navigate
                navigate(st.session_state,page)
                st.rerun()

if st.session_state.get('navigation_history'):
    from ortak.gezinme import go_back
    if st.sidebar.button('← Önceki Ekrana Dön',key='go_previous'):
        go_back(st.session_state);st.rerun()
st.markdown('<style>.stMainBlockContainer{padding-top:2.1rem!important}h1{padding-top:.15rem!important}</style>',unsafe_allow_html=True)
from ortak.arayuz_tasarimi import APP_CSS
st.markdown(APP_CSS,unsafe_allow_html=True)
main = st.session_state["main_page"]


# ---------------- Routing ----------------
from ortak.gezinme import sections

if main == "📞 Çağrı Tahmini":
    st.title(main)
    sections('nav_forecast',{
        'Veri Kaynağı':render_call_forecast_data,'Feature Engineering':render_feature_engineering,
        'Veri Kalitesi':render_data_quality,'Aykırı Değer (IQR)':render_outlier_iqr,
        'Grafik İzleme':render_monitoring,'Model Kur':render_modeling,
        'Model Raporu':render_model_report,'Tahmin':render_predict_ui})
elif main == "📅 Mesai Planı":
    st.title(main)
    sections('nav_staffing',{'Tahmin Kaynağı':render_forecast_view,'İnterval':render_intraday_ratio,
                            'Kayıt Seçim':render_profile_select,'Personel Hesap':render_staffing_forecast})
elif main == "🗓️ Vardiya Planı":
    st.title(main)
    sections('nav_roster',{'Plan Dönem Seçimi':render_plan_period,'Vardiya Kuralları':render_current_plan,
                          'Talepler':render_requests_tab,'Vardiya Saatleri':render_shift_hours,'Yabancı Dil Planı':__import__('modules.vardiya_plani.yabanci_dil_plani',fromlist=['render']).render,
                          'Oluştur & Kontrol & Yayınla':render_publish,'Yayın Yönetimi':render_publication_management,'Yayın Onayları':__import__('modules.yayin_onay_ekrani',fromlist=['render']).render})
elif main == "📈 Güncel Takip Analizi":
    render_history_comparison()
elif main == "🧪 Demo Veritabanı":
    render_demo_workspace()
elif main == "👥 Personel Takip":
    st.title(main)
    sections('nav_personnel',{'Personel Talepleri':render_personel_talep,'Personel Listesi':render_personnel_list,'Personel Ekleme / Ayrılma':__import__('modules.personel_takip.personel_yasam_dongusu',fromlist=['render']).render})
elif main == "📌 Takip":
    sections('nav_tracking',{'Benim Vardiyam':render_my_shift,'Ders Programı':render_class_schedule,
                            'Talep İlet':render_requests_submit,'Talep Sonuç':render_requests_inbox})
elif main == "🗓️ Tüm Vardiyalar":
    st.title(main)
    if profile.get("position")!="agent":st.toggle("Ayrılan personellerin eski vardiyalarını da göster",value=False,key="all_include_inactive")
    sections('nav_all_shifts',{'Full Time':render_all_fulltime,'Dış Kaynak':render_all_outsource,
                              'Yabancı Dil':render_all_foreign_language,'Akademi':render_all_academy,
                              'Gece':render_all_night,'Yıllık İzin':render_all_annual_leave,
                              'Hafta Sonu Sorumlu':render_all_weekend_owner,'Değişim Alanı':__import__('modules.tum_vardiyalar.vardiya_duzenleme',fromlist=['render']).render})
elif main == '📆 Ajanda':
    from modules.ajanda import render
    render()
elif main == '📥 Onay Merkezi':
    from modules.onay_merkezi import render
    render()
elif main == "📊 İzleme":
    from modules.mola_izleme import render as render_monitor
    render_monitor()

elif main == "🔮 Similasyon":
    from modules.similasyon import render
    render()
elif main == "🧾 Fatura Mutabakat":
    st.title(main);st.info("Bu alan sonraki faz için ayrıldı.")
elif main == "🗃️ Veri ve Kayıt Merkezi":
    from modules.kayit_merkezi import render as render_registry
    render_registry()
elif main == "⚙️ Ayarlar":
    from modules.ayarlar import render as render_settings
    render_settings()

from ortak.bildirim_popup import render as render_welcome_notices
render_welcome_notices(st.session_state)
from ortak.calisma_alani_deposu import save_keys
save_keys(st.session_state)

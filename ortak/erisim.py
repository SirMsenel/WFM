"""Erişim — role göre menü ve ilk giriş ekranı."""
from ortak.calisma_modu import demo_enabled


def landing_page(profile):
    role=(profile or {}).get('position')
    return '🗓️ Vardiya Planı' if role=='wfm' else '📌 Takip' if role in {'tl','manager','moderator','planning_manager'} else '📌 Takip'


def allowed_pages(profile,pages):
    role=(profile or {}).get('position');base={'📌 Takip','🗓️ Tüm Vardiyalar','📊 İzleme','⚙️ Ayarlar'}
    if demo_enabled():base.add('🧪 Demo Veritabanı')
    if role=='tl':base.add('👥 Personel Takip')
    elif role in {'wfm','manager','moderator','planning_manager'}:
        base=set(pages)

        if not demo_enabled():base.discard('🧪 Demo Veritabanı')
    return base


def enter_session(state,profile):
    """Yeni hesap eski kullanıcının alt ekranı veya personel filtresiyle açılmaz."""
    for key in list(state):
        if key.startswith(('nav_','my_shift_','all_change_','personal_change_','new_request_','report_','monitor_','academic_staff_','school_cards_','travel_','break_','feedback_' )):
            state.pop(key,None)
    state.pop('status_rules_edit',None)
    state['main_page']=landing_page(profile);state['navigation_history']=[]

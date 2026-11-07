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

    st.subheader('Mevcut Plan')
    part=st.segmented_control('Mevcut plan bölümü',['Personel Özeti','Mesai Kuralları','Çalışma Süreleri'],default='Personel Özeti',key='nav_current_plan_v2')
    if part=='Personel Özeti':
        from core.personnel import get_people,personnel_summary
        from core.personnel_charts import render_summary
        render_summary(personnel_summary(get_people(st.session_state)))
        from core.work_hours_ui import render_hours_summary
        render_hours_summary(st.session_state,get_people(st.session_state))
        st.caption('Personel listesi Personel Takip → Personel Listesi ekranındadır.')

    if part=='Çalışma Süreleri':
        from core.work_hours_ui import render_targets
        render_targets(st.session_state)

    if part=='Mesai Kuralları':
        # --- helpers ---
        def _init_rules():
            from core.defaults import default_shift_rules
            st.session_state.setdefault("shift_rules", default_shift_rules())

        def _t(s: str) -> time:
            hh, mm = s.split(":")
            return time(int(hh), int(mm))

        def _tstr(t0: time) -> str:
            return f"{t0.hour:02d}:{t0.minute:02d}"

        _init_rules()
        rules = st.session_state["shift_rules"]
        from core.defaults import enforce_current_rules
        enforce_current_rules(st.session_state)
        from copy import deepcopy
        rules=deepcopy(st.session_state.get('shift_rules_draft') or st.session_state['shift_rules'])

        st.markdown("### 🧩 Mesai Kuralları")
        st.info("Bu ekrandaki kurallar çalışma alanı veritabanına kaydedilir." if st.session_state.get('workspace_db_path') else "Kurallar bu oturum için kaydedilir.")

        # ------------------------------------------------------
        # 1) Gün başlangıçları
        # ------------------------------------------------------
        with st.container(border=True):
            st.markdown("#### Gün başlangıçları")

            c1, c2 = st.columns(2)
            with c1:
                wd = st.time_input(
                    "Hafta içi genel giriş (min başlangıç)",
                    value=_t(rules["general"]["weekday_general_start"]),
                    key="rule_weekday_general_start",
                )
                rules["general"]["weekday_general_start"] = _tstr(wd)

            with c2:
                we = st.time_input(
                    "Hafta sonu genel giriş (min başlangıç)",
                    value=_t(rules["general"]["weekend_general_start"]),
                    key="rule_weekend_general_start",
                )
                rules["general"]["weekend_general_start"] = _tstr(we)

            st.markdown("---")

            b1, b2 = st.columns([1, 1.2])
            with b1:
                rules["boosts"]["weekday_0700_fulltime_extra_enabled"] = st.toggle(
                    "Hafta içi 07:00 Full Time takviyesi aktif",
                    value=bool(rules["boosts"]["weekday_0700_fulltime_extra_enabled"]),
                    key="rule_ft_0700_boost_enabled",
                )
            with b2:
                rules["boosts"]["weekday_0700_fulltime_extra_count"] = st.number_input(
                    "07:00 ek Full Time sayısı",
                    min_value=0,
                    max_value=50,
                    value=int(rules["boosts"]["weekday_0700_fulltime_extra_count"]),
                    step=1,
                    key="rule_ft_0700_boost_count",
                )

        # ------------------------------------------------------
        # 2) Bitiş limitleri
        # ------------------------------------------------------
        with st.container(border=True):
            st.markdown("#### Bitiş limitleri")

            global_end = st.time_input(
                "Global max bitiş (hard limit)",
                value=_t(rules["general"].get("global_latest_end", "03:00")),
                key="rule_global_latest_end",
            )
            rules["general"]["global_latest_end"] = _tstr(global_end)
            st.caption("Hard limit: plan oluştururken bu saati aşan vardiya yazdırılmaz.")

            st.markdown("---")

            st.markdown("**Dış kaynak**")
            c1, c2, c3 = st.columns([1, 1, 1.6])
            with c1:
                dk_end = st.time_input(
                    "Max bitiş",
                    value=_t(rules["work_type"]["dis_kaynak"]["max_end_time"]),
                    key="rule_dk_max_end_time",
                )
                rules["work_type"]["dis_kaynak"]["max_end_time"] = _tstr(dk_end)

            with c2:
                rules["work_type"]["dis_kaynak"]["max_end_is_hard"] = st.radio(
                    "Kural tipi",
                    options=[False, True],
                    format_func=lambda x: "Soft (uyar)" if x is False else "Hard (engelle)",
                    index=1 if rules["work_type"]["dis_kaynak"]["max_end_is_hard"] else 0,
                    key="rule_dk_end_hard_soft",
                    horizontal=True,
                )

            with c3:
                rules["work_type"]["dis_kaynak"]["override_required_if_violate"] = st.toggle(
                    "Soft ihlalde onay iste",
                    value=bool(rules["work_type"]["dis_kaynak"]["override_required_if_violate"]),
                    help="Soft kural aşıldığında kullanıcıdan devam onayı alınsın mı?",
                    key="rule_dk_override_required",
                )

            st.markdown("---")

            st.markdown("**Akademi**")
            c1, c2, c3 = st.columns([1, 1, 1.6])
            with c1:
                ak_end = st.time_input(
                    "Max bitiş",
                    value=_t(rules["work_type"]["akademi"]["max_end_time"]),
                    key="rule_ak_max_end_time",
                )
                rules["work_type"]["akademi"]["max_end_time"] = _tstr(ak_end)

            with c2:
                rules["work_type"]["akademi"]["max_end_is_hard"] = st.radio(
                    "Kural tipi",
                    options=[False, True],
                    format_func=lambda x: "Soft (uyar)" if x is False else "Hard (engelle)",
                    index=1 if rules["work_type"]["akademi"]["max_end_is_hard"] else 0,
                    key="rule_ak_end_hard_soft",
                    horizontal=True,
                )

            with c3:
                rules["work_type"]["akademi"]["override_required_if_violate"] = st.toggle(
                    "Soft ihlalde onay iste",
                    value=bool(rules["work_type"]["akademi"]["override_required_if_violate"]),
                    help="Soft kural aşıldığında kullanıcıdan devam onayı alınsın mı?",
                    key="rule_ak_override_required",
                )

        # ------------------------------------------------------
        # 3) Gece planlaması
        # ------------------------------------------------------
        with st.container(border=True):
            st.markdown("#### Gece planlaması (00:00–08:00)")

            night = rules["night"]

            c1, c2 = st.columns([1, 1.2])
            with c1:
                night["enabled"] = st.toggle(
                    "Gece planlaması aktif",
                    value=bool(night["enabled"]),
                    key="rule_night_enabled",
                )

            if not night["enabled"]:
                st.info("Gece planlaması kapalı. Gece ihtiyacı ve gece çalışma izinleri dikkate alınmayacak.")
            else:
                with c2:
                    night["mode"] = st.selectbox(
                        "İhtiyaç modu",
                        options=["normal", "ramazan", "ozel"],
                        index=["normal", "ramazan", "ozel"].index(night.get("mode", "normal")),
                        format_func=lambda x: {"normal": "Normal", "ramazan": "Ramazan", "ozel": "Özel"}[x],
                        key="rule_night_mode",
                    )

                st.markdown("---")
                w1, w2 = st.columns(2)
                with w1:
                    ns = st.time_input(
                        "Gece pencere başlangıç",
                        value=_t(rules["general"]["night_window_start"]),
                        key="rule_night_window_start",
                    )
                    rules["general"]["night_window_start"] = _tstr(ns)

                with w2:
                    ne = st.time_input(
                        "Gece pencere bitiş",
                        value=_t(rules["general"]["night_window_end"]),
                        key="rule_night_window_end",
                    )
                    rules["general"]["night_window_end"] = _tstr(ne)

                st.markdown("---")
                st.caption("Dil kırılımı: TR / EN / AR adet")

                def _need_block(title, key_prefix, payload):
                    st.markdown(f"**{title}**")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        payload["tr"] = st.number_input("TR", 0, 50, int(payload.get("tr", 0)), 1, key=f"{key_prefix}_tr")
                    with c2:
                        payload["en"] = st.number_input("EN", 0, 50, int(payload.get("en", 0)), 1, key=f"{key_prefix}_en")
                    with c3:
                        payload["ar"] = st.number_input("AR", 0, 50, int(payload.get("ar", 0)), 1, key=f"{key_prefix}_ar")

                if night["mode"] == "normal":
                    _need_block("Normal gece ihtiyacı", "night_normal", night["normal"])
                elif night["mode"] == "ramazan":
                    _need_block("Ramazan gece ihtiyacı", "night_ramazan", night["ramazan"])
                else:
                    _need_block("Özel gece ihtiyacı", "night_ozel", night["ozel"])

                st.markdown("---")
                night["allowed_work_types"] = st.multiselect(
                    "Gece çalışabilecek çalışma tipleri",
                    options=["akademi", "fulltime", "dis_kaynak"],
                    default=night.get("allowed_work_types", ["akademi"]),
                    key="rule_night_allowed_worktypes",
                )

        # ------------------------------------------------------
        # 4) Çalışma tipi kuralları
        # ------------------------------------------------------
        with st.container(border=True):
            st.markdown("#### Çalışma tipi kuralları")

            # Full Time
            ft = rules["work_type"]["fulltime"]
            st.markdown("**Full Time**")

            ft = rules["work_type"]["fulltime"]

            # 1) Toggle en üstte -> state önce güncellensin
            ft["allow_6th_day"] = st.toggle(
                "6. gün esnetme",
                value=bool(ft.get("allow_6th_day", True)),
                key="rule_ft_allow_6th_day",
            )

            c1, c2 = st.columns([1.2, 1.2])

            with c1:
                st.number_input(
                    "Toplam vardiya süresi (saat)",
                    value=int(ft["shift_total_hours"]),
                    disabled=True,
                    key="rule_ft_shift_hours_fixed",
                )

            with c2:
                if not ft["allow_6th_day"]:
                    # 🔒 Esnetme kapalı → sabit 5 gün
                    ft["max_days_per_week_default"] = 5
                    st.number_input(
                        "Haftalık gün",
                        value=5,
                        disabled=True,
                        key="rule_ft_max_days_default_locked",
                    )
                else:
                    # ✅ Esnetme açık → 5 veya 6
                    ft["max_days_per_week_default"] = st.number_input(
                        "Haftalık gün",
                        min_value=5,
                        max_value=6,
                        value=int(min(max(ft.get("max_days_per_week_default", 5), 5), 6)),
                        step=1,
                        key="rule_ft_max_days_default",
                    )
            st.markdown("---")

            # Akademi
            st.markdown("**Akademi**")
            ak = rules["work_type"]["akademi"]
            c1, c2, c3 = st.columns(3)
            with c1:
                ak["shift_total_hours_max"] = st.number_input(
                    "Günlük max saat",
                    min_value=1,
                    max_value=12,
                    value=int(ak["shift_total_hours_max"]),
                    key="rule_ak_max_daily_hours",
                )
            with c2:
                ak["max_days_per_week"] = st.number_input(
                    "Haftalık max gün",
                    min_value=1,
                    max_value=6,  # ✅ 6
                    value=int(min(ak["max_days_per_week"], 6)),
                    key="rule_ak_max_days_week",
                )
            with c3:
                ak["min_rest_hours"] = st.number_input(
                    "Min dinlenme (saat)",
                    min_value=11,
                    max_value=24,
                    value=max(11,int(ak["min_rest_hours"])),
                    key="rule_ak_min_rest_hours",
                )

            st.markdown("---")

            # Dış Kaynak
            st.markdown("**Dış kaynak**")
            dk = rules["work_type"]["dis_kaynak"]
            c1, c2 = st.columns(2)
            with c1:
                st.number_input(
                    "Toplam vardiya süresi (saat)",
                    value=int(dk["shift_total_hours"]),
                    disabled=True,
                    key="rule_dk_shift_hours_fixed",
                )
            with c2:
                dk["max_days_per_week"] = st.number_input(
                    "Haftalık max gün",
                    min_value=1,
                    max_value=6,  # ✅ 6
                    value=int(min(dk["max_days_per_week"], 6)),
                    key="rule_dk_max_days_week",
                )

        st.info('Tüm personeller için vardiyalar arasında en az 11 saat dinlenme zorunludur. Değişiklikler aşağıdaki düğmeyle uygulanır.')
        st.session_state['shift_rules_draft']=rules
        sync=st.checkbox('Seçili dönemdeki gece kayıtlarını seçtiğim başlangıç/bitiş saatlerine uyarla',value=True,key='rules_sync_nights')
        st.caption('Onaylı taleplerin saatleri talep kaydından değiştirilir. Bu işlem kesin gece kayıtları ve elle girilmiş gece vardiyalarını günceller; yayınlanan geçmişi değiştirmez.')
        if st.button('Kaydet ve Uygula',type='primary',key='rules_apply'):
            from core.rule_service import apply_rules
            changed=apply_rules(st.session_state,rules,sync)
            st.success(f'Mesai kuralları kaydedildi ve uygulandı. {changed} gece kaydının saati güncellendi. Otomatik taslağı yeniden oluşturun.')

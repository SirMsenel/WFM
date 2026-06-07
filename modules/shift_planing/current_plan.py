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

    st.subheader("Mevcut Plan Ayarları")
    st.caption("Personel listesini görüntüle ve mesai yazma kurallarını belirle.")

    tab1, tab2 = st.tabs(["👥 Personel Listesi", "🧩 Mesai Kuralları"])

    # ==========================================================
    # TAB 1: Personel Listesi
    # ==========================================================
    with tab1:
        # ====== ÖZET ======
        try:
            s = _api_get("/employees/summary", token=token)
            total_active = int(s.get("total_active", 0))

            def _to_map(rows):
                d = {}
                for r in rows or []:
                    d[str(r.get("key"))] = int(r.get("count", 0))
                return d

            loc_map = _to_map(s.get("by_location"))
            lang_map = _to_map(s.get("by_language"))
            wt_map = _to_map(s.get("by_work_type"))

            with st.container(border=True):
                st.markdown("### 📌 Aktif Personel Özeti")

                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Toplam Aktif", f"{total_active}")
                k2.metric("En yüksek lokasyon", max(loc_map.values()) if loc_map else 0)
                k3.metric("En yüksek dil", max(lang_map.values()) if lang_map else 0)
                k4.metric("En yüksek çalışma tipi", max(wt_map.values()) if wt_map else 0)

                st.markdown("---")

                c1, c2, c3 = st.columns(3, vertical_alignment="top")

                with c1:
                    st.markdown("**📍 Lokasyon**")
                    st.dataframe(
                        [{"Lokasyon": k, "Aktif": v} for k, v in sorted(loc_map.items(), key=lambda x: x[1], reverse=True)],
                        use_container_width=True,
                        hide_index=True,
                        height=220,
                    )

                with c2:
                    st.markdown("**🗣️ Dil**")
                    st.dataframe(
                        [{"Dil": k, "Aktif": v} for k, v in sorted(lang_map.items(), key=lambda x: x[1], reverse=True)],
                        use_container_width=True,
                        hide_index=True,
                        height=220,
                    )

                with c3:
                    st.markdown("**🧩 Çalışma Biçimi**")
                    st.dataframe(
                        [{"Çalışma": k, "Aktif": v} for k, v in sorted(wt_map.items(), key=lambda x: x[1], reverse=True)],
                        use_container_width=True,
                        hide_index=True,
                        height=220,
                    )

        except Exception as e:
            st.warning(f"Özet alınamadı: {e}")

        st.markdown("---")

        # ====== FİLTRELER ======
        with st.container(border=True):
            st.markdown("### 🔎 Filtreler")

            f1, f2, f3, f4 = st.columns([2.2, 1.2, 1.2, 1.2], vertical_alignment="bottom")

            with f1:
                search = st.text_input("Ara (ad, TL, yönetici)", value="", key="emp_search")

            with f2:
                position = st.selectbox(
                    "Pozisyon",
                    options=["(Hepsi)", "agent", "tl", "wfm", "manager"],
                    index=0,
                    key="emp_position",
                )

            with f3:
                location = st.selectbox(
                    "Lokasyon",
                    options=["(Hepsi)", "Ankara", "Istanbul", "Izmir", "Konya", "Diyarbakir", "Adana"],
                    index=0,
                    key="emp_location",
                )

            with f4:
                work_type = st.selectbox(
                    "Çalışma Biçimi",
                    options=["(Hepsi)", "fulltime", "akademi", "dis_kaynak"],
                    index=0,
                    key="emp_worktype",
                )

        # ====== 15'ER YÜKLEME ======
        st.session_state.setdefault("emp_limit", 15)

        b1, b2 = st.columns([1, 5], vertical_alignment="center")
        with b1:
            if st.button("🔄 Sıfırla", use_container_width=True, key="emp_reset_btn"):
                st.session_state["emp_limit"] = 15
                st.rerun()
        with b2:
            st.caption("İlk 15 kayıt gösterilir. “Daha fazla yükle” ile listeyi büyütebilirsin.")

        params = {"limit": int(st.session_state["emp_limit"]), "offset": 0}
        if search.strip():
            params["search"] = search.strip()
        if position != "(Hepsi)":
            params["position"] = position
        if location != "(Hepsi)":
            params["location"] = location
        if work_type != "(Hepsi)":
            params["work_type"] = work_type

        try:
            res = _api_get("/employees/query", token=token, params=params)
            items = res.get("items", [])
            total = int(res.get("total", 0))

            st.markdown(f"### 👥 Liste ({len(items)} / {total})")
            st.dataframe(items, use_container_width=True, hide_index=True, height=520)

            if len(items) < total:
                if st.button("⬇️ Daha fazla yükle (+15)", use_container_width=True, key="emp_more_btn"):
                    st.session_state["emp_limit"] = int(st.session_state["emp_limit"]) + 15
                    st.rerun()

        except Exception as e:
            st.error(f"Personel listesi alınamadı: {e}")

    # ==========================================================
    # TAB 2: Mesai Kuralları
    # ==========================================================
    with tab2:
        # --- helpers ---
        def _init_rules():
            st.session_state.setdefault(
                "shift_rules",
                {
                    "general": {
                        "weekday_general_start": "08:00",
                        "weekend_general_start": "08:00",
                        "global_latest_end": "03:00",  # hard kabul edeceğiz
                        "night_window_start": "00:00",
                        "night_window_end": "08:00",
                    },
                    "boosts": {
                        "weekday_0700_fulltime_extra_enabled": True,
                        "weekday_0700_fulltime_extra_count": 2,
                    },
                    "night": {
                        "enabled": True,
                        "mode": "normal",  # normal | ramazan | ozel
                        "normal": {"tr": 2, "en": 1, "ar": 1},   # toplam 4
                        "ramazan": {"tr": 3, "en": 0, "ar": 0},  # toplam 3
                        "ozel": {"tr": 2, "en": 1, "ar": 1},     # kullanıcı doldurur
                        "allowed_work_types": ["akademi"],
                    },
                    "work_type": {
                        "fulltime": {
                            "shift_total_hours": 9,
                            "prefer_daytime": True,
                            "daytime_window_start": "07:00",
                            "daytime_window_end": "19:00",
                            "max_days_per_week_default": 5,
                            "allow_6th_day": True,
                            "night_allowed": False,
                        },
                        "akademi": {
                            "shift_total_hours_max": 7,
                            "max_days_per_week": 6,
                            "min_rest_hours": 11,
                            "night_allowed": True,
                            "max_end_time": "03:00",
                            "max_end_is_hard": True,
                            "override_required_if_violate": True,
                        },
                        "dis_kaynak": {
                            "shift_total_hours": 11,
                            "max_days_per_week": 6,
                            "night_allowed": False,
                            "max_end_time": "00:00",
                            "max_end_is_hard": False,
                            "override_required_if_violate": True,
                        },
                    },
                },
            )

        def _t(s: str) -> time:
            hh, mm = s.split(":")
            return time(int(hh), int(mm))

        def _tstr(t0: time) -> str:
            return f"{t0.hour:02d}:{t0.minute:02d}"

        _init_rules()
        rules = st.session_state["shift_rules"]

        st.markdown("### 🧩 Mesai Kuralları")
        st.info("Bu ekrandaki değişiklikler otomatik olarak session_state’e kaydedilir (uygulama kapanınca sıfırlanır).")

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
                    min_value=0,
                    max_value=24,
                    value=int(ak["min_rest_hours"]),
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

        # session’a kaydet
        st.session_state["shift_rules"] = rules
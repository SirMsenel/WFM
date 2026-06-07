import pandas as pd
import streamlit as st


def require_login(_api_get, _api_post):
    st.session_state.setdefault("auth_token", None)
    st.session_state.setdefault("profile", None)
    st.session_state.setdefault("demo_users_all", None)
    st.session_state.setdefault("show_demo_users", False)

    if st.session_state["auth_token"] and st.session_state["profile"]:
        return

    st.markdown(
        """
        <style>
        /* ---------- Animations ---------- */
        @keyframes floatLogo {
            0% { transform: translateY(0px) scale(1); }
            50% { transform: translateY(-7px) scale(1.02); }
            100% { transform: translateY(0px) scale(1); }
        }

        @keyframes pulseGlow {
            0% { box-shadow: 0 0 0 rgba(99,102,241,0.00), 0 0 0 rgba(59,130,246,0.00); }
            50% { box-shadow: 0 0 28px rgba(99,102,241,0.18), 0 0 64px rgba(59,130,246,0.12); }
            100% { box-shadow: 0 0 0 rgba(99,102,241,0.00), 0 0 0 rgba(59,130,246,0.00); }
        }

        @keyframes softAppear {
            from {
                opacity: 0;
                transform: translateY(18px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes gradientShift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        /* ---------- Main Layout ---------- */
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(99,102,241,0.10), transparent 24%),
                radial-gradient(circle at top right, rgba(56,189,248,0.10), transparent 20%),
                radial-gradient(circle at bottom center, rgba(168,85,247,0.08), transparent 24%);
        }

        .block-container {
            max-width: 1200px !important;
            padding-top: 3.2rem !important;
            padding-bottom: 2rem !important;
        }

        /* ---------- Card Wrapper ---------- */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 32px !important;
            border: 1px solid rgba(255,255,255,0.10) !important;
            background:
                radial-gradient(circle at 50% -10%, rgba(255,255,255,0.28), transparent 26%),
                radial-gradient(circle at 50% 12%, rgba(165,180,252,0.24), transparent 18%),
                radial-gradient(circle at 70% 0%, rgba(125,211,252,0.12), transparent 18%),
                linear-gradient(135deg, rgba(255,255,255,0.08), rgba(255,255,255,0.03)) !important;
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            box-shadow:
                0 24px 60px rgba(0,0,0,0.16),
                inset 0 1px 0 rgba(255,255,255,0.08) !important;
            padding: 1.6rem 1.45rem 1.2rem 1.45rem !important;
            animation: softAppear 0.5s ease;
            overflow: hidden !important;
            position: relative;
        }

        div[data-testid="stVerticalBlockBorderWrapper"]::before {
            content: "";
            position: absolute;
            inset: 0;
            border-radius: 32px;
            padding: 1px;
            background: linear-gradient(
                135deg,
                rgba(255,255,255,0.16),
                rgba(255,255,255,0.04),
                rgba(99,102,241,0.10),
                rgba(56,189,248,0.08)
            );
            -webkit-mask:
                linear-gradient(#fff 0 0) content-box,
                linear-gradient(#fff 0 0);
            -webkit-mask-composite: xor;
            mask-composite: exclude;
            pointer-events: none;
        }

        /* ---------- Labels ---------- */
        div[data-testid="stTextInput"] label {
            font-weight: 700 !important;
            font-size: 0.95rem !important;
            margin-bottom: 0.3rem !important;
        }

        /* ---------- Inputs ---------- */
        div[data-testid="stTextInput"] input {
            min-height: 56px !important;
            border-radius: 18px !important;
            padding-left: 16px !important;
            background: rgba(240,242,246,0.92) !important;
            border: 1px solid rgba(255,255,255,0.10) !important;
            box-shadow: inset 0 1px 2px rgba(0,0,0,0.04) !important;
            transition: all 0.2s ease !important;
        }

        div[data-testid="stTextInput"] input:focus {
            border: 1px solid rgba(99,102,241,0.35) !important;
            box-shadow:
                0 0 0 4px rgba(99,102,241,0.10),
                inset 0 1px 2px rgba(0,0,0,0.02) !important;
            background: rgba(248,250,252,0.98) !important;
        }

        /* ---------- Buttons ---------- */
        button[kind="primary"] {
            min-height: 56px !important;
            border-radius: 18px !important;
            font-size: 1rem !important;
            font-weight: 800 !important;
            border: 0 !important;
            background: linear-gradient(
                135deg,
                rgba(79,70,229,1) 0%,
                rgba(99,102,241,1) 35%,
                rgba(59,130,246,1) 100%
            ) !important;
            background-size: 200% 200% !important;
            animation: gradientShift 7s ease infinite;
            box-shadow: 0 12px 28px rgba(79,70,229,0.24) !important;
            transition: all 0.2s ease !important;
        }

        button[kind="primary"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 16px 32px rgba(79,70,229,0.28) !important;
        }

        div[data-testid="stButton"] button {
            min-height: 52px !important;
            border-radius: 18px !important;
            font-size: 0.98rem !important;
            font-weight: 700 !important;
            border: 1px solid rgba(255,255,255,0.10) !important;
            background: linear-gradient(
                135deg,
                rgba(255,255,255,0.10),
                rgba(255,255,255,0.05)
            ) !important;
            backdrop-filter: blur(8px);
            color: inherit !important;
            transition: all 0.2s ease !important;
        }

        div[data-testid="stButton"] button:hover {
            transform: translateY(-1px);
            border-color: rgba(99,102,241,0.18) !important;
            box-shadow: 0 10px 24px rgba(0,0,0,0.10) !important;
        }

        /* ---------- Header Area ---------- */
        .login-top {
            text-align: center;
            padding-top: 0.9rem;
            padding-bottom: 1.05rem;
        }

        .login-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 0.45rem 0.85rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
            color: #c7d2fe;
            background: rgba(99,102,241,0.10);
            border: 1px solid rgba(255,255,255,0.10);
            margin-bottom: 1rem;
        }

        .login-logo {
            width: 92px;
            height: 92px;
            margin: 0 auto 16px auto;
            border-radius: 28px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 40px;
            color: white;
            background:
                radial-gradient(circle at 30% 30%, rgba(255,255,255,0.34), transparent 32%),
                linear-gradient(135deg, rgba(99,102,241,0.92), rgba(59,130,246,0.92), rgba(14,165,233,0.92));
            border: 1px solid rgba(255,255,255,0.16);
            box-shadow:
                0 16px 38px rgba(79,70,229,0.22),
                inset 0 1px 0 rgba(255,255,255,0.22);
            animation:
                floatLogo 3.2s ease-in-out infinite,
                pulseGlow 4.2s ease-in-out infinite;
            position: relative;
        }

        .login-logo::after {
            content: "";
            position: absolute;
            inset: 8px;
            border-radius: 22px;
            border: 1px solid rgba(255,255,255,0.12);
            pointer-events: none;
        }

        .login-title {
            font-size: 2.2rem;
            font-weight: 800;
            line-height: 1.08;
            margin-bottom: 0.45rem;
            letter-spacing: -0.02em;
            color: inherit;
        }

        .login-subtitle {
            font-size: 0.99rem;
            color: #9aa0a6;
            max-width: 440px;
            margin: 0 auto 0.1rem auto;
            line-height: 1.5;
        }

        .login-note {
            text-align: center;
            font-size: 0.88rem;
            color: #9aa0a6;
            margin-top: 0.95rem;
        }

        .login-note strong {
            color: #c7d2fe;
            font-weight: 700;
        }

        /* ---------- Dataframe Area ---------- */
        div[data-testid="stExpander"] details {
            border-radius: 22px !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
            background: linear-gradient(
                135deg,
                rgba(255,255,255,0.05),
                rgba(255,255,255,0.02)
            ) !important;
            overflow: hidden !important;
        }

        div[data-testid="stExpander"] summary {
            font-weight: 700 !important;
        }

        /* ---------- Small spacing ---------- */
        .login-separator {
            height: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    left, center, right = st.columns([1, 1.2, 1])

    with center:
        with st.container(border=True):
            st.markdown(
                """
                <div class="login-top">
                    <div class="login-badge">✨ Modern WFM Experience</div>
                    <div class="login-logo">🔐</div>
                    <div class="login-title">WFM Giriş</div>
                    <div class="login-subtitle">
                        Hesabınızla giriş yaparak platforma güvenli şekilde erişin
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("Kullanıcı adı", placeholder="ahmet.yilmaz01")
                password = st.text_input("Şifre", type="password", placeholder="1234")
                submitted = st.form_submit_button("Giriş Yap", use_container_width=True)

            if submitted:
                try:
                    res = _api_post("/auth/login", {"username": username, "password": password})
                    st.session_state["auth_token"] = res["access_token"]
                    st.session_state["profile"] = res["profile"]
                    st.rerun()
                except Exception as e:
                    st.error(f"Giriş başarısız: {e}")

            if st.button("Örnek kullanıcılar", use_container_width=True):
                try:
                    demo = _api_get("/auth/demo_users", params={"limit": 500})
                    st.session_state["demo_users_all"] = demo
                    st.session_state["show_demo_users"] = not st.session_state["show_demo_users"]
                except Exception as e:
                    st.error(f"Demo listesi alınamadı: {e}")

            st.markdown(
                '<div class="login-note">Demo ortamı aktif • Varsayılan şifre: <strong>1234</strong></div>',
                unsafe_allow_html=True,
            )

    if st.session_state.get("show_demo_users"):
        demo = st.session_state.get("demo_users_all")
        if demo and "items" in demo:
            df_demo = pd.DataFrame(demo["items"])

            if not df_demo.empty:
                search_cols = [
                    c for c in df_demo.columns
                    if c.lower() in [
                        "role", "position", "department", "team",
                        "title", "user_type", "skill", "language"
                    ]
                ]
                if not search_cols:
                    search_cols = list(df_demo.columns)

                def row_text(row) -> str:
                    return " ".join(
                        str(row[col]).lower()
                        for col in search_cols
                        if col in df_demo.columns
                    )

                selected = []
                used_idx = set()

                targets = [
                    ("Agent 1", ["agent"]),
                    ("Agent 2", ["agent"]),
                    ("Agent 3", ["agent"]),
                    ("Agent 4", ["agent"]),
                    ("Agent 5", ["agent"]),
                    ("Agent 6", ["agent"]),
                    ("Agent 7", ["agent"]),
                    ("Agent 8", ["agent"]),
                    ("Agent 9", ["agent"]),
                    ("Agent 10", ["agent"]),
                    ("Takım Lideri 1", ["team leader", "takım lideri", "tl"]),
                    ("Takım Lideri 2", ["team leader", "takım lideri", "tl"]),
                    ("Yönetici", ["manager", "yönetici", "admin"]),
                    ("WFM", ["wfm", "workforce"]),
                    ("Moderator", ["moderator"]),
                    ("Full Time", ["full time", "fulltime"]),
                    ("Akademi 1", ["akademi", "academy"]),
                    ("Akademi 2", ["akademi", "academy"]),
                    ("Dış Kaynak 1", ["outsource", "dış kaynak", "diskaynak"]),
                    ("Dış Kaynak 2", ["outsource", "dış kaynak", "diskaynak"]),
                    ("İngilizce", ["english", "ingilizce"]),
                    ("Arapça", ["arabic", "arapça"]),
                ]

                for label, keywords in targets:
                    found = None
                    for idx, row in df_demo.iterrows():
                        if idx in used_idx:
                            continue
                        txt = row_text(row)
                        if any(k in txt for k in keywords):
                            found = idx
                            break
                    if found is not None:
                        used_idx.add(found)
                        item = df_demo.loc[found].to_dict()
                        item["Demo_Tipi"] = label
                        selected.append(item)

                if len(selected) < 32:
                    for idx, row in df_demo.iterrows():
                        if idx in used_idx:
                            continue
                        item = row.to_dict()
                        item["Demo_Tipi"] = (
                            item.get("role")
                            or item.get("position")
                            or item.get("department")
                            or f"Örnek {len(selected)+1}"
                        )
                        selected.append(item)
                        used_idx.add(idx)
                        if len(selected) >= 32:
                            break

                sample_df = pd.DataFrame(selected)

                preferred_cols = ["Demo_Tipi", "username", "full_name", "position", "role"]
                show_cols = [c for c in preferred_cols if c in sample_df.columns]
                if not show_cols:
                    show_cols = sample_df.columns.tolist()

                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander("Örnek kullanıcı listesi", expanded=True):
                    st.caption("Varsayılan şifre: 1234")
                    st.dataframe(sample_df[show_cols], use_container_width=True, hide_index=True)

    st.stop()

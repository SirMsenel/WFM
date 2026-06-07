import streamlit as st
from core.api_client import api_get, api_post


def require_login():
    st.session_state.setdefault("auth_token", None)
    st.session_state.setdefault("profile", None)
    st.session_state.setdefault("demo_users", None)

    if st.session_state["auth_token"] and st.session_state["profile"]:
        return

    st.markdown("## 🔐 WFM Giriş")
    st.caption("Demo şifre: **1234**")

    left, right = st.columns([1.05, 1.4], vertical_alignment="top")

    with left:
        with st.container(border=True):
            st.markdown("### Giriş Yap")

            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("Kullanıcı adı")
                password = st.text_input("Şifre", type="password")
                submitted = st.form_submit_button("Giriş", use_container_width=True)

            st.divider()

            if st.button("Demo kullanıcıları göster", use_container_width=True):
                try:
                    demo = api_get("/auth/demo_users", params={"limit": 20})
                    st.session_state["demo_users"] = demo
                except Exception as e:
                    st.error(f"Demo listesi alınamadı: {e}")

            if submitted:
                try:
                    res = api_post("/auth/login", {"username": username, "password": password})
                    st.session_state["auth_token"] = res["access_token"]
                    st.session_state["profile"] = res["profile"]
                    st.success(f"Hoş geldin, {res['profile']['full_name']}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Giriş başarısız: {e}")

    with right:
        demo = st.session_state.get("demo_users")
        if demo:
            with st.expander("Demo kullanıcılar"):
                st.dataframe(demo["items"], use_container_width=True, hide_index=True)

    st.stop()
"""
로그인 (streamlit-oauth 컴포넌트, Google OAuth).

* Streamlit Community Cloud에서 st.login(네이티브)이 콜백 쿠키 문제로
  "Missing provider for OAuth callback" 에러가 나서 컴포넌트 방식으로 전환.
* redirect_uri는 기존 [auth].redirect_uri 재사용(구글에 이미 등록됨) → 구글 설정 변경 불필요.
* 로그인 정보는 st.session_state['user_info']에 저장(세션 단위).
"""
import base64
import json

import streamlit as st

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"


def auth_configured() -> bool:
    try:
        a = st.secrets.get("auth")
        return bool(a and a.get("client_id") and a.get("client_secret") and a.get("redirect_uri"))
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def _oauth():
    from streamlit_oauth import OAuth2Component
    a = st.secrets["auth"]
    return OAuth2Component(
        a["client_id"], a["client_secret"],
        AUTHORIZE_URL, TOKEN_URL, TOKEN_URL, REVOKE_URL,
    )


def _decode_id_token(token: dict) -> dict:
    """id_token(JWT) payload를 디코딩해 사용자 정보(email·name·picture·sub)를 얻는다."""
    idt = token.get("id_token", "")
    parts = idt.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def login_button(label="Google로 로그인", key="login"):
    """Google 로그인 버튼(컴포넌트). 성공 시 session_state에 사용자 정보 저장."""
    if not auth_configured():
        st.caption("로그인 기능 준비중 (관리자 키 설정 필요)")
        return
    a = st.secrets["auth"]
    result = _oauth().authorize_button(
        name=label,
        redirect_uri=a["redirect_uri"],
        scope="openid email profile",
        key=key,
        use_container_width=True,
        pkce="S256",
        extras_params={"prompt": "select_account"},
    )
    if result and "token" in result:
        st.session_state["user_info"] = _decode_id_token(result["token"])
        st.rerun()


def is_logged_in() -> bool:
    return bool(st.session_state.get("user_info"))


def logout():
    st.session_state.pop("user_info", None)


def user_name() -> str:
    u = st.session_state.get("user_info") or {}
    return u.get("name") or u.get("email") or "사용자"


def user_picture() -> str:
    u = st.session_state.get("user_info") or {}
    return u.get("picture", "")


def user_id() -> str:
    u = st.session_state.get("user_info") or {}
    return u.get("sub") or u.get("email") or ""

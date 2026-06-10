"""
로그인 (Google OAuth — 같은 탭 리다이렉트 방식).

* 팝업 방식(streamlit-oauth)·네이티브(st.login) 모두 Streamlit Cloud에서 콜백 처리가 깨져서,
  가장 확실한 "같은 탭 리다이렉트 + 서버측 토큰 교환" 방식으로 구현.
* 흐름: 버튼(앵커) 클릭 → 구글 동의 화면으로 전체 이동 → 앱 URL로 ?code 와 함께 복귀
  → handle_callback()이 code를 토큰으로 교환 → id_token에서 사용자 정보 → session_state 저장.
* redirect_uri는 [auth].redirect_uri (앱 루트 URL) 사용.
"""
import base64
import json
import urllib.parse

import requests
import streamlit as st

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def auth_configured() -> bool:
    try:
        a = st.secrets.get("auth")
        return bool(a and a.get("client_id") and a.get("client_secret") and a.get("redirect_uri"))
    except Exception:
        return False


def _decode_id_token(token: dict) -> dict:
    idt = token.get("id_token", "")
    parts = idt.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def _authorize_url() -> str:
    a = st.secrets["auth"]
    params = {
        "client_id": a["client_id"],
        "redirect_uri": a["redirect_uri"],
        "response_type": "code",
        "scope": "openid email profile",
        "prompt": "select_account",
    }
    return AUTHORIZE_URL + "?" + urllib.parse.urlencode(params)


def handle_callback():
    """앱 시작 시 호출: URL에 ?code 가 있으면 토큰 교환 후 로그인 처리."""
    if st.session_state.get("user_info"):
        return
    code = st.query_params.get("code")
    if not code or not auth_configured():
        return
    a = st.secrets["auth"]
    try:
        resp = requests.post(TOKEN_URL, data={
            "code": code,
            "client_id": a["client_id"],
            "client_secret": a["client_secret"],
            "redirect_uri": a["redirect_uri"],
            "grant_type": "authorization_code",
        }, timeout=10)
        info = _decode_id_token(resp.json())
        if info:
            st.session_state["user_info"] = info
    except Exception as e:
        st.error(f"로그인 처리 실패: {e}")
    st.query_params.clear()  # URL에서 ?code 제거


def login_button(label="Google로 로그인", key="login"):
    """Google 로그인 버튼.

    target="_top" 앵커로 렌더 → 클릭 시 앱이 iframe에 감싸여 있든 아니든 항상
    '진짜 최상위 창'이 구글로 이동(같은 탭). 기존 target="_self"는 Cloud가 앱을
    iframe으로 감쌀 때 iframe 안만 이동해 구글이 403을 주던 문제가 있었음.
    """
    if not auth_configured():
        st.caption("로그인 기능 준비중 (관리자 키 설정 필요)")
        return
    st.markdown(
        f'<a href="{_authorize_url()}" target="_top" '
        f'style="display:flex;align-items:center;justify-content:center;height:40px;'
        f'background:#ffffff;color:#1f2937;border-radius:8px;font-weight:600;'
        f'text-decoration:none;border:1px solid #d1d5db;font-size:14px;">{label}</a>',
        unsafe_allow_html=True,
    )


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

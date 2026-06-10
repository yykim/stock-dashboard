"""
로그인 (Streamlit 내장 st.login, Google OIDC).
- secrets에 [auth]가 설정되지 않아도 앱이 죽지 않도록 방어 처리
  (키 발급 전에도 공개 대시보드는 그대로 동작).
"""
import streamlit as st


def auth_configured() -> bool:
    """secrets.toml에 [auth] 섹션이 설정돼 있는지."""
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def is_logged_in() -> bool:
    if not auth_configured():
        return False
    return bool(getattr(st.user, "is_logged_in", False))


def user_name() -> str:
    """로그인 사용자 표시 이름 (없으면 이메일)."""
    try:
        return st.user.get("name") or st.user.get("email") or "사용자"
    except Exception:
        return "사용자"


def user_picture() -> str:
    """구글 프로필 이미지 URL (없으면 빈 문자열)."""
    try:
        return st.user.get("picture") or ""
    except Exception:
        return ""


def user_id() -> str:
    """사용자 고유 식별자 (DB 키로 사용 예정 — Phase 3)."""
    try:
        return st.user.get("sub") or st.user.get("email") or ""
    except Exception:
        return ""

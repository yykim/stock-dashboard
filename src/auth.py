"""
구글 로그인 — Streamlit 공식 네이티브 인증(st.login / st.user / st.logout).

[왜 Render인가 — 실측 결론]
Streamlit Community Cloud는 앱을 `/~/+/` 래퍼 iframe으로 띄우는데, 이게 st.login의 인증
엔드포인트(`/~/+/auth/login`)를 500으로 깨뜨린다(공식 데모도 동일 — 직접 확인). 그래서
이 앱은 래퍼·샌드박스가 없는 호스트(Render)에 배포한다 → 앱이 최상위로 직접 서빙되어
st.login이 '같은 탭'에서 정상 동작(네이티브 30일 쿠키, cross-tab, 팝업 없음).

[secrets 형식 — 단일 provider(google)]
  [auth]
  redirect_uri = "https://<배포주소>/oauth2callback"   # 로컬: http://localhost:8501/oauth2callback
  cookie_secret = "<랜덤 문자열>"
  client_id = "...apps.googleusercontent.com"
  client_secret = "..."
  server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

st.login()이 구글 동의 화면으로 리다이렉트하고, 콜백·쿠키·세션을 모두 알아서 처리한다.
(별도 토큰 교환·쿠키 코드 불필요)
"""
import streamlit as st


def auth_configured() -> bool:
    """st.login에 필요한 [auth] secrets가 모두 있는지."""
    try:
        a = st.secrets.get("auth")
        return bool(a and a.get("client_id") and a.get("client_secret")
                    and a.get("redirect_uri") and a.get("cookie_secret"))
    except Exception:
        return False


def is_logged_in() -> bool:
    try:
        return bool(st.user.is_logged_in)
    except Exception:
        return False


def login_button(label="Google로 로그인", key="login"):
    """클릭 시 st.login()으로 구글 로그인(같은 탭 리다이렉트)."""
    if not auth_configured():
        st.caption("로그인 기능 준비중 (관리자 키 설정 필요)")
        return
    if st.button(label, key=key, width="stretch"):
        st.login()   # 단일 provider → 구글 동의 화면


def logout():
    """로그아웃: 네이티브 세션·쿠키 제거(st.logout이 리다이렉트까지 처리)."""
    st.logout()


def user_name() -> str:
    try:
        return st.user.name or st.user.email or "사용자"
    except Exception:
        return "사용자"


def user_picture() -> str:
    try:
        return st.user.picture or ""
    except Exception:
        return ""


def user_id() -> str:
    """관심종목 저장 키로 쓸 안정적 식별자(구글 sub)."""
    try:
        return st.user.sub or st.user.email or ""
    except Exception:
        return ""

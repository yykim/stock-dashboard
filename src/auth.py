"""
구글 로그인 (수동 OAuth + 서명 쿠키).

[왜 이렇게 구현했나 — 조사 결론]
Streamlit Community Cloud는 앱을 `allow-top-navigation`이 없는 sandbox iframe 안에서 띄운다.
그래서 iframe 안에서는 "이 탭을 구글로 이동"이 브라우저 차원에서 막힌다(직접 확인함).
  - target="_self": iframe 안에서 구글이 열리는데 구글이 framed 페이지를 거부 → 403
  - target="_top" : 최상위 창 이동을 sandbox가 차단 → 클릭해도 무반응
st.login(공식)·streamlit-oauth(팝업+창 폴링)도 같은 iframe 한계로 깨졌다.

[해법] sandbox가 `allow-popups`는 허용한다 → '새 탭(팝업)'에서 로그인하고,
결과를 '서명 쿠키'에 저장해 모든 탭/새로고침에 로그인을 공유한다.
탭끼리 창(window) 참조로 통신하면 Cloud 중첩 iframe에서 깨지므로, 브라우저 레벨인
'쿠키'를 탭 간 신호로 쓴다(이게 streamlit-oauth가 실패한 지점을 우회하는 핵심).

[흐름]
  1) 로그인 버튼 클릭 → window.open 으로 새 탭에서 구글 동의 화면
  2) 동의 후 새 탭이 앱 루트(?code)로 복귀 → handle_callback 이 code를 토큰으로 교환
  3) 사용자 정보를 cookie_secret 으로 HMAC 서명해 쿠키(sr_auth)에 저장 + 새 탭 자동 닫힘
  4) 원래 탭: 쿠키 등장 감지 → 자동 새로고침(best-effort). 새로고침/조작 시엔 항상 복원.
"""
import base64
import hashlib
import hmac
import json
import urllib.parse
from datetime import datetime, timedelta, timezone

import requests
import streamlit as st
import streamlit.components.v1 as components
import extra_streamlit_components as stx

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
COOKIE_NAME = "sr_auth"   # 로그인 상태 쿠키
COOKIE_DAYS = 7           # 로그인 유지 기간


# ---------------------------------------------------------------- 설정
def auth_configured() -> bool:
    """로그인에 필요한 secrets([auth])가 모두 있는지."""
    try:
        a = st.secrets.get("auth")
        return bool(a and a.get("client_id") and a.get("client_secret")
                    and a.get("redirect_uri") and a.get("cookie_secret"))
    except Exception:
        return False


# ---------------------------------------------------------------- 쿠키 매니저
def _cookie_manager():
    # CookieManager는 위젯이라 @st.cache_*에 넣을 수 없고, 한 run에 1번만 생성해야 함.
    # → 세션당 1개 인스턴스를 session_state에 보관해 재사용(중복 key 에러 방지).
    if "_cookie_mgr" not in st.session_state:
        st.session_state["_cookie_mgr"] = stx.CookieManager(key="sr_cookie_manager")
    return st.session_state["_cookie_mgr"]


# ---------------------------------------------------------------- 쿠키 서명/검증
def _sign(payload_b64: str) -> str:
    secret = st.secrets["auth"]["cookie_secret"].encode()
    return hmac.new(secret, payload_b64.encode(), hashlib.sha256).hexdigest()


def _encode_cookie(user: dict) -> str:
    """사용자 정보 → 'base64(payload).hmac서명' 토큰 (위조 방지)."""
    data = {
        "sub": user.get("sub"), "email": user.get("email"),
        "name": user.get("name"), "picture": user.get("picture"),
        "exp": int((datetime.now(timezone.utc) + timedelta(days=COOKIE_DAYS)).timestamp()),
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
    return f"{payload_b64}.{_sign(payload_b64)}"


def _decode_cookie(token: str):
    """토큰 검증(서명·만료) 후 사용자 dict 반환. 위조/만료면 None."""
    try:
        payload_b64, sig = token.split(".", 1)
        if not hmac.compare_digest(sig, _sign(payload_b64)):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload_b64))
        if data.get("exp", 0) < datetime.now(timezone.utc).timestamp():
            return None
        return data
    except Exception:
        return None


# ---------------------------------------------------------------- id_token 파싱
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


# ---------------------------------------------------------------- OAuth URL
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


# ---------------------------------------------------------------- 세션 복원/콜백
def restore_session():
    """앱 시작 시: 쿠키에 유효한 로그인이 있으면 session_state 복원(모든 탭·새로고침 공통)."""
    if st.session_state.get("user_info") or not auth_configured():
        return
    cookies = _cookie_manager().get_all(key="sr_get_all")
    token = cookies.get(COOKIE_NAME) if cookies else None
    data = _decode_cookie(token) if token else None
    if data:
        st.session_state["user_info"] = data


def handle_callback():
    """(새 탭에서 실행) URL에 ?code가 있으면 토큰 교환 → 쿠키 저장 → 새 탭 자동 닫기."""
    code = st.query_params.get("code")
    if not code or not auth_configured() or st.session_state.get("user_info"):
        return
    a = st.secrets["auth"]
    try:
        resp = requests.post(TOKEN_URL, data={
            "code": code, "client_id": a["client_id"], "client_secret": a["client_secret"],
            "redirect_uri": a["redirect_uri"], "grant_type": "authorization_code",
        }, timeout=10)
        info = _decode_id_token(resp.json())
    except Exception as e:
        st.error(f"로그인 처리 실패: {e}")
        return
    if not info:
        st.error("로그인 토큰을 확인하지 못했어요. 다시 시도해 주세요.")
        return

    user = {k: info.get(k) for k in ("sub", "email", "name", "picture")}
    st.session_state["user_info"] = user
    # 쿠키 저장 → 원래 탭/다른 탭/새로고침에 로그인 전파·유지
    _cookie_manager().set(
        COOKIE_NAME, _encode_cookie(user),
        expires_at=datetime.now(timezone.utc) + timedelta(days=COOKIE_DAYS),
        key="sr_set",
    )
    st.query_params.clear()  # URL에서 ?code 제거

    # 이 새 탭은 역할이 끝났으니, 쿠키 기록 시간을 잠깐 준 뒤 스스로 닫는다(best-effort).
    st.markdown("### ✅ 로그인 완료")
    st.caption("이 창은 곧 닫히고, 원래 탭에서 로그인됩니다. 자동으로 닫히지 않으면 닫아주세요.")
    components.html(
        "<script>setTimeout(function(){"
        "try{window.top.close();}catch(e){}try{window.close();}catch(e){}"
        "}, 1500);</script>",
        height=0,
    )
    st.stop()  # 새 탭에서는 대시보드 본문을 그리지 않음


# ---------------------------------------------------------------- 로그인 버튼
def login_button(label="Google로 로그인", key="login"):
    """구글 로그인 버튼.

    - 클릭(사용자 제스처) 시 window.open 으로 새 탭에서 구글 로그인(팝업차단 회피).
    - 동시에 'sr_auth 쿠키가 생기면(=다른 탭에서 로그인 완료) 이 탭을 자동 새로고침' 감시.
      (best-effort: sandbox가 부모 프레임 reload를 막으면 사용자가 새로고침하면 됨)
    """
    if not auth_configured():
        st.caption("로그인 기능 준비중 (관리자 키 설정 필요)")
        return
    url_js = json.dumps(_authorize_url())  # JS 문자열로 안전 인코딩(& 등 escape 불필요)
    components.html(
        f"""
        <script>var SR_URL={url_js};</script>
        <button onclick="window.open(SR_URL,'srlogin','popup=yes,width=500,height=660')"
            style="width:100%;height:40px;background:#ffffff;color:#1f2937;
            border:1px solid #d1d5db;border-radius:8px;font-weight:600;
            font-size:14px;cursor:pointer;font-family:sans-serif;">{label}</button>
        <script>
        setInterval(function(){{
            if (document.cookie.indexOf('{COOKIE_NAME}=') !== -1) {{
                try {{ window.parent.location.reload(); }}
                catch(e) {{ try {{ window.top.location.reload(); }} catch(e2) {{}} }}
            }}
        }}, 1500);
        </script>
        """,
        height=54,
    )


# ---------------------------------------------------------------- 상태/로그아웃
def is_logged_in() -> bool:
    return bool(st.session_state.get("user_info"))


def logout():
    """로그아웃: 세션·쿠키 모두 제거. (on_click 콜백이 아니라 본문에서 호출해야 함)"""
    st.session_state.pop("user_info", None)
    if auth_configured():
        try:
            _cookie_manager().delete(COOKIE_NAME, key="sr_del")
        except Exception:
            pass


def user_name() -> str:
    u = st.session_state.get("user_info") or {}
    return u.get("name") or u.get("email") or "사용자"


def user_picture() -> str:
    u = st.session_state.get("user_info") or {}
    return u.get("picture", "")


def user_id() -> str:
    u = st.session_state.get("user_info") or {}
    return u.get("sub") or u.get("email") or ""

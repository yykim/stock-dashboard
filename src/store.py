"""
사용자별 관심종목 저장 (Supabase Postgres).
- 로그인 사용자(user_id)별로 관심종목 코드를 저장/조회/삭제.
- secrets에 [supabase]가 없으면 비활성(앱은 계속 동작).
"""
import streamlit as st


def configured() -> bool:
    try:
        s = st.secrets.get("supabase")
        return bool(s and s.get("url") and s.get("key"))
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def _client():
    from supabase import create_client
    s = st.secrets["supabase"]
    # URL에 실수로 /rest/v1 같은 경로가 붙어도 베이스 URL만 사용 (PGRST125 방지)
    url = s["url"].split("/rest/v1")[0].rstrip("/")
    return create_client(url, s["key"])


def get_watchlist(user_id: str) -> list:
    if not configured() or not user_id:
        return []
    try:
        res = (
            _client().table("watchlist").select("code")
            .eq("user_id", user_id).order("created_at").execute()
        )
        return [row["code"] for row in res.data]
    except Exception as e:
        st.warning(f"관심종목 불러오기 실패: {e}")
        return []


def add(user_id: str, code: str):
    if not configured() or not user_id:
        return
    try:
        _client().table("watchlist").upsert(
            {"user_id": user_id, "code": str(code)}, on_conflict="user_id,code"
        ).execute()
    except Exception as e:
        st.warning(f"추가 실패: {e}")


def remove(user_id: str, code: str):
    if not configured() or not user_id:
        return
    try:
        _client().table("watchlist").delete() \
            .eq("user_id", user_id).eq("code", str(code)).execute()
    except Exception as e:
        st.warning(f"삭제 실패: {e}")

"""
지수 대비 강세·약세 종목 대시보드 (v2 — 공개 서비스)
- 데이터: 정적 종목목록(CSV) + yfinance(시세·지수). 로그인=구글 OAuth(서명 쿠키), 개인화=Supabase.
"""
import pandas as pd
import streamlit as st

from src import data_source as ds
from src import analyzer as an
from src import auth
from src import store
from src import quotes
from src.theme import apply_theme
from src.config import TOP_N, CACHE_TTL, DEFAULT_STOPLOSS, DISCLAIMER

st.set_page_config(page_title="Stock Dashboard", page_icon="📈", layout="wide",
                   initial_sidebar_state="expanded")
apply_theme()
auth.restore_session()  # 쿠키에 로그인 정보 있으면 복원 (모든 탭·새로고침 공통)
auth.handle_callback()  # (새 탭) 구글 리다이렉트 복귀(?code) → 쿠키 저장 후 자동 닫힘

# ---------- 사이드바: 계정 ----------
with st.sidebar:
    st.markdown("### 👤 계정")
    if auth.is_logged_in():
        pic = auth.user_picture()
        if pic:
            st.image(pic, width=72)
        st.success(f"{auth.user_name()}님")
        if st.button("로그아웃", width="stretch"):
            auth.logout()
            st.rerun()
    else:
        auth.login_button(label="Google로 로그인", key="sidebar_login")


# ---------- 데이터 (일별 → 30분 캐시) ----------
@st.cache_data(ttl=CACHE_TTL, show_spinner="시세 불러오는 중...")
def get_listing():
    return ds.load_listing()


@st.cache_data(ttl=CACHE_TTL, show_spinner="시세 불러오는 중...")
def load(market: str):
    df = ds.get_market(get_listing(), market, TOP_N)
    idx = ds.get_index(market)
    return an.add_excess_return(df, idx["등락률"]), idx


# 관심종목용 장중 지연시세 (yfinance, 5분 캐시)
@st.cache_data(ttl=300, show_spinner=False)
def intraday_quote(code: str, market: str):
    return quotes.intraday_quote(code, market)


@st.cache_data(ttl=300, show_spinner=False)
def intraday_index(market: str):
    return quotes.intraday_index(market)


_RED, _BLUE = "#F0454B", "#3B82F6"  # 한국식: 상승=빨강 / 하락=파랑


def style_table(df: pd.DataFrame):
    """표 스타일: 등락률·초과등락률을 +/-·%로 포맷하고 상승=빨강·하락=파랑 색."""
    pct = [c for c in ["등락률", "초과등락률"] if c in df.columns]
    num = [c for c in ["현재가"] if c in df.columns]
    fmts = {c: "{:+.2f}%" for c in pct}
    fmts.update({c: "{:,.0f}" for c in num})

    def color(v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return ""
        return f"color:{_RED}" if v > 0 else (f"color:{_BLUE}" if v < 0 else "")

    return df.style.format(fmts).map(color, subset=pct)


def render_watchlist(wdf):
    """관심종목 표를 커스텀 HTML로 렌더링.
    초과등락률 셀에 마우스를 올리면 '종목 % − 지수 % = 초과 %' 계산식 툴팁 표시."""
    def c(v):
        return _RED if v > 0 else (_BLUE if v < 0 else "#94A3B8")

    cols = ["종목명", "시장", "현재가", "등락률", "초과등락률", "기준", "상태"]
    head = "".join(f"<th>{h}</th>" for h in cols)
    rows_html = ""
    for _, r in wdf.iterrows():
        # 숨긴 자식 요소(span.tip)로 계산식 툴팁 — Streamlit이 title 속성을 제거하므로 CSS 방식 사용.
        # 라벨(왼쪽)·숫자(오른쪽 정렬) 구조 + 값별 색상 + 결과(초과등락률) 강조.
        tip = (
            "<span class='tip'>"
            f"<span class='tr'><span class='tl'>종목 등락률</span>"
            f"<span class='tv' style='color:{c(r['등락률'])}'>{r['등락률']:+.2f}%</span></span>"
            f"<span class='tr'><span class='tl'>지수 ({r['시장']})</span>"
            f"<span class='tv' style='color:{c(r['지수등락률'])}'>{r['지수등락률']:+.2f}%</span></span>"
            "<span class='tdiv'></span>"
            f"<span class='tr'><span class='tl'>초과등락률</span>"
            f"<span class='tv big' style='color:{c(r['초과등락률'])}'>{r['초과등락률']:+.2f}%</span></span>"
            "</span>"
        )
        rows_html += (
            "<tr>"
            f"<td>{r['종목명']}</td>"
            f"<td>{r['시장']}</td>"
            f"<td class='num'>{r['현재가']:,.0f}</td>"
            f"<td class='num' style='color:{c(r['등락률'])}'>{r['등락률']:+.2f}%</td>"
            f"<td class='num excess' style='color:{c(r['초과등락률'])}'>"
            f"{r['초과등락률']:+.2f}%{tip}</td>"
            f"<td>{r['기준']}</td>"
            f"<td>{r['상태']}</td>"
            "</tr>"
        )
    st.markdown(
        "<style>"
        ".wltbl{width:100%;border-collapse:collapse;font-size:0.92rem;margin-top:4px;}"
        ".wltbl th,.wltbl td{padding:9px 12px;border-bottom:1px solid #334155;text-align:left;}"
        ".wltbl th{color:#94A3B8;font-weight:600;}"
        ".wltbl td.num{text-align:right;}"
        ".wltbl td.excess{position:relative;cursor:help;text-decoration:underline dotted #64748B;}"
        ".wltbl td.excess .tip{visibility:hidden;opacity:0;position:absolute;z-index:1000;"
        "top:135%;left:50%;transform:translateX(-50%);background:#0B1220;border:1px solid #334155;"
        "border-radius:10px;padding:10px 12px;min-width:200px;text-decoration:none;"
        "box-shadow:0 6px 16px rgba(0,0,0,.5);}"
        ".wltbl td.excess:hover .tip{visibility:visible;opacity:1;}"
        ".wltbl .tip .tr{display:flex;justify-content:space-between;gap:22px;padding:3px 0;font-size:0.82rem;}"
        ".wltbl .tip .tl{color:#94A3B8;font-weight:500;}"
        ".wltbl .tip .tv{font-weight:700;font-variant-numeric:tabular-nums;}"
        ".wltbl .tip .tv.big{font-size:1.05rem;}"
        ".wltbl .tip .tdiv{display:block;border-top:1px solid #334155;margin:6px 0;}"
        "</style>"
        f"<table class='wltbl'><thead><tr>{head}</tr></thead><tbody>{rows_html}</tbody></table>",
        unsafe_allow_html=True,
    )


def index_card(col, label, value, rate):
    """지수 카드 (한국식 색: 상승=빨강 / 하락=파랑)."""
    if rate > 0:
        color, sign = _RED, "▲"
    elif rate < 0:
        color, sign = _BLUE, "▼"
    else:
        color, sign = "#94A3B8", "–"
    col.markdown(
        f'<div style="background:#1E293B;border:1px solid #334155;border-radius:16px;padding:18px 22px;">'
        f'<div style="color:#94A3B8;font-size:0.9rem;margin-bottom:4px;">{label}</div>'
        f'<div style="color:#F1F5F9;font-size:2.1rem;font-weight:700;line-height:1.15;">{value:,.2f}</div>'
        f'<div style="color:{color};font-weight:600;margin-top:6px;">{sign} {abs(rate):.2f}%</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------- 헤더 ----------
st.markdown("## 📈 지수 대비 강세·약세 종목")

kospi_df, kospi_idx = load("KOSPI")
kosdaq_df, kosdaq_idx = load("KOSDAQ")

day = kospi_idx.get("날짜", "")
if day:
    st.caption(f"데이터 기준일 {day[:4]}-{day[4:6]}-{day[6:]} · Yahoo Finance 일별 종가 기준")

c1, c2 = st.columns(2)
index_card(c1, "코스피 지수", kospi_idx["지수"], kospi_idx["등락률"])
index_card(c2, "코스닥 지수", kosdaq_idx["지수"], kosdaq_idx["등락률"])
st.write("")
st.divider()

tab1, tab2 = st.tabs(["🔥 강세 / 🧊 약세 종목", "⭐ 관심종목"])

with tab1:
    for market_name, df in [("코스피", kospi_df), ("코스닥", kosdaq_df)]:
        st.subheader(f"[{market_name}]")
        strong, weak = an.top_bottom(df, 10)
        cols = ["종목명", "현재가", "등락률", "초과등락률"]
        a, b = st.columns(2)
        a.markdown("**🔥 지수 대비 강세 Top 10**")
        a.dataframe(style_table(strong[cols]), hide_index=True, width="stretch")
        b.markdown("**🧊 지수 대비 약세 Bottom 10**")
        b.dataframe(style_table(weak[cols]), hide_index=True, width="stretch")

with tab2:
    if not auth.is_logged_in():
        st.info("⭐ 로그인하면 관심종목을 저장하고 손절 알림을 받을 수 있어요.")
        auth.login_button(label="Google로 로그인하고 시작하기", key="tab_login")
    elif not store.configured():
        st.warning("관심종목 저장소(DB)가 아직 설정되지 않았어요. (관리자 Supabase 키 필요)")
    else:
        uid = auth.user_id()
        listing = get_listing()
        st.markdown(f"**{auth.user_name()}님의 관심종목**")

        # 검색 + 추가
        q = st.text_input("종목 검색 (이름 또는 코드)",
                          placeholder="예: 삼성전자 또는 005930", key="wl_search")
        if q:
            res = ds.search_listing(listing, q)
            if res.empty:
                st.caption("검색 결과가 없어요.")
            else:
                scols = st.columns(3)
                for i, (_, r) in enumerate(res.iterrows()):
                    if scols[i % 3].button(f"➕ {r['종목명']}", key=f"add_{r['코드']}",
                                           width="stretch"):
                        store.add(uid, str(r["코드"]))
                        st.toast(f"✅ {r['종목명']} 추가")
                        st.rerun()

        threshold = st.slider("손절 경고 기준 (지수 대비 초과하락 %)",
                              1.0, 20.0, DEFAULT_STOPLOSS, 0.5)

        wl = store.get_watchlist(uid)
        if not wl:
            st.info("위에서 종목을 검색해 관심종목을 추가해 보세요.")
        else:
            rows = []
            for code in wl:
                info = listing[listing["코드"] == code]
                name = info["종목명"].iloc[0] if len(info) else code
                raw_mkt = str(info["시장"].iloc[0]) if len(info) else "KOSPI"
                cmp_mkt = "KOSDAQ" if raw_mkt.startswith("KOSDAQ") else "KOSPI"

                qd = intraday_quote(code, cmp_mkt)
                if qd:
                    price, rate, src = qd["현재가"], qd["등락률"], "장중"
                else:  # yfinance 실패 → 일별(FDR) 폴백
                    price = float(info["현재가"].iloc[0]) if len(info) else 0.0
                    rate = float(info["등락률"].iloc[0]) if len(info) else 0.0
                    src = "전일"

                ii = intraday_index(cmp_mkt)
                daily = kospi_idx if cmp_mkt == "KOSPI" else kosdaq_idx
                idx_rate = ii["등락률"] if ii else daily["등락률"]

                rows.append({
                    "종목명": name, "시장": cmp_mkt, "현재가": price, "등락률": rate,
                    "지수등락률": round(idx_rate, 2),
                    "초과등락률": round(rate - idx_rate, 2), "기준": src,
                })

            wdf = an.stoploss_flags(pd.DataFrame(rows), threshold)
            wdf["상태"] = wdf["손절경고"].map(lambda x: "⚠️ 손절 검토" if x else "정상")
            st.caption("💡 현재가·등락률은 장중 지연시세(약 15~20분), '기준=전일'은 종가 기준 · "
                       "**초과등락률에 마우스를 올리면 계산식**(종목 % − 지수 %)이 보여요")
            render_watchlist(wdf)

            st.caption("관심종목 삭제")
            dcols = st.columns(min(len(wl), 5))
            for i, code in enumerate(wl):
                nm = wdf["종목명"].iloc[i]
                if dcols[i % len(dcols)].button(f"➖ {nm}", key=f"del_{code}"):
                    store.remove(uid, code)
                    st.rerun()

st.divider()
st.caption("⚠️ " + DISCLAIMER)

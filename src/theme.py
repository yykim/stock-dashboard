"""v2 다크 테마 + Pretendard 폰트 주입 (v1 기본 라이트와 구분)."""
import streamlit as st

from .config import ACCENT, BG, CARD


def apply_theme():
    st.markdown(
        f"""
        <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@latest/dist/web/static/pretendard.css');

        html, body, [class*="css"], .stMarkdown, [data-testid="stMetric"] {{
            font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
        }}
        .stApp {{ background: {BG}; }}

        /* footer만 정리 (헤더·툴바·사이드바 컨트롤은 절대 건드리지 않음) */
        footer {{ visibility: hidden; }}

        /* 지수 메트릭 카드 */
        [data-testid="stMetric"] {{
            background: {CARD};
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 18px 22px;
        }}
        [data-testid="stMetricValue"] {{ font-weight: 700; }}

        h1, h2, h3 {{ color: #F1F5F9; letter-spacing: -0.5px; }}
        [data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; }}
        a {{ color: {ACCENT}; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

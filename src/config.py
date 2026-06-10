"""앱 전반 상수. (v2 — 공개 서비스용, pykrx 일별 데이터)"""

MARKETS = ["KOSPI", "KOSDAQ"]
INDEX_TICKER = {"KOSPI": "1001", "KOSDAQ": "2001"}  # pykrx 지수 코드

TOP_N = 80             # 각 시장 시총 상위 N개 (yfinance 배치 부담 고려해 적정선)
CACHE_TTL = 60 * 30    # 30분 (일별 데이터라 자주 갱신 불필요)
DEFAULT_STOPLOSS = 5.0  # 손절 경고 기준(%) — 지수 대비 초과하락

# v2 디자인 (v1과 구분: 다크 + 인디고)
ACCENT = "#6366F1"     # 인디고
BG = "#0F172A"
CARD = "#1E293B"

DISCLAIMER = (
    "본 서비스는 Yahoo Finance 시세(지연될 수 있음)를 사용하는 투자 참고용 서비스이며, "
    "투자 권유가 아닙니다. 모든 투자 판단과 책임은 투자자 본인에게 있습니다."
)

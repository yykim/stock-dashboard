"""
관심종목 장중 지연시세 (yfinance, 약 15~20분 지연).
- 한국 종목: 코스피 {코드}.KS / 코스닥 {코드}.KQ
- 실패하면 None을 반환 → 호출부에서 일별(FDR) 데이터로 폴백.
"""
import yfinance as yf

_STOCK_SUFFIX = {"KOSPI": "KS", "KOSDAQ": "KQ"}
_INDEX_TICKER = {"KOSPI": "^KS11", "KOSDAQ": "^KQ11"}


def _norm(market: str) -> str:
    return "KOSDAQ" if str(market).startswith("KOSDAQ") else "KOSPI"


def _pct(ticker: str):
    """yfinance fast_info로 (현재가, 등락률%) 반환. 실패 시 None."""
    fi = yf.Ticker(ticker).fast_info
    last, prev = fi.last_price, fi.previous_close
    if last and prev:
        return float(last), round((last / prev - 1) * 100, 2)
    return None


def intraday_quote(code: str, market: str):
    """개별 종목 장중 지연 현재가·등락률 (실패 시 None)."""
    suffix = _STOCK_SUFFIX[_norm(market)]
    try:
        r = _pct(f"{code}.{suffix}")
        if r:
            return {"현재가": r[0], "등락률": r[1]}
    except Exception:
        pass
    return None


def intraday_index(market: str):
    """지수 장중 지연 등락률 (실패 시 None)."""
    try:
        r = _pct(_INDEX_TICKER[_norm(market)])
        if r:
            return {"지수": r[0], "등락률": r[1]}
    except Exception:
        pass
    return None

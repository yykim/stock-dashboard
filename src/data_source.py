"""
데이터 소스 (클라우드 친화 버전)

* 종목 목록: 저장된 정적 CSV(data/listing.csv).
  KRX(data.krx.co.kr)가 클라우드 공유 IP를 간헐적으로 차단해서, 목록은 로컬에서
  미리 뽑아둔 스냅샷을 사용한다(코드·종목명·시장·시가총액). 주기적으로만 갱신.
* 등락률·현재가·지수: yfinance(Yahoo) — 클라우드에서 잘 작동.
  종목 = {코드}.KS/.KQ, 지수 = ^KS11/^KQ11.
"""
from pathlib import Path

import pandas as pd
import yfinance as yf

LISTING_CSV = Path(__file__).resolve().parent.parent / "data" / "listing.csv"
INDEX_SYMBOL = {"KOSPI": "^KS11", "KOSDAQ": "^KQ11"}


def load_listing():
    """정적 종목 목록 CSV 로드 (코드·종목명·시장·시가총액)."""
    return pd.read_csv(LISTING_CSV, dtype={"코드": str})


def _suffix(market: str) -> str:
    return "KQ" if str(market).startswith("KOSDAQ") else "KS"


def _yf_changes(codes, market: str) -> dict:
    """yfinance 일배치로 {코드: (현재가, 등락률%)} 반환."""
    suf = _suffix(market)
    tickers = [f"{c}.{suf}" for c in codes]
    if not tickers:
        return {}
    data = yf.download(tickers, period="7d", interval="1d", group_by="ticker",
                       auto_adjust=False, progress=False, threads=True)
    out = {}
    for c in codes:
        try:
            closes = data[f"{c}.{suf}"]["Close"].dropna()
            if len(closes) >= 2 and float(closes.iloc[-2]):
                last, prev = float(closes.iloc[-1]), float(closes.iloc[-2])
                out[c] = (last, round((last / prev - 1) * 100, 2))
        except Exception:
            pass
    return out


def get_market(listing, market: str, top_n: int):
    """시총 상위 top_n 종목 + yfinance 등락률·현재가."""
    sub = (listing[listing["시장"].astype(str).str.startswith(market)]
           .dropna(subset=["시가총액"])
           .sort_values("시가총액", ascending=False)
           .head(top_n).copy())
    ch = _yf_changes(sub["코드"].tolist(), market)
    sub["현재가"] = sub["코드"].map(lambda c: ch.get(c, (0.0, 0.0))[0])
    sub["등락률"] = sub["코드"].map(lambda c: ch.get(c, (0.0, 0.0))[1])
    sub = sub[sub["현재가"] > 0]  # yfinance에서 못 받은 종목 제외
    return sub[["코드", "종목명", "시장", "현재가", "등락률", "시가총액"]].reset_index(drop=True)


def search_listing(listing, query: str):
    """종목명 또는 코드로 검색 (최대 15건)."""
    q = query.strip()
    if not q:
        return listing.iloc[0:0]
    mask = (listing["종목명"].astype(str).str.contains(q, case=False, na=False)
            | listing["코드"].astype(str).str.contains(q, na=False))
    return listing[mask].head(15)


def get_index(market: str) -> dict:
    """코스피/코스닥 지수값·등락률 (yfinance, 일별 종가 기준)."""
    sym = INDEX_SYMBOL["KOSDAQ" if str(market).startswith("KOSDAQ") else "KOSPI"]
    try:
        data = yf.download(sym, period="7d", interval="1d", progress=False, auto_adjust=False)
        closes = data["Close"]
        if isinstance(closes, pd.DataFrame):
            closes = closes.iloc[:, 0]
        closes = closes.dropna()
        if len(closes) == 0:
            return {"지수": 0.0, "등락률": 0.0, "날짜": ""}
        last = float(closes.iloc[-1])
        rate = round((last / float(closes.iloc[-2]) - 1) * 100, 2) if len(closes) >= 2 else 0.0
        return {"지수": last, "등락률": rate, "날짜": closes.index[-1].strftime("%Y%m%d")}
    except Exception:
        return {"지수": 0.0, "등락률": 0.0, "날짜": ""}

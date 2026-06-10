"""
데이터 소스 (FinanceDataReader 기반, KRX 일별 종가)

* 당초 pykrx 계획이었으나, 최신 pykrx가 KRX 회원 로그인(KRX_ID/PW)을 요구해
  무료 공개 서비스에 부적합 → FinanceDataReader로 전환.
  FDR도 KRX 공식 데이터(EOD)라 합법·안정. 장중 실시간 아님(종가 기준).
"""
import pandas as pd
import FinanceDataReader as fdr

INDEX_SYMBOL = {"KOSPI": "KS11", "KOSDAQ": "KQ11"}  # FDR 지수 심볼


def _normalize(df, market_label=None):
    """FDR 결과 컬럼을 표준(코드·종목명·시장·현재가·등락률·시가총액)으로 정규화.

    일반 주식 목록과 ETF 목록은 컬럼명이 달라(예: Close/Price, ChagesRatio/ChangeRate,
    Marcap/MarCap) 둘 다 흡수한다.
    """
    code = "Code" if "Code" in df.columns else "Symbol"
    ren = {code: "코드", "Name": "종목명", "Market": "시장"}
    if "Close" in df.columns:
        ren["Close"] = "현재가"
    elif "Price" in df.columns:
        ren["Price"] = "현재가"
    if "ChagesRatio" in df.columns:
        ren["ChagesRatio"] = "등락률"
    elif "ChangeRate" in df.columns:
        ren["ChangeRate"] = "등락률"
    if "Marcap" in df.columns:
        ren["Marcap"] = "시가총액"
    elif "MarCap" in df.columns:
        ren["MarCap"] = "시가총액"

    df = df.rename(columns=ren)
    if market_label is not None:
        df["시장"] = market_label
    keep = ["코드", "종목명", "시장", "현재가", "등락률", "시가총액"]
    df = df[[c for c in keep if c in df.columns]].copy()
    df["코드"] = df["코드"].astype(str)
    if "등락률" in df.columns:
        df["등락률"] = df["등락률"].fillna(0.0)
    return df


def load_listing():
    """KRX 전체 종목 + ETF 목록 (검색·관심종목용).

    시장 컬럼: KOSPI / KOSDAQ / ETF. (ETF는 검색엔 나오지만 시장 강세/약세 스캔에선 제외)
    """
    stocks = _normalize(fdr.StockListing("KRX"))
    try:
        etfs = _normalize(fdr.StockListing("ETF/KR"), market_label="ETF")
    except Exception:
        etfs = stocks.iloc[0:0]
    df = pd.concat([stocks, etfs], ignore_index=True)
    return df.drop_duplicates(subset=["코드"], keep="first")


def get_market(listing, market: str, top_n: int):
    """해당 시장(KOSPI/KOSDAQ) 시총 상위 top_n 종목 (ETF는 시장명으로 자연 제외)."""
    df = listing[listing["시장"].astype(str).str.startswith(market)].copy()
    df = df.dropna(subset=["시가총액"]).sort_values("시가총액", ascending=False).head(top_n)
    return df.reset_index(drop=True)


def search_listing(listing, query: str):
    """종목명 또는 코드로 검색 (최대 15건)."""
    q = query.strip()
    if not q:
        return listing.iloc[0:0]
    mask = (
        listing["종목명"].str.contains(q, case=False, na=False)
        | listing["코드"].astype(str).str.contains(q, na=False)
    )
    return listing[mask].head(15)


def get_index(market: str) -> dict:
    """코스피/코스닥 지수의 지수값·일별 등락률(%)·기준일을 반환한다."""
    idx = fdr.DataReader(INDEX_SYMBOL[market])
    close = idx["Close"].dropna()
    if len(close) == 0:
        return {"지수": 0.0, "등락률": 0.0, "날짜": ""}
    level = float(close.iloc[-1])
    rate = (close.iloc[-1] / close.iloc[-2] - 1) * 100 if len(close) >= 2 else 0.0
    return {
        "지수": level,
        "등락률": round(float(rate), 2),
        "날짜": close.index[-1].strftime("%Y%m%d"),
    }

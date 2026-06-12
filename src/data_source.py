"""
데이터 소스 (클라우드 친화 + 스냅샷 폴백)

* 종목 목록: 정적 CSV(data/listing.csv) — KRX가 클라우드 IP를 막아서 로컬 스냅샷 사용.
* 시세·지수: yfinance(Yahoo) 라이브 우선.
  ⚠️ 클라우드(예: Render) 공유 IP가 야후에 rate-limit 당하면 시세가 비어버린다.
  → 로컬에서 만든 '시세 스냅샷'(data/snapshot_prices.csv, snapshot_index.json)으로 폴백.
  즉 라이브가 되면 최신값, 막히면 스냅샷값 → 데모가 빈 표가 되지 않는다.
  스냅샷 갱신: `python tools/refresh_snapshot.py` 실행 후 commit/push.
"""
import json
from pathlib import Path

import pandas as pd
import yfinance as yf

DATA = Path(__file__).resolve().parent.parent / "data"
LISTING_CSV = DATA / "listing.csv"
SNAP_PRICES = DATA / "snapshot_prices.csv"
SNAP_INDEX = DATA / "snapshot_index.json"
SNAP_SUPPLY = DATA / "snapshot_supply.json"
INDEX_SYMBOL = {"KOSPI": "^KS11", "KOSDAQ": "^KQ11"}


def load_listing():
    """정적 종목 목록 CSV 로드 (코드·종목명·시장·시가총액)."""
    return pd.read_csv(LISTING_CSV, dtype={"코드": str})


def _suffix(market: str) -> str:
    return "KQ" if str(market).startswith("KOSDAQ") else "KS"


def _yf_changes(codes, market: str) -> dict:
    """yfinance 일배치로 {코드: (현재가, 등락률%)} 반환. 실패 시 빈 dict."""
    suf = _suffix(market)
    tickers = [f"{c}.{suf}" for c in codes]
    if not tickers:
        return {}
    try:
        data = yf.download(tickers, period="7d", interval="1d", group_by="ticker",
                           auto_adjust=False, progress=False, threads=True, timeout=12)
    except Exception:
        return {}
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


def _snapshot_prices() -> dict:
    """폴백용 시세 스냅샷 {코드: (현재가, 등락률)}."""
    try:
        df = pd.read_csv(SNAP_PRICES, dtype={"코드": str})
        return {r["코드"]: (float(r["현재가"]), float(r["등락률"])) for _, r in df.iterrows()}
    except Exception:
        return {}


def _snapshot_index() -> dict:
    """폴백용 지수 스냅샷 {'KOSPI': {지수,등락률,날짜}, 'KOSDAQ': {...}}."""
    try:
        return json.loads(SNAP_INDEX.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_market(listing, market: str, top_n: int):
    """시총 상위 top_n 종목 + 시세. 라이브(yfinance) 우선, 실패분은 스냅샷 폴백."""
    sub = (listing[listing["시장"].astype(str).str.startswith(market)]
           .dropna(subset=["시가총액"])
           .sort_values("시가총액", ascending=False)
           .head(top_n).copy())
    ch = _yf_changes(sub["코드"].tolist(), market)            # 라이브 시도
    snap = _snapshot_prices() if len(ch) < len(sub) else {}   # 일부라도 실패하면 스냅샷 로드
    sub["현재가"] = sub["코드"].map(lambda c: (ch.get(c) or snap.get(c) or (0.0, 0.0))[0])
    sub["등락률"] = sub["코드"].map(lambda c: (ch.get(c) or snap.get(c) or (0.0, 0.0))[1])
    sub = sub[sub["현재가"] > 0]   # 라이브·스냅샷 모두 없는 종목만 제외
    return sub[["코드", "종목명", "시장", "현재가", "등락률", "시가총액"]].reset_index(drop=True)


def search_listing(listing, query: str):
    """종목명 또는 코드로 검색 (최대 15건)."""
    q = query.strip()
    if not q:
        return listing.iloc[0:0]
    mask = (listing["종목명"].astype(str).str.contains(q, case=False, na=False)
            | listing["코드"].astype(str).str.contains(q, na=False))
    return listing[mask].head(15)


def _live_index(market: str) -> dict:
    """yfinance 라이브 지수값·등락률 (일별 종가)."""
    sym = INDEX_SYMBOL["KOSDAQ" if str(market).startswith("KOSDAQ") else "KOSPI"]
    try:
        data = yf.download(sym, period="7d", interval="1d", progress=False,
                           auto_adjust=False, timeout=10)
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


def market_meta() -> dict:
    """데이터의 '실제 시각'과 장 상태.

    KRX 지수(^KS11) 분봉의 마지막 봉 시각(야후, ~15~20분 지연)을 사용 — 코스피·코스닥 공통.
    batch download 계열이라 클라우드(Render)에서도 동작한다(get_info는 클라우드 IP에서
    rate-limit으로 자주 실패해 안 씀). 실패 시 빈 dict.
    """
    try:
        h = yf.download("^KS11", period="5d", interval="5m",
                        progress=False, auto_adjust=False, timeout=10)
        if len(h):
            ts = h.index[-1]   # tz-aware(Asia/Seoul)
            kst = ts.tz_convert("Asia/Seoul") if ts.tzinfo else (ts + pd.Timedelta(hours=9))
            after_close = (kst.hour * 60 + kst.minute) >= 15 * 60 + 25  # 15:25 이후 = 마감
            return {"시각": kst.strftime("%Y-%m-%d %H:%M"),
                    "상태": "장마감 종가" if after_close else "장중 (약 15~20분 지연)"}
    except Exception:
        pass
    return {}


def get_index(market: str) -> dict:
    """코스피/코스닥 지수 + 데이터 실제 시각. 라이브 우선, 실패 시 스냅샷 폴백."""
    key = "KOSDAQ" if str(market).startswith("KOSDAQ") else "KOSPI"
    res = _live_index(market)
    if res.get("지수", 0) > 0:
        meta = market_meta()  # 실제 데이터 시각(라이브)
        d = res.get("날짜", "")
        res["시각"] = meta.get("시각") or (f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else d)
        res["상태"] = meta.get("상태", "")
        res["source"] = "live"
        return res
    snap = _snapshot_index().get(key)   # 폴백: 스냅샷에 저장된 '실제 데이터 시각' 사용
    if snap:
        return {**snap, "source": "snapshot"}
    return {**res, "시각": "", "상태": "", "source": "live"}


def get_supply() -> dict:
    """투자자별 수급 스냅샷 (장마감 기준, 단위: 억원, 순매수).

    {'기준일': 'YYYY-MM-DD', 'KOSPI': {외국인,기관,개인}, 'KOSDAQ': {...}}
    KRX(클라우드 차단)·pykrx(로그인 필요) 대신, 로컬에서 Naver를 크롤해 만든 스냅샷을 읽는다.
    (클라우드는 직접 크롤하지 않고 커밋된 스냅샷만 표시 — `tools/refresh_snapshot.py`로 갱신.)
    """
    try:
        return json.loads(SNAP_SUPPLY.read_text(encoding="utf-8"))
    except Exception:
        return {}

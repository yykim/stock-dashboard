"""
시세 스냅샷 생성기 (Render 등 클라우드에서 yfinance rate-limit 시 폴백용).

로컬(rate-limit 안 걸리는 IP)에서 실행 → data/snapshot_prices.csv, snapshot_index.json 갱신
→ git commit/push 하면 Render 배포본이 라이브 실패 시 이 값으로 폴백한다.

사용:
    ./venv/bin/python tools/refresh_snapshot.py

데모를 최신 상태로 유지하려면 가끔(주 1회 등) 다시 실행해 커밋하면 됨.
"""
import datetime
import json
import re
import sys
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
import pandas as pd  # noqa: E402
from src import data_source as ds  # noqa: E402
from src.config import TOP_N  # noqa: E402


_H = {"User-Agent": "Mozilla/5.0"}


def fetch_supply(sosok: str, bizdate: str):
    """Naver 투자자별 매매동향에서 최신 영업일의 외국인·기관·개인 순매수(억원)."""
    url = ("https://finance.naver.com/sise/investorDealTrendDay.naver"
           f"?bizdate={bizdate}&sosok={sosok}")
    r = httpx.get(url, headers=_H, timeout=10)
    r.encoding = "euc-kr"
    df = pd.read_html(StringIO(r.text))[0].dropna(how="all")
    for _, row in df.iterrows():
        d = str(row.iloc[0])
        if re.match(r"\d{2}\.\d{2}\.\d{2}", d):   # 날짜 행(YY.MM.DD)이 최신값
            return {"날짜": "20" + d.replace(".", "-"),
                    "개인": int(row.iloc[1]), "외국인": int(row.iloc[2]), "기관": int(row.iloc[3])}
    return None

listing = ds.load_listing()
rows = []
for market in ["KOSPI", "KOSDAQ"]:
    sub = (listing[listing["시장"].astype(str).str.startswith(market)]
           .dropna(subset=["시가총액"])
           .sort_values("시가총액", ascending=False)
           .head(TOP_N))
    ch = ds._yf_changes(sub["코드"].tolist(), market)
    for code, (price, rate) in ch.items():
        rows.append({"코드": code, "현재가": price, "등락률": rate})
    print(f"  {market}: {len(ch)}/{len(sub)} 종목 시세 수집")

if not rows:
    print("⚠️ 시세를 하나도 못 받았어요 (yfinance rate-limit?). 잠시 후 다시 실행하세요.")
    sys.exit(1)

pd.DataFrame(rows).to_csv(ds.SNAP_PRICES, index=False)

meta = ds.market_meta()   # 데이터 실제 시각·장상태 (스냅샷에 함께 저장 → 폴백 시 정확)
idx = {}
for m in ["KOSPI", "KOSDAQ"]:
    base = ds._live_index(m)
    base.update(meta)
    idx[m] = base
ds.SNAP_INDEX.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")

# ---- 투자자별 수급 (Naver 크롤) ----
bizdate = datetime.datetime.now().strftime("%Y%m%d")
supply = {}
for sosok, m in [("01", "KOSPI"), ("02", "KOSDAQ")]:
    try:
        s = fetch_supply(sosok, bizdate)
        if s:
            supply.setdefault("기준일", s["날짜"])
            supply[m] = {"외국인": s["외국인"], "기관": s["기관"], "개인": s["개인"]}
            print(f"  {m} 수급: 외국인 {s['외국인']:+,} 기관 {s['기관']:+,} 개인 {s['개인']:+,} (억원)")
    except Exception as e:
        print(f"  ⚠️ {m} 수급 크롤 실패: {repr(e)[:80]}")
if supply.get("KOSPI") or supply.get("KOSDAQ"):
    # 수급 집계 시각·장상태 (가격과 동일 run의 market_meta 재사용 → 캡션 일관)
    supply["시각"] = meta.get("시각") or supply.get("기준일", "")
    supply["상태"] = meta.get("상태", "")
    ds.SNAP_SUPPLY.write_text(json.dumps(supply, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"\n✅ 저장: {ds.SNAP_PRICES.name} ({len(rows)}종목), {ds.SNAP_INDEX.name}, {ds.SNAP_SUPPLY.name}")
print(f"   지수: KOSPI {idx['KOSPI']['지수']} ({idx['KOSPI']['등락률']:+}%), "
      f"KOSDAQ {idx['KOSDAQ']['지수']} ({idx['KOSDAQ']['등락률']:+}%)")
print("   → git add data/ && commit && push 하면 Render 폴백에 반영됩니다.")

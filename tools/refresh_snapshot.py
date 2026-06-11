"""
시세 스냅샷 생성기 (Render 등 클라우드에서 yfinance rate-limit 시 폴백용).

로컬(rate-limit 안 걸리는 IP)에서 실행 → data/snapshot_prices.csv, snapshot_index.json 갱신
→ git commit/push 하면 Render 배포본이 라이브 실패 시 이 값으로 폴백한다.

사용:
    ./venv/bin/python tools/refresh_snapshot.py

데모를 최신 상태로 유지하려면 가끔(주 1회 등) 다시 실행해 커밋하면 됨.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
from src import data_source as ds  # noqa: E402
from src.config import TOP_N  # noqa: E402

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

idx = {m: ds._live_index(m) for m in ["KOSPI", "KOSDAQ"]}
ds.SNAP_INDEX.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"\n✅ 저장: {ds.SNAP_PRICES.name} ({len(rows)}종목), {ds.SNAP_INDEX.name}")
print(f"   지수: KOSPI {idx['KOSPI']['지수']} ({idx['KOSPI']['등락률']:+}%), "
      f"KOSDAQ {idx['KOSDAQ']['지수']} ({idx['KOSDAQ']['등락률']:+}%)")
print("   → git add data/ && commit && push 하면 Render 폴백에 반영됩니다.")

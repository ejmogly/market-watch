"""USD/KRW 일별 환율(2020-01~) → data/history/fx_usdkrw.csv

포지션 섹션이 달러 실현손익을 매도일 환율로 원화 환산할 때 쓴다.
출처는 Yahoo Finance chart API `KRW=X`(비공식 경로), 값은 그날 종가(서울 날짜 기준).

실행: python3 scripts/fetch_fx.py
"""
import csv
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from backfill_history import YAHOO, get_json

OUT = Path(__file__).resolve().parent.parent / "data" / "history" / "fx_usdkrw.csv"
FROM = "2020-01-01"


def main():
    p1 = int(datetime.fromisoformat(FROM).replace(tzinfo=timezone.utc).timestamp())
    res = get_json(YAHOO.format(sym="KRW=X", p1=p1, p2=int(time.time())))["chart"]["result"][0]
    tz = ZoneInfo("Asia/Seoul")
    rows = {}
    for ts, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"]):
        if c:
            rows[datetime.fromtimestamp(ts, tz).date().isoformat()] = round(c, 2)
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "usdkrw"])
        w.writerows(sorted(rows.items()))
    d = sorted(rows)
    print(f"{OUT.name}: {len(d)} rows {d[0]}~{d[-1]} last={rows[d[-1]]}")


if __name__ == "__main__":
    main()

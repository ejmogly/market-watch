"""관심 종목 과거 일봉 백필: 2024-01부터 받아 2025-01-01 이후 일자별 지표·판단을 계산한다.

계산식은 routines/_common.md와 같다.
- 이동평균 20·50·200 = 그 날로 끝나는 N개 종가의 단순 평균
- ATR(14) = True Range의 와일더 평활(첫 값 14개 단순 평균, 이후 (전 ATR×13 + TR)÷14)
- 52주 최고·최저 = 그 날까지 1년(주식 252거래일, 크립토 365일) 고가·저가. 52주 위치(%) = (종가−최저)÷(최고−최저)×100
- 한 줄 판단 = 관심/관망/비중 축소. 종가 200개 미만이면 200→50, 50→20일선으로 한 칸 내린다
출처는 Yahoo Finance chart API(해외·크립토, 비공식 경로)와 네이버 증권 일별 시세 API(국내, 비공식 경로).

실행: python3 scripts/backfill_history.py  → data/history/{history.csv, history.json, meta.json}
"""
import csv
import json
import ssl
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "history"
FETCH_FROM = "2024-01-01"
KEEP_FROM = "2025-01-01"
UA = {"User-Agent": "Mozilla/5.0"}

# asset, 이름, 시장, 통화, 출처 심볼
ASSETS = [
    ("TSLA", "테슬라", "US", "USD", "TSLA"),
    ("GOOGL", "알파벳 A", "US", "USD", "GOOGL"),
    ("NVDA", "엔비디아", "US", "USD", "NVDA"),
    ("SpaceX", "스페이스X", "US", "USD", "SPCX"),
    ("AAPL", "애플", "US", "USD", "AAPL"),
    ("VOO", "Vanguard S&P 500 ETF", "US", "USD", "VOO"),
    ("SMH", "VanEck Semiconductor ETF", "US", "USD", "SMH"),
    ("QQQM", "Invesco NASDAQ 100 ETF", "US", "USD", "QQQM"),
    ("BTC", "비트코인", "CRYPTO", "USD", "BTC-USD"),
    ("ETH", "이더리움", "CRYPTO", "USD", "ETH-USD"),
    ("삼성전자", "삼성전자", "KR", "KRW", "005930"),
    ("SK하이닉스", "SK하이닉스", "KR", "KRW", "000660"),
    ("현대차", "현대차", "KR", "KRW", "005380"),
    ("두산에너빌리티", "두산에너빌리티", "KR", "KRW", "034020"),
]
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d"
NAVER = "https://api.stock.naver.com/chart/domestic/item/{code}/day?startDateTime={s}0000&endDateTime={e}2359"


# 인증서 검증은 그대로 하되, 중간 프록시 인증서가 걸리는 파이썬 3.13+의 엄격 모드(X509_STRICT)만 끈다
CTX = ssl.create_default_context()
CTX.verify_flags &= ~ssl.VERIFY_X509_STRICT


def get_json(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30, context=CTX) as r:
                return json.load(r)
        except Exception:  # 429 등은 간격을 두고 재시도
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))


def fetch_yahoo(sym, market):
    p1 = int(datetime.fromisoformat(FETCH_FROM).replace(tzinfo=timezone.utc).timestamp())
    p2 = int(time.time())
    url = YAHOO.format(sym=sym, p1=p1, p2=p2)
    res = get_json(url)["chart"]["result"][0]
    tz = ZoneInfo(res["meta"]["exchangeTimezoneName"]) if market != "CRYPTO" else timezone.utc
    q = res["indicators"]["quote"][0]
    rows, dropped = [], []
    for i, ts in enumerate(res["timestamp"]):
        d = datetime.fromtimestamp(ts, tz).date().isoformat()
        o, h, l, c, v = (q[k][i] for k in ("open", "high", "low", "close", "volume"))
        if None in (h, l, c):
            dropped.append(d)
            continue
        rows.append({"date": d, "open": o, "high": h, "low": l, "close": c, "volume": v})
    # 같은 날짜가 두 번 오면(장중 마지막 봉) 뒤의 것을 쓴다
    dedup = {r["date"]: r for r in rows}
    # 끝나지 않은 오늘 봉은 뺀다(크립토 UTC 일봉, 미국장 장중)
    today = datetime.now(tz).date().isoformat()
    if market == "CRYPTO" or res["meta"].get("currentTradingPeriod", {}).get("regular", {}).get("end", 0) > time.time():
        dedup.pop(today, None)
    filled = []
    for d in dropped:  # 빈 일봉은 같은 날 1시간봉으로 채운다(이슈 #7)
        if d == today:
            continue
        bar = fill_from_hourly(sym, d)
        if bar:
            dedup[d] = bar
            filled.append(d)
    return url.split("?")[0], [dedup[k] for k in sorted(dedup)], [d for d in dropped if d not in filled], filled


def fill_from_hourly(sym, d):
    t0 = int(datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp())
    res = get_json(YAHOO.format(sym=sym, p1=t0, p2=t0 + 86400).replace("interval=1d", "interval=1h"))["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    bars = [(ts, q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i])
            for i, ts in enumerate(res.get("timestamp") or []) if t0 <= ts < t0 + 86400 and q["close"][i] is not None]
    if len(bars) < 20:  # 하루 24개 중 대부분이 있어야 쓴다
        return None
    return {"date": d, "open": bars[0][1], "high": max(b[2] for b in bars), "low": min(b[3] for b in bars),
            "close": bars[-1][4], "volume": sum(b[5] or 0 for b in bars), "filled_from": "1h"}


def fetch_naver(code):
    end = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d")
    url = NAVER.format(code=code, s=FETCH_FROM.replace("-", ""), e=end)
    rows = [{"date": f'{r["localDate"][:4]}-{r["localDate"][4:6]}-{r["localDate"][6:]}',
             "open": r["openPrice"], "high": r["highPrice"], "low": r["lowPrice"],
             "close": r["closePrice"], "volume": r["accumulatedTradingVolume"]} for r in get_json(url)]
    return url.split("?")[0], sorted(rows, key=lambda r: r["date"]), [], []


def sma(vals, n, i):
    return sum(vals[i - n + 1:i + 1]) / n if i >= n - 1 else None


def compute(rows, market):
    closes = [r["close"] for r in rows]
    win = 365 if market == "CRYPTO" else 252
    atr = None
    trs = []
    for i, r in enumerate(rows):
        tr = r["high"] - r["low"] if i == 0 else max(
            r["high"] - r["low"], abs(r["high"] - closes[i - 1]), abs(r["low"] - closes[i - 1]))
        trs.append(tr)
        if i == 13:
            atr = sum(trs[:14]) / 14
        elif i > 13:
            atr = (atr * 13 + tr) / 14
        r["atr14"] = atr if i >= 13 else None
        r["ret"] = (r["close"] / closes[i - 1] - 1) * 100 if i > 0 else None
        for n in (20, 50, 200):
            r[f"ma{n}"] = sma(closes, n, i)
        lo = max(0, i - win + 1)
        hi52, lo52 = max(x["high"] for x in rows[lo:i + 1]), min(x["low"] for x in rows[lo:i + 1])
        r["hi52"], r["lo52"] = hi52, lo52
        r["pos52"] = (r["close"] - lo52) / (hi52 - lo52) * 100 if hi52 > lo52 else None
        r["n_closes"] = i + 1
        # 판단 규칙. 200일선이 없으면 한 칸 내림(200→50, 50→20)
        long_, mid = ("ma200", "ma50") if r["ma200"] is not None else ("ma50", "ma20")
        r["basis"] = "200일선" if long_ == "ma200" else "50일선"
        L, M, c = r[long_], r[mid], r["close"]
        if L is None or M is None:
            r["label"] = None
        elif c >= L and M >= L:
            r["label"] = "관심"
        elif c < L and M < L:
            r["label"] = "비중 축소"
        else:
            r["label"] = "관망"
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meta, out = {"generated_at": datetime.now(timezone.utc).isoformat(), "fetch_from": FETCH_FROM,
                 "keep_from": KEEP_FROM, "assets": []}, []
    for asset, name, market, cur, sym in ASSETS:
        src, rows, dropped, filled = fetch_naver(sym) if market == "KR" else fetch_yahoo(sym, market)
        rows = compute(rows, market)
        kept = [r for r in rows if r["date"] >= KEEP_FROM]
        for r in kept:
            out.append({"asset": asset, "market": market, "currency": cur, **r})
        meta["assets"].append({"asset": asset, "name": name, "market": market, "currency": cur, "symbol": sym,
                               "source": src + " (비공식 경로)", "first": rows[0]["date"], "last": rows[-1]["date"],
                               "rows_fetched": len(rows), "rows_kept": len(kept),
                               "close_before_keep": ([r["close"] for r in rows if r["date"] < KEEP_FROM] or [None])[-1], "dropped_null_days": dropped,
                               "filled_from_hourly": filled})
        print(f"{asset:10s} {market:6s} {rows[0]['date']}~{rows[-1]['date']} fetched={len(rows)} kept={len(kept)} "
              f"dropped={len(dropped)} filled={filled}")
        time.sleep(1.5)
    cols = ["asset", "market", "currency", "date", "open", "high", "low", "close", "volume", "ret",
            "ma20", "ma50", "ma200", "atr14", "hi52", "lo52", "pos52", "n_closes", "basis", "label"]
    with open(OUT / "history.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in out:
            w.writerow({k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items() if k in cols})
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print("rows", len(out))


if __name__ == "__main__":
    main()

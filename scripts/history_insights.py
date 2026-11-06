"""data/history/history.csv → data/history/insights.json (수익률·낙폭·변동성·상관·판단 규칙 사후 성과)."""
import csv, json, math, statistics
from collections import defaultdict
from pathlib import Path

H = Path(__file__).resolve().parent.parent / "data" / "history"
rows = list(csv.DictReader(open(H / "history.csv")))
by = defaultdict(list)
for r in rows:
    for k in ("close", "high", "low", "ret", "ma20", "ma50", "ma200", "atr14", "pos52"):
        r[k] = float(r[k]) if r[k] not in ("", None) else None
    by[r["asset"]].append(r)
order = ["TSLA", "GOOGL", "NVDA", "SpaceX", "AAPL", "VOO", "SMH", "QQQM", "BTC", "ETH", "삼성전자", "SK하이닉스", "현대차", "두산에너빌리티"]

def ret_between(rs, d0, d1):
    a = [r for r in rs if r["date"] < d0]  # d0 전 마지막 종가가 시작
    b = [r for r in rs if r["date"] <= d1]
    if not b:
        return None
    start = a[-1]["close"] if a else rs[0]["close"]
    return (b[-1]["close"] / start - 1) * 100

HS = (20, 60)  # 판단 뒤 20·60거래일(크립토는 일) 수익률
out = {"assets": {}, "label_forward": {}, "corr": {}}
pool = {h: defaultdict(list) for h in HS}
for a in order:
    rs = by[a]
    peak, mdd, mdd_at = -1, 0, None
    for r in rs:
        peak = max(peak, r["close"])
        dd = (r["close"] / peak - 1) * 100
        if dd < mdd:
            mdd, mdd_at = dd, r["date"]
    rets = [r["ret"] for r in rs if r["ret"] is not None]
    ann = 365 if rs[0]["market"] == "CRYPTO" else 252
    fwd = {h: defaultdict(list) for h in HS}
    for h in HS:
        for i, r in enumerate(rs[:-h]):
            if r["label"]:
                f = (rs[i + h]["close"] / r["close"] - 1) * 100
                fwd[h][r["label"]].append(f)
                pool[h][r["label"]].append(f)
    changes = [(rs[i]["date"], rs[i - 1]["label"], rs[i]["label"]) for i in range(1, len(rs))
               if rs[i]["label"] != rs[i - 1]["label"] and rs[i - 1]["label"]]
    last = rs[-1]
    out["assets"][a] = {
        "market": rs[0]["market"], "currency": rs[0]["currency"], "first": rs[0]["date"], "last": last["date"],
        "days": len(rs),
        "ret_2025": ret_between(rs, "2025-01-01", "2025-12-31") if rs[0]["date"] < "2025-06-01" else None,
        "ret_2026ytd": ret_between(rs, "2026-01-01", "2026-12-31"),
        "ret_total": (last["close"] / rs[0]["close"] - 1) * 100,
        "mdd": mdd, "mdd_at": mdd_at, "dd_now": (last["close"] / max(r["close"] for r in rs) - 1) * 100,
        "vol_ann": statistics.stdev(rets) * math.sqrt(ann) if len(rets) > 2 else None,
        "label_now": last["label"], "label_days": {k: sum(1 for r in rs if r["label"] == k) for k in ("관심", "관망", "비중 축소")},
        "label_changes": len(changes), "last_change": changes[-1] if changes else None,
        "fwd": {h: {k: {"n": len(v), "mean": statistics.mean(v), "win": sum(1 for x in v if x > 0) / len(v) * 100}
                    for k, v in fwd[h].items() if v} for h in HS},
    }
out["label_forward"] = {h: {k: {"n": len(v), "mean": statistics.mean(v), "median": statistics.median(v),
                                "win": sum(1 for x in v if x > 0) / len(v) * 100} for k, v in pool[h].items()} for h in HS}
# 상관: 같은 날짜가 있는 날의 일간 수익률(미국 거래일 기준, 국내는 국내끼리 + 미국과는 겹치는 날짜)
rmap = {a: {r["date"]: r["ret"] for r in by[a] if r["ret"] is not None} for a in order if a != "SpaceX"}
def corr(x, y):
    d = sorted(set(rmap[x]) & set(rmap[y]))
    if len(d) < 60:
        return None
    return statistics.correlation([rmap[x][k] for k in d], [rmap[y][k] for k in d])
names = [a for a in order if a != "SpaceX"]
out["corr"] = {"assets": names, "matrix": [[corr(x, y) if x != y else 1.0 for y in names] for x in names]}
(H / "insights.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
for a, v in out["assets"].items():
    f = lambda x: "—" if x is None else f"{x:+.1f}"
    print(f"{a:8s} 2025 {f(v['ret_2025']):>7} 26YTD {f(v['ret_2026ytd']):>7} 전체 {f(v['ret_total']):>7} MDD {v['mdd']:6.1f}({v['mdd_at']}) 지금낙폭 {v['dd_now']:6.1f} 변동성 {f(v['vol_ann'])} 판단 {v['label_now']} 변경{v['label_changes']} 최근변경 {v['last_change']}")
print({h: {k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in d.items()} for h, d in out["label_forward"].items()})

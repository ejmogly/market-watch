"""history.csv → data/history/monthly.json : 자산 × 월 요약(월말 종가, 월 수익률, 월중 최고·최저, 월말 판단, 판단 변경, 관심 일수)."""
import csv, json
from collections import defaultdict
from pathlib import Path

H = Path(__file__).resolve().parent.parent / "data" / "history"
meta = {a["asset"]: a for a in json.load(open(H / "meta.json"))["assets"]}
by = defaultdict(lambda: defaultdict(list))
for r in csv.DictReader(open(H / "history.csv")):
    by[r["asset"]][r["date"][:7]].append(r)
out = []
for a, months in by.items():
    prev_close, prev_label = meta[a]["close_before_keep"], None
    for m in sorted(months):
        rs = months[m]
        c = float(rs[-1]["close"])
        labels = [r["label"] for r in rs]
        changes = sum(1 for i in range(1, len(labels)) if labels[i] != labels[i - 1] and labels[i - 1])
        if prev_label and labels[0] and labels[0] != prev_label:
            changes += 1
        out.append({"asset": a, "market": rs[0]["market"], "currency": rs[0]["currency"], "month": m,
                    "close": c, "ret": (c / prev_close - 1) * 100 if prev_close else None,
                    "high": max(float(r["high"]) for r in rs), "low": min(float(r["low"]) for r in rs),
                    "label_end": labels[-1] or None, "changes": changes,
                    "days_interest": sum(1 for l in labels if l == "관심"), "days": len(rs),
                    "partial": m == "2026-09"})
        prev_close, prev_label = c, labels[-1] or prev_label
(H / "monthly.json").write_text(json.dumps(out, ensure_ascii=False))
print(len(out), "rows")

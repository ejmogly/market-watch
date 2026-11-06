"""history_template.html + data/history/*.json → history.html (게시용 단일 파일)."""
import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "data" / "history"
ins = json.load(open(H / "insights.json"))
meta = json.load(open(H / "meta.json"))
L = {"관심": 1, "관망": 0, "비중 축소": -1, "": None}
series = {}
rows = list(csv.DictReader(open(H / "history.csv")))
for a in ins["assets"]:
    rs = [r for r in rows if r["asset"] == a]
    nd = 0 if rs[0]["currency"] == "KRW" else 2
    f = lambda v: None if v == "" else round(float(v), nd)
    series[a] = {"d": [r["date"] for r in rs], "c": [f(r["close"]) for r in rs], "m50": [f(r["ma50"]) for r in rs],
                 "m200": [f(r["ma200"]) for r in rs], "l": [L[r["label"]] for r in rs]}
data = {"series": series, "insights": ins, "generated": meta["generated_at"][:10],
        "meta": {m["asset"]: {k: m[k] for k in ("name", "market", "currency", "symbol", "first", "last")} for m in meta["assets"]}}
tpl = (ROOT / "history_template.html").read_text()
(ROOT / "history.html").write_text(tpl.replace("/*DATA*/", json.dumps(data, ensure_ascii=False, separators=(",", ":"))))
print("history.html", (ROOT / "history.html").stat().st_size)

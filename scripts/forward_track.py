"""표본 밖 성과 추적: 2026-09-26 이후 한 줄 판단(관심·관망·비중 축소)의 5·20·60거래일 뒤 수익률.

판단은 CLAUDE.md "판단 규칙"(200일선 없는 종목 규칙 포함)과 같은 식이다. 식이 달라지지 않도록
scripts/backfill_history.py의 compute()를 그대로 불러 다시 계산하고, history.csv의 label과 대조한다.

실행: python3 scripts/forward_track.py
입력: data/history/history.csv (가격을 새로 받으려면 먼저 python3 scripts/backfill_history.py)
출력: metrics/forward_labels.csv   표본 밖 판단 한 줄씩(쌓임). 수익률 칸은 그 날짜가 오면 채워지고, 아직이면 빈칸
      metrics/forward_summary.md   판단별 n·평균·오른 비율, 단순 보유(같은 자산)·VOO 대비
규칙
- 표본 밖 = 가격 기준일이 FORWARD_START 이후인 판단. 과거 백테스트(label_context.py, 2025-01~2026-09-25)와 겹치지 않게 한다.
- 한 번 기록한 판단(label·close)은 고치지 않는다. 가격이 나중에 수정돼 다시 계산한 판단이 달라지면 요약에 "판단 변동"으로 센다.
- n일 뒤 = 그 자산의 n번째 다음 행(주식·ETF는 그 시장 거래일, 크립토는 UTC 일봉 = 달력일).
- VOO 대비 = 같은 기간(판단일 → 그 자산의 n일 뒤 날짜) VOO 수익률. 날짜가 VOO 거래일이 아니면 그 날 또는 그 전 마지막 VOO 종가를 쓴다.
"""
import csv
import importlib.util
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "data" / "history" / "history.csv"
OUT_CSV = ROOT / "metrics" / "forward_labels.csv"
OUT_MD = ROOT / "metrics" / "forward_summary.md"
FORWARD_START = "2026-09-26"   # 첫 정규 실행일. 이 날짜 이후 가격 기준일의 판단만 표본 밖으로 본다
HORIZONS = (5, 20, 60)
LABELS = ("관심", "관망", "비중 축소")
EARLY_N = 30                    # 이보다 작으면 "초기"로 굵게 표시

_spec = importlib.util.spec_from_file_location("backfill_history", ROOT / "scripts" / "backfill_history.py")
assert _spec and _spec.loader
backfill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(backfill)
compute = backfill.compute     # 판단 규칙 식은 이 함수 하나만 쓴다


def load_history():
    by = {}
    for r in csv.DictReader(open(HIST)):
        by.setdefault(r["asset"], []).append(r)
    for rows in by.values():
        rows.sort(key=lambda r: r["date"])
    return by


def recompute(by):
    """compute()로 다시 계산한 판단과 history.csv의 label 대조. 앞부분(2025-01 이전 가격이 없어 이동평균 기준이 달라지는 행)은 비교에서 뺀다."""
    out, checked, same = {}, 0, 0
    for asset, rows in by.items():
        market = rows[0]["market"]
        calc = compute([{"date": r["date"], "open": float(r["open"] or r["close"]), "high": float(r["high"]),
                         "low": float(r["low"]), "close": float(r["close"]), "volume": r["volume"]} for r in rows], market)
        out[asset] = calc
        for r, c in zip(rows, calc):
            if r["label"] and c["label"] and r["basis"] == c["basis"]:
                checked += 1
                same += r["label"] == c["label"]
    return out, checked, same


def ret(a, b):
    return (b / a - 1) * 100


def voo_close_on_or_before(voo, d):
    best = None
    for r in voo:
        if r["date"] <= d:
            best = r
        else:
            break
    return best


def fmt(x, nd=2, sign=True):
    return "" if x is None else (f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}")


def main():
    by = load_history()
    calc, checked, same = recompute(by)
    voo = calc["VOO"]
    last_price = {a: rows[-1]["date"] for a, rows in calc.items()}

    # 기존 기록(동결)
    kept = {}
    if OUT_CSV.exists():
        for r in csv.DictReader(open(OUT_CSV)):
            kept[(r["date"], r["asset"])] = r

    rows_out, drift = [], []
    for asset, rows in sorted(calc.items()):
        for i, r in enumerate(rows):
            if r["date"] < FORWARD_START or r["label"] is None:
                continue
            key = (r["date"], asset)
            label, close = r["label"], r["close"]
            if key in kept:  # 이미 기록한 판단은 그대로 둔다
                if kept[key]["label"] != label:
                    drift.append((key, kept[key]["label"], label))
                label, close = kept[key]["label"], float(kept[key]["close"])
            rec = {"date": r["date"], "asset": asset, "market": by[asset][0]["market"], "label": label,
                   "basis": r["basis"], "close": round(close, 6)}
            for n in HORIZONS:
                j = i + n
                if j < len(rows):
                    tgt = rows[j]
                    v0, v1 = voo_close_on_or_before(voo, r["date"]), voo_close_on_or_before(voo, tgt["date"])
                    rec[f"date_{n}"] = tgt["date"]
                    rec[f"ret_{n}"] = round(ret(close, tgt["close"]), 4)
                    rec[f"voo_{n}"] = round(ret(v0["close"], v1["close"]), 4) if v0 and v1 else ""
                else:
                    rec[f"date_{n}"] = rec[f"ret_{n}"] = rec[f"voo_{n}"] = ""
            rows_out.append(rec)
    # 이전에 기록했는데 가격 이력에서 사라진 행도 남긴다(삭제하지 않음)
    have = {(r["date"], r["asset"]) for r in rows_out}
    for key, r in kept.items():
        if key not in have:
            rows_out.append(r)
    rows_out.sort(key=lambda r: (r["date"], r["asset"]))

    cols = ["date", "asset", "market", "label", "basis", "close"] + [f"{p}_{n}" for n in HORIZONS for p in ("date", "ret", "voo")]
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows_out:
            w.writerow({k: r.get(k, "") for k in cols})

    # ---- 요약 ----
    def stats(vals):
        vals = [float(v) for v in vals if v not in ("", None)]
        if not vals:
            return None
        return dict(n=len(vals), mean=statistics.fmean(vals), up=sum(v > 0 for v in vals) / len(vals) * 100)

    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    try:
        g = json.loads((HIST.parent / "meta.json").read_text())["generated_at"]
        hist_generated = datetime.fromisoformat(g).astimezone().strftime("%Y-%m-%d %H:%M %Z") + " (data/history/meta.json)"
    except Exception:
        hist_generated = "확인 못 함(meta.json 없음)"
    L = [f"# 표본 밖 성과 추적 (판단 규칙)", "",
         f"- 생성: {now} · `python3 scripts/forward_track.py` · 입력 `data/history/history.csv`",
         f"- 가격 이력 갱신(`scripts/backfill_history.py` 실행) 시각: {hist_generated}",
         f"- 가격 이력 마지막 날짜: " + ", ".join(f"{a} {d}" for a, d in sorted(last_price.items())),
         f"- 표본 밖 시작: 가격 기준일 {FORWARD_START} 이후 (과거 백테스트 구간 2025-01-01~2026-09-25와 겹치지 않음)",
         f"- 판단 식 재계산 대조: `backfill_history.compute()`로 다시 계산한 판단이 history.csv와 {same}/{checked}행 일치"
         + ("" if same == checked else " — **불일치 있음, 확인 필요**"),
         f"- 판단 변동(기록 뒤 가격 수정으로 다시 계산한 판단이 달라진 행): {len(drift)}건", ""]
    n_total = len(rows_out)
    by_label = {lb: [r for r in rows_out if r["label"] == lb] for lb in LABELS}
    L += [f"## 기록 현황", "",
          f"표본 밖 판단 {n_total}행 (" + ", ".join(f"{lb} {len(v)}" for lb, v in by_label.items()) + ")", ""]
    if n_total:
        L += ["| 날짜 | 자산 | 판단 | 기준 | 종가 |", "|---|---|---|---|---|"]
        L += [f"| {r['date']} | {r['asset']} | {r['label']} | {r['basis']} | {float(r['close']):,.2f} |" for r in rows_out[-30:]]
        if n_total > 30:
            L.append(f"| … | 앞 {n_total - 30}행 생략(`metrics/forward_labels.csv`) | | | |")
        L.append("")
    L += ["## 판단별 성과", ""]
    any_ret = False
    for n in HORIZONS:
        L += [f"### {n}일 뒤", "", "| 판단 | n | 평균 수익률 | 오른 비율 | 같은 기간 VOO 평균 | 판단 − VOO |", "|---|---|---|---|---|---|"]
        for lb in LABELS + ("전체(단순 보유)",):
            src = rows_out if lb.startswith("전체") else by_label[lb]
            s = stats(r[f"ret_{n}"] for r in src)
            v = stats(r[f"voo_{n}"] for r in src if r[f"ret_{n}"] not in ("", None))
            if not s:
                L.append(f"| {lb} | 0 | | | | |")
                continue
            any_ret = True
            early = f"**초기, n={s['n']}**" if s["n"] < EARLY_N else str(s["n"])
            L.append(f"| {lb} | {early} | {fmt(s['mean'])}% | {s['up']:.0f}% | {fmt(v['mean']) if v else ''}% | "
                     f"{fmt(s['mean'] - v['mean']) if v else ''}%p |")
        L.append("")
    if not any_ret:
        first = min((r["date"] for r in rows_out), default=None)
        L += [f"**아직 n일 뒤 가격이 생긴 판단이 없습니다.** 5일 뒤 수익률은 첫 표본 밖 판단({first or '없음'})에서 "
              "그 자산 기준 5거래일(크립토 5일)이 지나야 채워집니다. 매번 이 스크립트를 다시 돌리면 쌓입니다.", ""]
    L += ["## 읽는 법과 한계", "",
          "- `전체(단순 보유)`는 판단과 상관없이 표본 밖 모든 날에 그 자산을 샀다고 볼 때의 평균이다. 판단이 쓸모 있으려면 "
          "`관심`이 이것보다 높고 `비중 축소`가 낮아야 한다.",
          "- 같은 자산의 이웃한 날 판단은 기간이 겹쳐 서로 독립이 아니다. n이 커도 실제 정보량은 그보다 작다.",
          f"- n이 {EARLY_N} 미만이면 **초기**로 표시한다. 이 구간의 평균으로 규칙의 좋고 나쁨을 판단하지 않는다.",
          "- 과거 구간 참고값은 `scripts/label_context.py`(CLAUDE.md 이슈 #17)의 표본 안 결과를 본다.", ""]
    OUT_MD.write_text("\n".join(L))
    print(f"forward rows {n_total} ({', '.join(f'{lb} {len(v)}' for lb, v in by_label.items())}); "
          f"recompute {same}/{checked}; drift {len(drift)}")


if __name__ == "__main__":
    main()

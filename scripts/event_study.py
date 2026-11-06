"""이벤트 스터디: Events DB 스냅숏의 실적·FOMC·CPI·고용 이벤트 뒤 D+1·D+5 반응을 종류별·자산별로 요약한다.

Notion은 이 스크립트가 읽지 않는다. 세션이 view 모드로 읽어 metrics/events_snapshot.jsonl에 저장한 것만 읽는다
(SQL·rows 모드는 워크스페이스 한도, CLAUDE.md 이슈 #15·#18).

실행: python3 scripts/event_study.py
입력: metrics/events_snapshot.jsonl(+ .meta.json), data/history/history.csv
출력: metrics/events_study.csv   이벤트 × 자산 한 줄(DB 값, 가격 이력으로 다시 계산한 값, 차이)
      metrics/events_summary.md  요약
계산 규칙(routines/_event.md 5단계와 같음)
- 기준가: 장 전·장 중·미정 발표 = 발표일 직전 거래일 종가, 장 마감 후 = 발표일 종가.
- D+n 종가 = 기준가 날짜 다음 n번째 거래일(그 자산의 시장) 종가. 수익률(%) = (D+n ÷ 기준 − 1) × 100.
- 초과(%p) = 자산 수익률 − 같은 기준가 날짜·같은 n의 기준 지수 수익률. 미국 = VOO. 국내 = KOSPI인데
  history.csv에 KOSPI가 없어 다시 계산하지 못한다 → 국내 초과는 DB 값만 쓴다(표에 "DB"로 표시).
- 거시 이벤트: 미국 자산 10개(VOO·QQQM·SMH·TSLA·GOOGL·NVDA·AAPL·SpaceX·BTC·ETH)의 반응을 가격 이력으로 계산한다.
  DB 속성에는 VOO 값만 있으므로 DB 대조는 VOO만 한다. 크립토는 UTC 일봉: 기준 = 발표일 전날 UTC 일봉(미국 발표 시각
  08:30·14:00 ET는 모두 UTC 발표일 중간), D+n = 그 n일 뒤 일봉. 크립토는 거래일 달력이 달라 초과를 계산하지 않는다.
"""
import csv
import json
import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "metrics" / "events_snapshot.jsonl"
SNAP_META = ROOT / "metrics" / "events_snapshot.meta.json"
HIST = ROOT / "data" / "history" / "history.csv"
OUT_CSV = ROOT / "metrics" / "events_study.csv"
OUT_MD = ROOT / "metrics" / "events_summary.md"
MACRO_ASSETS = ["VOO", "QQQM", "SMH", "TSLA", "GOOGL", "NVDA", "AAPL", "SpaceX", "BTC", "ETH"]
MATCH_TOL = 0.011  # DB는 소수 둘째 자리 반올림 → 0.01 이내면 일치


def load_history():
    by = {}
    for r in csv.DictReader(open(HIST)):
        by.setdefault(r["asset"], []).append((r["date"], float(r["close"]), float(r["ret"]) if r["ret"] else None))
    for v in by.values():
        v.sort()
    return by


def base_index(series, day, timing, crypto=False):
    """기준가 행 번호. 크립토는 발표일 전날 UTC 일봉."""
    dates = [d for d, _, _ in series]
    if crypto:
        target = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
        return dates.index(target) if target in dates else None
    if timing == "장 마감 후":
        return dates.index(day) if day in dates else None
    prev = [i for i, d in enumerate(dates) if d < day]
    return prev[-1] if prev else None


def reaction(series, i, n):
    if i is None or i + n >= len(series):
        return None
    return (series[i + n][1] / series[i][1] - 1) * 100


def st(vals):
    v = [x for x in vals if x is not None]
    if not v:
        return None
    return {"n": len(v), "mean": statistics.fmean(v), "median": statistics.median(v),
            "up": sum(x > 0 for x in v) / len(v) * 100, "min": min(v), "max": max(v)}


def f2(x, sign=True):
    return "" if x is None else (f"{x:+.2f}" if sign else f"{x:.2f}")


def main():
    events = [json.loads(line) for line in open(SNAP)]
    meta = json.loads(SNAP_META.read_text()) if SNAP_META.exists() else {}
    hist = load_history()
    done = [e for e in events if e["상태"] == "측정 완료"]
    rows = []  # 이벤트 × 자산

    for e in done:
        kind, day, timing = e["종류"], e["일자"], e["발표 시점"]
        if kind == "실적":
            a = e["자산"]
            s = hist.get(a)
            i = base_index(s, day, timing) if s else None
            r1, r5 = reaction(s, i, 1) if s else None, reaction(s, i, 5) if s else None
            if e["시장"] == "US":
                v = hist["VOO"]
                iv = base_index(v, day, timing)
                # 기준가 날짜를 자산 쪽과 맞춘다(같은 미국 거래일 달력)
                x1 = r1 - reaction(v, iv, 1) if r1 is not None and reaction(v, iv, 1) is not None else None
                x5 = r5 - reaction(v, iv, 5) if r5 is not None and reaction(v, iv, 5) is not None else None
                xsrc = "재계산(VOO)"
            else:
                x1, x5, xsrc = e["D+1 초과(%p)"], e["D+5 초과(%p)"], "DB(KOSPI, 재계산 불가)"
            rows.append(dict(title=e["제목"], kind=kind, market=e["시장"], event_date=day, timing=timing, asset=a,
                             base_date=s[i][0] if i is not None else "", base_close=s[i][1] if i is not None else None,
                             db_base_date=e["기준가 날짜"], db_base_close=e["기준 종가"],
                             r1=r1, r5=r5, db_r1=e["D+1 수익률(%)"], db_r5=e["D+5 수익률(%)"],
                             x1=x1, x5=x5, db_x1=e["D+1 초과(%p)"], db_x5=e["D+5 초과(%p)"], x_source=xsrc, url=e["url"]))
        else:  # 거시: 자산 10개
            v = hist["VOO"]
            iv = base_index(v, day, timing)
            v1, v5 = reaction(v, iv, 1), reaction(v, iv, 5)
            for a in MACRO_ASSETS:
                s = hist.get(a)
                crypto = a in ("BTC", "ETH")
                i = base_index(s, day, timing, crypto) if s else None
                r1, r5 = reaction(s, i, 1) if s else None, reaction(s, i, 5) if s else None
                x1 = r1 - v1 if (not crypto and a != "VOO" and r1 is not None and v1 is not None) else None
                x5 = r5 - v5 if (not crypto and a != "VOO" and r5 is not None and v5 is not None) else None
                is_voo = a == "VOO"
                rows.append(dict(title=e["제목"], kind=kind, market="US", event_date=day, timing=timing, asset=a,
                                 base_date=s[i][0] if i is not None else "", base_close=s[i][1] if i is not None else None,
                                 db_base_date=e["기준가 날짜"] if is_voo else "", db_base_close=e["기준 종가"] if is_voo else None,
                                 r1=r1, r5=r5, db_r1=e["D+1 수익률(%)"] if is_voo else None, db_r5=e["D+5 수익률(%)"] if is_voo else None,
                                 x1=x1, x5=x5, db_x1=None, db_x5=None,
                                 x_source="재계산(VOO)" if (x1 is not None) else "", url=e["url"]))

    # DB 대조
    checks, mism = 0, []
    for r in rows:
        for k in ("r1", "r5", "x1", "x5"):
            db = r[f"db_{k}"]
            if db is None or r[k] is None or (k.startswith("x") and r["x_source"].startswith("DB")):
                continue
            checks += 1
            if abs(r[k] - db) > MATCH_TOL:
                mism.append((r["title"], r["asset"], k, round(r[k], 2), db))
        if r["db_base_close"] is not None and r["base_close"] is not None:
            checks += 1
            if abs(r["base_close"] / r["db_base_close"] - 1) > 0.0001:  # DB는 소수 둘째 자리(국내는 원 단위)
                mism.append((r["title"], r["asset"], "기준 종가", round(r["base_close"], 2), r["db_base_close"]))
        if r["db_base_date"] and r["base_date"] and r["db_base_date"] != r["base_date"]:
            mism.append((r["title"], r["asset"], "기준가 날짜", r["base_date"], r["db_base_date"]))
        r["match"] = ""
    mism_keys = {(t, a) for t, a, *_ in mism}
    for r in rows:
        if r["db_r1"] is not None:
            r["match"] = "불일치" if (r["title"], r["asset"]) in mism_keys else "일치"

    cols = ["title", "kind", "market", "event_date", "timing", "asset", "base_date", "base_close", "db_base_date", "db_base_close",
            "r1", "db_r1", "r5", "db_r5", "x1", "db_x1", "x5", "db_x5", "x_source", "match", "url"]
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(r[k], 4) if isinstance(r[k], float) else r[k]) for k in cols})

    # 평소 하루 움직임(절댓값 평균): 이벤트 반응일을 뺀 모든 날
    event_days = {(r["asset"], r["base_date"]) for r in rows if r["base_date"]}
    def typical_abs(a):
        s = hist[a]
        skip = {s[k + 1][0] for k, (d, _, _) in enumerate(s[:-1]) if (a, d) in event_days}
        v = [abs(x) for d, _, x in s if x is not None and d not in skip]
        return statistics.fmean(v) if v else None

    # ---- 요약 ----
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    earn = [r for r in rows if r["kind"] == "실적"]
    macro = [r for r in rows if r["kind"] != "실적"]
    n_earn = {a: sum(r["asset"] == a for r in earn) for a in sorted({r["asset"] for r in earn})}
    n_macro = {k: sum(r["kind"] == k and r["asset"] == "VOO" for r in macro) for k in ("FOMC", "CPI", "고용")}
    n_macro_events = sum(n_macro.values())
    L = ["# 이벤트 스터디 (실적·FOMC·CPI·고용)", "",
         f"- 생성: {now} · `python3 scripts/event_study.py`",
         f"- 입력: `metrics/events_snapshot.jsonl` ({meta.get('read_at', '조회 시각 미상')} view 모드 조회, {len(events)}행 중 `측정 완료` {len(done)}행) · `data/history/history.csv`",
         f"- DB 값과 가격 이력 재계산 대조: {checks}개 값 중 {checks - sum(1 for m in mism if m[2] != '기준가 날짜')}개 일치(수익률 허용 오차 {MATCH_TOL:.3f}%p, 기준 종가 0.01%)"
         + (f", 기준가 날짜 불일치 {sum(1 for m in mism if m[2] == '기준가 날짜')}건" if any(m[2] == '기준가 날짜' for m in mism) else ""),
         f"- **표본이 작습니다.** 자산별 실적 {min(n_earn.values())}~{max(n_earn.values())}회"
         + (f"(3회 미만: {', '.join(f'{a} {n}회' for a, n in n_earn.items() if n < 3)})" if min(n_earn.values()) < 3 else "")
         + f", 거시는 종류별 {'·'.join(f'{k} {v}' for k, v in n_macro.items())}회입니다. 아래 숫자는 지금까지의 반응 기록이며 앞으로의 반응을 예측하지 않습니다.", ""]
    if mism:
        L += ["### DB와 다른 값", "", "| 이벤트 | 자산 | 항목 | 재계산 | DB |", "|---|---|---|---|---|"]
        L += [f"| {t} | {a} | {k} | {x} | {y} |" for t, a, k, x, y in mism] + [""]

    L += ["## 1. 실적 발표 반응 — 자산별", "",
          "| 자산 | 시장 | n | D+1 평균 | D+1 중앙값 | D+1 오른 비율 | D+5 평균 | D+5 오른 비율 | D+1 초과 평균 | D+5 초과 평균 | 실적일 |D+1| ÷ 평소 |하루| |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for a in sorted({r["asset"] for r in earn}, key=lambda a: (next(r["market"] for r in earn if r["asset"] == a), a)):
        g = [r for r in earn if r["asset"] == a]
        s1, s5, sx1, sx5 = st(r["r1"] for r in g), st(r["r5"] for r in g), st(r["x1"] for r in g), st(r["x5"] for r in g)
        ab = st(abs(r["r1"]) for r in g if r["r1"] is not None)
        ty = typical_abs(a)
        ratio = f"{ab['mean'] / ty:.1f}배 ({ab['mean']:.2f} ÷ {ty:.2f})" if ab and ty else ""
        L.append(f"| {a} | {g[0]['market']} | {len(g)} | {f2(s1['mean'])}% | {f2(s1['median'])}% | {s1['up']:.0f}% | "
                 f"{f2(s5['mean']) if s5 else ''}% | {s5['up'] if s5 else 0:.0f}% | {f2(sx1['mean']) if sx1 else ''}%p | "
                 f"{f2(sx5['mean']) if sx5 else ''}%p | {ratio} |")
    L += ["", "- 초과: 미국 = VOO 대비(가격 이력으로 재계산), 국내 = KOSPI 대비(DB 값, KOSPI 가격 이력이 없어 재계산 못 함).",
          "- `실적일 |D+1| ÷ 평소 |하루|` = 실적 뒤 첫날 움직임 크기(절댓값 평균)를 그 자산의 평소 하루 움직임 크기(이벤트 반응일을 뺀 "
          "2025-01~ 일간 수익률 절댓값 평균)로 나눈 값. 방향이 아니라 **크기**를 본다.", ""]

    L += ["## 2. 실적 발표 반응 — 시장별 합산", "", "| 시장 | n | D+1 평균 | D+1 오른 비율 | D+5 평균 | D+5 오른 비율 | D+1 초과 평균 | D+1 초과 오른 비율 | |D+1| 평균 |", "|---|---|---|---|---|---|---|---|---|"]
    for m in ("US", "KR"):
        g = [r for r in earn if r["market"] == m]
        s1, s5, sx1, ab = st(r["r1"] for r in g), st(r["r5"] for r in g), st(r["x1"] for r in g), st(abs(r["r1"]) for r in g if r["r1"] is not None)
        L.append(f"| {m} | {len(g)} | {f2(s1['mean'])}% | {s1['up']:.0f}% | {f2(s5['mean'])}% | {s5['up']:.0f}% | "
                 f"{f2(sx1['mean'])}%p | {sx1['up']:.0f}% | {ab['mean']:.2f}% |")
    L.append("")

    L += ["## 3. 거시 이벤트 반응 — 종류별 VOO", "", "| 종류 | n | 이벤트 | VOO D+1 | VOO D+5 | D+1 평균 | D+5 평균 |", "|---|---|---|---|---|---|---|"]
    for k in ("FOMC", "CPI", "고용"):
        g = [r for r in macro if r["kind"] == k and r["asset"] == "VOO"]
        if not g:
            continue
        s1, s5 = st(r["r1"] for r in g), st(r["r5"] for r in g)
        L.append(f"| {k} | {len(g)} | " + ", ".join(r["event_date"] for r in g) + " | "
                 + " / ".join(f2(r["r1"]) for r in g) + " | " + " / ".join(f2(r["r5"]) for r in g)
                 + f" | {f2(s1['mean'])}% | {f2(s5['mean'])}% |")
    L += ["", f"## 4. 거시 이벤트 반응 — 자산별({n_macro_events}개 이벤트 합산)", "",
          "| 자산 | n | D+1 평균 | D+1 오른 비율 | D+5 평균 | D+1 VOO 대비 평균 | 거시일 |D+1| ÷ 평소 |하루| |", "|---|---|---|---|---|---|---|"]
    for a in MACRO_ASSETS:
        g = [r for r in macro if r["asset"] == a and r["r1"] is not None]
        if not g:
            continue
        s1, s5, sx1 = st(r["r1"] for r in g), st(r["r5"] for r in g), st(r["x1"] for r in g)
        ab, ty = st(abs(r["r1"]) for r in g), typical_abs(a)
        L.append(f"| {a} | {len(g)} | {f2(s1['mean'])}% | {s1['up']:.0f}% | {f2(s5['mean']) if s5 else ''}% | "
                 f"{f2(sx1['mean']) + '%p' if sx1 else '—'} | {ab['mean'] / ty:.1f}배 |")
    short = [a for a in MACRO_ASSETS if 0 < sum(r["asset"] == a and r["r1"] is not None for r in macro) < n_macro_events]
    L += ["", (f"- {', '.join(short)}은 가격 이력이 없는 날(상장 전 등)의 이벤트가 빠져 n이 {n_macro_events}보다 작다. " if short else
               f"- 모든 자산이 거시 이벤트 {n_macro_events}개를 다 포함한다(SpaceX 상장 2026-06-12 이후 이벤트만 있음). ")
          + "크립토는 UTC 일봉 기준이며 VOO 대비를 계산하지 않는다.", ""]

    L += ["## 읽는 법과 한계", "",
          "- 이벤트 결과가 가격 움직임의 원인이라고 단정하지 않는다. 같은 날 다른 뉴스가 섞인다.",
          "- 같은 날 발표한 이벤트(예: 2026-07-22 GOOGL·TSLA, 2026-07-29 FOMC·SK하이닉스)는 서로 독립이 아니다.",
          "- 국내 실적 행 일부는 `검증 = 대기`(검증 담당이 아직 다시 계산하지 않음)다. 원자료 대조 결과는 `metrics/events_study.csv`의 `match` 칸.",
          "- 스냅숏은 조회 시점의 DB다. DB가 바뀌면 view 모드로 다시 읽어 스냅숏을 새로 만든 뒤 이 스크립트를 다시 돌린다.", ""]
    OUT_MD.write_text("\n".join(L))
    print(f"events {len(done)} measured; rows {len(rows)}; checks {checks}; mismatches {len(mism)}")
    for m in mism:
        print("  MISMATCH", m)


if __name__ == "__main__":
    main()

"""판단 규칙(관심·관망·비중 축소)이 기준선보다 나은지 정직하게 잰다.

입력: data/history/history.csv (backfill_history.py가 만든 일봉 + 그날의 판단)
출력: metrics/signal_eval.json, metrics/signal_eval.md

두 가지를 본다.
1. 규칙을 포지션으로 쓴 전략 vs 단순 보유
   - 그날 종가로 판단 → 다음 날 수익률에 적용(미래 정보 없음)
   - 비중: 관심 100%, 관망 50%, 비중 축소 0%(현금, 이자 0)
   - 거래 비용 0(유리한 가정). 수익률·최대 낙폭·연 변동성·시장 참여율
2. 판단 뒤 N거래일 수익률을 겹치지 않는 창으로만 표본 추출
   - 판단별 평균 − 같은 창들의 전체 평균 = 판단의 "정보량"
   - 부트스트랩 90% 신뢰구간(재표본 2000회, 시드 고정)
"""
import csv, json, math, random, statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "data" / "history" / "history.csv"
OUT = ROOT / "metrics"
OUT.mkdir(exist_ok=True)

WEIGHT = {"관심": 1.0, "관망": 0.5, "비중 축소": 0.0}
LABELS = ("관심", "관망", "비중 축소")
HORIZONS = (20, 60)
ORDER = ["TSLA", "GOOGL", "NVDA", "AAPL", "VOO", "SMH", "QQQM", "BTC", "ETH",
         "삼성전자", "SK하이닉스", "현대차", "두산에너빌리티"]  # SpaceX는 73일뿐이라 제외
SEED, B = 20260927, 2000

by = defaultdict(list)
for r in csv.DictReader(open(H)):
    r["close"] = float(r["close"])
    by[r["asset"]].append(r)


def path_stats(rets, ann):
    eq, peak, mdd = 1.0, 1.0, 0.0
    for x in rets:
        eq *= 1 + x
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
    vol = statistics.stdev(rets) * math.sqrt(ann) if len(rets) > 2 else None
    return {"total": (eq - 1) * 100, "mdd": mdd * 100, "vol": vol * 100 if vol is not None else None}


def strategy(rs):
    ann = 365 if rs[0]["market"] == "CRYPTO" else 252
    hold, strat, w_used = [], [], []
    for i in range(1, len(rs)):
        prev = rs[i - 1]
        if not prev["label"]:
            continue
        r = rs[i]["close"] / prev["close"] - 1
        w = WEIGHT[prev["label"]]
        hold.append(r)
        strat.append(w * r)
        w_used.append(w)
    return {
        "from": rs[0]["date"], "to": rs[-1]["date"], "days": len(hold),
        "hold": path_stats(hold, ann), "rule": path_stats(strat, ann),
        "exposure": statistics.mean(w_used) * 100,
    }


def boot_ci(xs, rng):
    if len(xs) < 3:
        return None
    ms = sorted(statistics.mean(rng.choices(xs, k=len(xs))) for _ in range(B))
    return [ms[int(B * 0.05)], ms[int(B * 0.95)]]


def nonoverlap(rs, h, rng):
    """offset 0부터 h일 간격으로 판단일을 뽑아 겹치지 않는 h일 뒤 수익률."""
    per, allx = defaultdict(list), []
    i = 0
    while i + h < len(rs):
        if rs[i]["label"]:
            f = (rs[i + h]["close"] / rs[i]["close"] - 1) * 100
            per[rs[i]["label"]].append(f)
            allx.append(f)
        i += h
    base = statistics.mean(allx) if allx else None
    res = {"n_all": len(allx), "base_mean": base}
    for k in LABELS:
        xs = per.get(k, [])
        res[k] = {"n": len(xs), "mean": statistics.mean(xs) if xs else None,
                  "edge": (statistics.mean(xs) - base) if xs and base is not None else None,
                  "ci90": boot_ci(xs, rng)}
    return res


rng = random.Random(SEED)
result = {"method": (__doc__ or "").strip().splitlines()[0], "weights": WEIGHT, "seed": SEED, "bootstrap": B,
          "assets": {}, "pooled": {}}
pooled = {h: defaultdict(list) for h in HORIZONS}
pooled_base = {h: [] for h in HORIZONS}
for a in ORDER:
    rs = by[a]
    s = strategy(rs)
    s["nonoverlap"] = {}
    for h in HORIZONS:
        no = nonoverlap(rs, h, rng)
        s["nonoverlap"][h] = no
        i = 0
        while i + h < len(rs):
            if rs[i]["label"]:
                f = (rs[i + h]["close"] / rs[i]["close"] - 1) * 100
                pooled[h][rs[i]["label"]].append(f)
                pooled_base[h].append(f)
            i += h
    result["assets"][a] = s
for h in HORIZONS:
    base = statistics.mean(pooled_base[h])
    result["pooled"][h] = {"n_all": len(pooled_base[h]), "base_mean": base}
    for k in LABELS:
        xs = pooled[h][k]
        result["pooled"][h][k] = {"n": len(xs), "mean": statistics.mean(xs), "edge": statistics.mean(xs) - base,
                                  "ci90": boot_ci(xs, rng)}

beat = [a for a, s in result["assets"].items() if s["rule"]["total"] > s["hold"]["total"]]
shallower = [a for a, s in result["assets"].items() if s["rule"]["mdd"] > s["hold"]["mdd"]]
result["summary"] = {"assets": len(ORDER), "rule_beats_hold_return": beat, "rule_smaller_drawdown": shallower}
(OUT / "signal_eval.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))

f = lambda x, d=1: "—" if x is None else f"{x:+.{d}f}"
L = ["# 판단 규칙 성과 검증", "",
     f"- 입력: `data/history/history.csv` ({min(s['from'] for s in result['assets'].values())} ~ "
     f"{max(s['to'] for s in result['assets'].values())}), 스크립트 `scripts/signal_eval.py`",
     "- 전략: 그날 종가의 판단으로 다음 날 비중을 정함(관심 100% · 관망 50% · 비중 축소 0%), 거래 비용 0, 현금 이자 0",
     "- 표본 밖 검증이 아니다. 같은 기간에 규칙을 적용한 **사후 점검**이며 표본 밖 성과는 `forward_track.py`가 따로 쌓는다", "",
     "## 1. 규칙 전략 vs 단순 보유", "",
     "| 자산 | 기간(일) | 보유 수익률 | 규칙 수익률 | 차이(%p) | 보유 MDD | 규칙 MDD | 보유 변동성 | 규칙 변동성 | 시장 참여율 |",
     "|---|---|---|---|---|---|---|---|---|---|"]
for a, s in result["assets"].items():
    L.append(f"| {a} | {s['days']} | {f(s['hold']['total'])}% | {f(s['rule']['total'])}% | "
             f"{f(s['rule']['total'] - s['hold']['total'])} | {s['hold']['mdd']:.1f}% | {s['rule']['mdd']:.1f}% | "
             f"{s['hold']['vol']:.0f}% | {s['rule']['vol']:.0f}% | {s['exposure']:.0f}% |")
L += ["", f"- 수익률에서 보유를 이긴 자산: **{len(beat)} / {len(ORDER)}** ({', '.join(beat) or '없음'})",
      f"- 최대 낙폭이 보유보다 얕았던 자산: **{len(shallower)} / {len(ORDER)}** ({', '.join(shallower) or '없음'})", ""]
for h in HORIZONS:
    p = result["pooled"][h]
    L += [f"## 2. 판단 뒤 {h}거래일 — 겹치지 않는 창, 13자산 합산", "",
          f"전체 창 {p['n_all']}개의 평균 {f(p['base_mean'])}%. `차이` = 그 판단 창의 평균 − 전체 평균. 신뢰구간은 판단별 평균의 부트스트랩 90%.", "",
          "| 판단 | n | 평균 | 차이(%p) | 평균의 90% 구간 |", "|---|---|---|---|---|"]
    for k in LABELS:
        v = p[k]
        ci = v["ci90"]
        L.append(f"| {k} | {v['n']} | {f(v['mean'])}% | {f(v['edge'])} | "
                 f"{'—' if not ci else f'{ci[0]:+.1f} ~ {ci[1]:+.1f}%'} |")
    L.append("")
p60 = result["pooled"][60]
L += ["## 읽는 법", "",
      f"- 추세 규칙이 좋은 신호라면 `관심`의 차이가 +, `비중 축소`가 − 여야 한다. 60거래일 합산에서 관심 {f(p60['관심']['edge'])}%p, "
      f"비중 축소 {f(p60['비중 축소']['edge'])}%p.",
      "- 창이 겹치지 않게 뽑아 n이 작고 신뢰구간이 넓다. 이 기간(2025~2026 강세장, 4월 급락 뒤 반등)에 한정된 결과다.",
      "- 겹치는 표본(매일 판단 뒤 60일, `insights.json`)에서는 `비중 축소` 뒤 성과가 가장 좋아 규칙이 거꾸로 작동하는 것처럼 보였다. 창을 겹치지 않게 뽑으면 판단 간 차이가 신뢰구간 안에서 거의 사라진다 — 이 기간 규칙은 **수익률 신호로는 정보가 거의 없고, 낙폭·변동성을 줄이는 위험 관리 도구**에 가깝다.",
      "- 운영 대응: 규칙을 바꾸지 않고 행마다 `과거 참고` 줄(그 자산·그 판단의 과거 성과)을 붙여 과신을 막았다(CLAUDE.md 이슈 #17)."]
(OUT / "signal_eval.md").write_text("\n".join(L) + "\n")
print("\n".join(L))

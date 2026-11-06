"""metrics/runs.jsonl(루틴 실행 장부) → metrics/ops_metrics.json, metrics/ops_metrics.md

장부는 총괄 세션이 RemoteTrigger list_runs·get_run_log(읽기 전용)로 모은다.
가드레일(휴대폰 알림 차단·연락처 규칙, 보조 에이전트 차단) 전후로 나눠 위반 건수를 센다.
"""
import json, statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
M = ROOT / "metrics"
runs = [json.loads(l) for l in open(M / "runs.jsonl")]
meta = json.load(open(M / "runs_snapshot_meta.json"))
T = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
G_PUSH = T(meta["guardrail_times_utc"]["push_block_email_rule"])
G_AGENT = T(meta["guardrail_times_utc"]["agent_block"])

fetched = [r for r in runs if r["result_status"] != "not_fetched"]
sched = [r for r in runs if r["trigger_kind"] == "scheduled"]
by = defaultdict(list)
for r in runs:
    by[r["routine"]].append(r)


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def viol(rs, key):
    known = [r for r in rs if r[key] is not None]
    return sum(1 for r in known if r[key]), len(known)


before = [r for r in fetched if T(r["created_at"]) < G_PUSH]
after = [r for r in fetched if T(r["created_at"]) >= G_PUSH]
before_a = [r for r in fetched if T(r["created_at"]) < G_AGENT]
after_a = [r for r in fetched if T(r["created_at"]) >= G_AGENT]
out = {
    "snapshot_at_utc": meta["snapshot_at_utc"],
    "runs_total": len(runs), "runs_log_read": len(fetched),
    "scheduled_runs": len(sched),
    "scheduled_success": sum(1 for r in sched if r["result_status"] == "success"),
    "start_delay_min_median": med([r["start_delay_min"] for r in sched]),
    "start_delay_min_max": max(r["start_delay_min"] for r in sched),
    "duration_s_median": med([r["duration_s"] for r in fetched]),
    "turns_median": med([r["turns"] for r in fetched]),
    "guardrails": {
        "push_before": viol(before, "push_notification_uses"), "push_after": viol(after, "push_notification_uses"),
        "company_email_before": viol(before, "company_email_in_ua"), "company_email_after": viol(after, "company_email_in_ua"),
        "agent_before": viol(before_a, "agent_tool_uses"), "agent_after": viol(after_a, "agent_tool_uses"),
    },
    "by_routine": {k: {"runs": len(v), "success": sum(1 for r in v if r["result_status"] == "success"),
                       "median_duration_s": med([r["duration_s"] for r in v if r["duration_source"] == "result_line"])}
                   for k, v in by.items()},
}
(M / "ops_metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

g = out["guardrails"]
L = ["# 운영 지표 (루틴 실행 장부)", "",
     f"- 스냅숏 {out['snapshot_at_utc']} · 실행 {out['runs_total']}회(로그 전체 확인 {out['runs_log_read']}회) · 입력 `metrics/runs.jsonl`",
     f"- 데이터가 이틀치라 **초기 수치**다. 2026-10-25에 다시 받는다.", "",
     "## 요약", "",
     f"| 지표 | 값 |", "|---|---|",
     f"| 예약 실행 성공 | {out['scheduled_success']} / {out['scheduled_runs']} |",
     f"| 예약 대비 시작 지연(중앙값·최대) | {out['start_delay_min_median']}분 · {out['start_delay_min_max']}분 |",
     f"| 실행 1회 소요(중앙값) | {out['duration_s_median'] / 60:.1f}분 ({out['turns_median']}턴) |", "",
     "## 가드레일 전후 (로그로 확인한 실행만, 위반 실행 수 / 확인 실행 수)", "",
     "| 위반 | 적용 전 | 적용 후 | 적용 시각(UTC) |", "|---|---|---|---|",
     f"| 시키지 않은 휴대폰 알림 | {g['push_before'][0]} / {g['push_before'][1]} | {g['push_after'][0]} / {g['push_after'][1]} | {meta['guardrail_times_utc']['push_block_email_rule']} |",
     f"| 외부 요청에 회사 이메일 | {g['company_email_before'][0]} / {g['company_email_before'][1]} | {g['company_email_after'][0]} / {g['company_email_after'][1]} | 같은 시각(stocknews는 셋업 교체 뒤) |",
     f"| 보조 에이전트 위임 | {g['agent_before'][0]} / {g['agent_before'][1]} | {g['agent_after'][0]} / {g['agent_after'][1]} | {meta['guardrail_times_utc']['agent_block']} |", "",
     "## 루틴별", "", "| 루틴 | 실행 | 성공 | 소요 중앙값 |", "|---|---|---|---|"]
for k, v in sorted(out["by_routine"].items()):
    d = v["median_duration_s"]
    L.append(f"| {k} | {v['runs']} | {v['success']} | {'—' if d is None else f'{d / 60:.1f}분'} |")
L += ["", "- 회사 이메일 '적용 후 0'에는 stocknews-refresh 2026-09-27 08:10 정기 실행이 빠져 있다. 옛 셋업 스크립트(연락처가 허용되지 않은 주소)로 돌았을 가능성이 높지만 요청 헤더가 로그에 남지 않아 확인하지 못했다(unknown). 그 뒤 셋업을 교체하고 프롬프트에 연락처 검사를 넣었다.",
      "- `not_fetched`(첫 등록 시험 등 7회)는 성공 수에 넣지 않았고, 소요 시간은 목록 시각 차이로만 적었다.",
      "- monthly-brief는 첫 실행이 2026-10-01이라 기록이 없다. 비용(토큰·달러)은 실행 로그에 나오지 않아 비워 두었다."]
(M / "ops_metrics.md").write_text("\n".join(L) + "\n")
print("\n".join(L))

# 검증 판정 추이 (metrics/verdicts.jsonl = Market Daily view 모드 스냅숏)
vp = M / "verdicts.jsonl"
if vp.exists():
    vs = [json.loads(l) for l in open(vp)]
    agg = defaultdict(lambda: defaultdict(int))
    for v in vs:
        day = "-".join(v["title"].split("-")[1:4])
        agg[(day, v["mode"])][v["verdict"] or "대기"] += 1
    K = ["PASS", "WARNING", "ERROR", "NEED MORE INFO", "대기"]
    V = ["# Market Daily 검증 판정 추이", "", f"- 스냅숏 {meta['snapshot_at_utc']} · 행 {len(vs)}개 · 작성일(KST, 제목 기준)·실행 방식별", "",
         "| 작성일 | 방식 | " + " | ".join(K) + " |", "|---|---|" + "---|" * len(K)]
    for (day, mode), c in sorted(agg.items()):
        V.append(f"| {day} | {mode} | " + " | ".join(str(c.get(k, 0)) for k in K) + " |")
    V += ["", "- 9/26 ERROR 4건은 수치 오류가 아니라 출처 칸 `(비공식 경로)` 표기 누락(+GOOGL 뉴스 게재일)이었다. 규칙을 고친 뒤(이슈 #12·#13) 9/27 행은 모두 PASS.",
          "- 검증 담당은 수치를 원출처에서 다시 받아 재계산한다. 현재 DB에 남은 판정 중 수치 불일치로 ERROR인 행은 없다(9/25 수동 행은 재검증 r3 뒤의 판정)."]
    (M / "verdicts.md").write_text("\n".join(V) + "\n")
    print("\n".join(V))

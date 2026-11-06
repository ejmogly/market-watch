# 이슈 분류·재발 요약

- 입력: `metrics/issues.csv` (47행 = market-watch 이슈 기록 #1~#23 + agent-office 이슈 표 #1~#24)
- 집계 시각: 2026-09-27 21:51 KST. 집계는 아래 "재현" 명령 하나로 다시 낼 수 있다.
- 분류는 사람이 행마다 한 것이다. 근거는 행의 `rule_location`·`recurrence_evidence`에 적었다.
  사용한 자료는 두 `CLAUDE.md`와 아래 파일들이다.
  - `agent-office/output/warnings.md`, `agent-office/output/verify_20260923_r5.md`
  - `market-watch/output/verify_2026-09-25_r3.md`, `market-watch/output/review_2026-09-26.md`
  - Notion Market Daily 검증 메모 22행(view 모드로 읽기만, 2026-09-27 조회)
- `issues.csv`에는 지시서 열 11개 끝에 `rule_lag` 열 하나를 더 붙였다. 규칙 반영까지 걸린 시간을 재현할 수 있게 하려는 것이다.

## 유형별

| category | 건수 | agent-office | market-watch | 재발 Y | 재발 N | unknown |
|---|---|---|---|---|---|---|
| format (태그·표기) | 17 | 12 | 5 | 5 | 10 | 2 |
| data-source (출처·누락·경로 차이) | 12 | 7 | 5 | 4 | 6 | 2 |
| platform (Notion·네트워크 한도) | 7 | 2 | 5 | 2 | 1 | 4 |
| calc-rule (식·반올림) | 5 | 1 | 4 | 0 | 3 | 2 |
| orchestration (순서·에이전트·한도) | 3 | 1 | 2 | 1 | 0 | 2 |
| rule-ambiguity | 2 | 1 | 1 | 1 | 0 | 1 |
| guardrail (보안·알림·이메일) | 1 | 0 | 1 | 0 | 0 | 1 |
| **합계** | **47** | **24** | **23** | **13** | **20** | **14** |

## 심각도별

| severity | 건수 | 재발 Y | 발견자 |
|---|---|---|---|
| high (사실이 틀린 채 게시되거나 외부로 샌 것) | 7 | 0 | verifier 4 · independent-review 1 · unknown 2 |
| medium | 22 | 8 | |
| low | 18 | 5 | |

## 발견자별 — 검증 담당 vs 사람

| detected_by | 건수 | agent-office | market-watch |
|---|---|---|---|
| verifier | 18 | 9 | 9 |
| lead (메인 세션) | 13 | 13 | 0 |
| user | 1 | 1 | 0 |
| independent-review | 1 | 0 | 1 |
| unknown | 14 | 1 | 13 |

- 발견자를 확인한 33건 가운데 **검증 담당 18건(55%)**, 사람 15건(45%)이다. 사람 15건은 lead 13, user 1, independent-review 1이다.
- 두 프로젝트의 양상이 다르다.
  - agent-office(23건 확인)는 검증 담당 9건(39%)이다. 수집·초안 단계에서 메인 세션이 먼저 찾은 이슈(#1~#10, #19~#21)가 많다.
  - market-watch(10건 확인)는 검증 담당 9건(90%)이다. 다만 market-watch 23건 중 13건은 발견자 기록이 없어 unknown이다. 이 비율은 **확인된 10건에서만** 나온 값이다.
- agent-office의 `verifier`는 에이전트 팀의 검증 담당(stock-verifier)이다. market-watch의 `verifier`는 루틴 검증 담당(market-verifier)이다.

## 규칙 반영까지 걸린 시간

| rule_lag | 건수 |
|---|---|
| same-day | 45 |
| next-day | 2 (agent-office #3, #7) |

- market-watch는 이슈와 규칙이 같은 행에 같은 날짜로 기록돼 있다. 그래서 23건 모두 same-day로 셌다.
  발생 시각과 반영 시각을 따로 남기지 않았으므로, 실제보다 빠르게 잡혔을 수 있다.
- agent-office는 코드나 지침 파일에 처음 반영된 날로 셌다. #3·#7은 9/24 밤에 발견해 9/25에 지침에 넣었다.

## 재발

- 재발 여부를 판단할 자료가 있는 33건 가운데 **13건(39%)이 재발했다**. agent-office는 22건 중 10건, market-watch는 11건 중 3건이다.
- 14건은 unknown이다. 규칙을 만든 뒤 해당 유형이 다시 실행된 자료가 없다. 예를 들어 주식·ETF 예약 행은 9/26 재등록 뒤 아직 없고, 국내 예약 행은 9/28부터 쌓인다.
- 재발 13건 중 12건은 검증 담당이나 독립 검토의 기록에서 드러났다. 나머지 1건(market-watch #15 → #18)은 루틴 실행 오류로 드러났다. 재발을 놓치고 넘어간 기록은 없다. 다만 놓쳤다면 기록에도 없을 것이다.
- 국내 예약 실행 첫 시험(2026-09-26)에서 agent-office 규칙 4건이 재발했다: #1 외국인 소진율 날짜, #20 투자의견 풀이, #21 잘린 제목, #22 (산출) 태그. 근거는 `review_2026-09-26.md` 3-6·3-7·3-8·3-12다.
  네 규칙은 그때 이미 `routines/_kr_common.md`에 들어 있었다.
- high 7건은 재발 0건이다. 그중 4건은 unknown이라, 재발하지 않았다고 확인된 것은 3건뿐이다.

## 짧은 해석

1. 이슈의 절반 가까이(17/47)가 태그·표기 문제였다. 재발도 이 유형과 출처 유형에 몰렸다(13건 중 9건). 계산식(calc-rule) 이슈는 규칙을 고친 뒤 재발이 확인되지 않았다(판단 가능 3건 중 0건).
2. 규칙을 프롬프트에 적어도 재발은 막히지 않았다(국내 시험 4건). 재발을 드러낸 것은 규칙 자체가 아니라 대부분(12/13) 검증 담당과 독립 검토의 재계산·대조였다.
3. 이 수치는 표본이 작고(n=47, 판단 가능 33) 기간이 사흘(2026-09-24~27)이다. 발견자·반영 시각 기록이 빠진 행이 있어 비율은 추세가 아니라 현재 상태를 기록한 값이다.

## 재현

```bash
cd lab/market-watch
python3 - <<'EOF'
import csv, collections as C
rows = list(csv.DictReader(open("metrics/issues.csv")))
for key in ["category", "severity", "detected_by", "fix_type", "rule_lag"]:
    print("##", key)
    for v, _ in C.Counter(r[key] for r in rows).most_common():
        s = [r for r in rows if r[key] == v]
        print(v, len(s), sum(r["project"] == "agent-office" for r in s), sum(r["project"] == "market-watch" for r in s),
              "Y", sum(r["recurred"] == "Y" for r in s), "N", sum(r["recurred"] == "N" for r in s),
              "unknown", sum(r["recurred"] == "unknown" for r in s))
EOF
```

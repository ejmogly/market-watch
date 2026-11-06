# 검증 담당 평가 결과 (eval)

- 생성: 2026-09-28 07:42 KST · 모델 `claude-sonnet-5` · `claude -p --tools "" --safe-mode --strict-mcp-config --no-session-persistence`
- 입력: `eval/fixtures/F01~F20.md` (정상 8 · 결함 12), 정답 `eval/labels.json`, 판본 `eval/prompts/*.md`(ablation 목록 `eval/ablation.json`)
- 누적 `claude -p` 호출 96회 (상한 100회, `eval/results/calls.jsonl`)
- 재현: `python3 eval/build_fixtures.py && python3 eval/build_holdout.py && python3 eval/run_eval.py prompts && python3 eval/run_eval.py run full && python3 eval/run_eval.py run ablated && python3 eval/run_eval.py run v2 && python3 eval/run_eval.py run full --holdout && python3 eval/run_eval.py run v2 --holdout && python3 eval/run_eval.py report`

## 핵심 수치

| 판본 | 결과 파일 | 돌린 행 | 검출률(결함을 기대 심각도 이상으로) | 오탐률(정상을 WARNING 이상으로) | 심각도 일치율 | 응답 파싱 실패 |
|---|---|---|---|---|---|---|
| full | `eval/results/2026-09-27_full.jsonl` | 20 | 66.7% (8/12) | 0.0% (0/8) | 80.0% (16/20) | 0 |
| ablated | `eval/results/2026-09-27_ablated.jsonl` | 20 | 50.0% (6/12) | 25.0% (2/8) | 60.0% (12/20) | 0 |
| full_r2 | `eval/results/2026-09-27_full_r2.jsonl` | 18 | 54.5% (6/11) | 0.0% (0/7) | 72.2% (13/18) | 0 |
| v2 | `eval/results/2026-09-28_v2.jsonl` | 20 | 91.7% (11/12) | 0.0% (0/8) | 95.0% (19/20) | 0 |

- 검출률 차이(full − ablated): **+16.7%p** · 오탐률 차이: -25.0%p · 일치율 차이: +20.0%p
- 이슈 기록에서 온 결함 8건: full 62.5% (5/8) vs ablated 37.5% (3/8)
- 이슈와 무관한 대조 결함 4건(규칙을 빼도 잡혀야 정상): full 75.0% (3/4) vs ablated 75.0% (3/4)
- full 반복 일치율(1회차 vs 2회차, 두 회차 모두 있는 행): 94.4% (17/18) · 다르게 나온 행: F13(ERROR→PASS)
- 2차(2026-09-28): 검증 규칙 4개(고지·기사 제목·'쉽게 말하면' 칸·반올림 방향)를 넣은 v2 — 검출률 91.7% (11/12) (full 대비 +25.0%p) · 오탐률 0.0% (0/8) · 일치율 95.0% (19/20)
- 호출 비용 합계(claude -p 보고값): 4.99 USD
- 같은 파일에 두 번 기록된 행(마지막 기록을 씀): full:F01, full:F04 — fixture 표시 버그를 고친 뒤 다시 돌림(`notes.md`)

## 행별 결과

| id | 자산 | 결함 유형 | 이슈 # | 기대 | full | ablated | full_r2 | v2 |
|---|---|---|---|---|---|---|---|---|
| F01 | GOOGL | 뉴스 날짜를 검색 결과 날짜로 적음(원문 게재 7일 초과) | 13 | ERROR | ERROR | ERROR | 미실행 | ERROR |
| F02 | VOO | 정상 | - | PASS | PASS | PASS | PASS | PASS |
| F03 | SMH | 이동평균 수치 불일치 | - | ERROR | ERROR | ERROR | ERROR | ERROR |
| F04 | GOOGL | 정상 | - | PASS | PASS | WARNING ▲ | 미실행 | PASS |
| F05 | ETH | 고지 문구 누락 | - | ERROR | PASS ▼ | PASS ▼ | PASS ▼ | ERROR |
| F06 | QQQM | 정상 | - | PASS | PASS | PASS | PASS | PASS |
| F07 | TSLA | 출처 칸 기사 제목 축약 | 10 | WARNING | PASS ▼ | PASS ▼ | PASS ▼ | PASS ▼ |
| F08 | SpaceX | 정상 | - | PASS | PASS | ERROR ▲ | PASS | PASS |
| F09 | VOO | 손절선을 반올림 후 하단으로 계산 | 2 | ERROR | ERROR | PASS ▼ | ERROR | ERROR |
| F10 | SMH | 정상 | - | PASS | PASS | PASS | PASS | PASS |
| F11 | TSLA | 한 줄 판단 라벨 규칙 위반 | - | ERROR | ERROR | ERROR | ERROR | ERROR |
| F12 | NVDA | 정상 | - | PASS | PASS | PASS | PASS | PASS |
| F13 | NVDA | 사실 문장에 (의견) 태그 | 9 | ERROR | ERROR | ERROR | PASS ▼ | ERROR |
| F14 | ETH | '쉽게 말하면' 칸에 출처별 값 | 11 | WARNING | PASS ▼ | PASS ▼ | PASS ▼ | WARNING |
| F15 | TSLA | 정상 | - | PASS | PASS | PASS | PASS | PASS |
| F16 | QQQM | 출처 (비공식 경로) 표기 누락 | 12 | WARNING | WARNING | PASS ▼ | WARNING | WARNING |
| F17 | SMH | 차익 실현 하단 반올림 방향 오류 | 3 | ERROR | PASS ▼ | PASS ▼ | PASS ▼ | ERROR |
| F18 | BTC | 정상 | - | PASS | PASS | PASS | PASS | PASS |
| F19 | SpaceX | 200일선 없는 종목 판단 보류 | 4 | ERROR | ERROR | ERROR | ERROR | ERROR |
| F20 | BTC | 판단 섹션 밖 전망 단정 | - | ERROR | ERROR | ERROR | ERROR | ERROR |

▲ 기대보다 심하게, ▼ 기대보다 약하게 판정. 검출은 '기대 심각도 이상'이면 인정(WARNING 기대 행을 ERROR로 판정해도 검출).

## holdout — 규칙을 고친 뒤 새로 만든 8행 (과적합 점검)

1차 fixture를 보고 규칙을 고쳤으므로, 같은 fixture 점수만으로는 과적합을 가릴 수 없다. 그래서 규칙이 겨냥한 4유형을 **다른 종목·다른 모양**으로 심은 행(target)과, 이번 규칙과 무관한 유형(control), 정상 행을 새로 만들었다(`eval/build_holdout.py`).

| 판본 | 결과 파일 | 검출률 | target 4건 | control 2건 | 오탐률 | 일치율 |
|---|---|---|---|---|---|---|
| full | `eval/results/2026-09-28_full_holdout.jsonl` | 33.3% (2/6) | 25.0% (1/4) | 50.0% (1/2) | 0.0% (0/2) | 50.0% (4/8) |
| v2 | `eval/results/2026-09-28_v2_holdout.jsonl` | 66.7% (4/6) | 75.0% (3/4) | 50.0% (1/2) | 0.0% (0/2) | 75.0% (6/8) |

| id | 자산 | 구분 | 결함 유형 | 기대 | full | v2 |
|---|---|---|---|---|---|---|
| H01 | GOOGL | target | 차익 실현 상단 반올림 방향 오류(내림) | ERROR | ERROR | ERROR |
| H02 | SpaceX | normal | 정상 | PASS | PASS | PASS |
| H03 | QQQM | target | 고지 문구를 다른 문장으로 바꿈 | ERROR | WARNING ▼ | ERROR |
| H04 | VOO | control | 52주 위치 수치 불일치 | ERROR | ERROR | ERROR |
| H05 | ETH | normal | 정상 | PASS | PASS | PASS |
| H06 | NVDA | target | 출처 칸 기사 제목 말줄임 | WARNING | PASS ▼ | PASS ▼ |
| H07 | TSLA | control | 뉴스 인용 문장에 (확인) 태그 | ERROR | PASS ▼ | PASS ▼ |
| H08 | BTC | target | '쉽게 말하면' 칸에 그 행의 52주 위치 값 | WARNING | PASS ▼ | WARNING |

## ablation — ablated 판본에서 뺀 규칙 문장

- #15·18 `_common.md`: - **여러 행 읽기는 view 모드만 씁니다**(한도 없음). `notion-query-data-sources`의 SQL 모드와 rows 모드는 워크스페이스 사용 한도에 걸리므로 쓰지 않습니다. 호출 형식: `{"data": {"mode": "vie… → (삭제)
- #22 `_common.md`: - **알림 금지**: PushNotification 같은 휴대폰·앱 알림 도구는 쓰지 않습니다(설정에서도 막혀 있음). 결과는 Notion과 마지막 보고에만 남깁니다. → (삭제)
- #22 `_common.md`: - **이메일**: 외부 요청에 연락처 이메일이 필요하면(SEC EDGAR User-Agent 등) `<CONTACT_EMAIL>`만 씁니다. 허용되지 않은 도메인 주소는 절대 쓰지 않고, 이메일 주소를 지어내지 않습니다. → (삭제)
- #6 `_common.md`: 본문 문장에는 링크를 넣지 않고, 도메인 대신 매체명만 씁니다(Notion 자동 링크 방지). → `본문 문장에는 링크를 넣지 않습니다.`
- #10 `_common.md`: 기사 제목은 원문 제목 전체. → (삭제)
- #5 `_common.md`: - 같은 값을 두 출처에서 확인할 수 있으면 확인하고, 다르면 값 칸 괄호나 표 아래 메모에 둘 다 적습니다(엔드포인트와 조회 시각 포함). → (삭제)
- #12 `_common.md`: - 비공식 데이터 경로(웹사이트 내부 API)를 쓰면 출처 칸의 **그 출처 줄마다** `(비공식 경로)`를 붙입니다. Yahoo Finance의 `query1`·`query2.finance.yahoo.com`(chart, quoteSummary 등)… → `- 비공식 데이터 경로(웹사이트 내부 API)를 쓰면 출처 칸에 `(비공식 경로)`를 붙입니다.`
- #13 `_common.md`: - **뉴스 날짜**는 기사 원문 페이지에서 확인한 **최초 게재일**입니다. 검색 결과에 보이는 날짜나 수정(업데이트)일을 쓰지 않습니다. 원문에서 게재일을 확인할 수 없는 기사는 쓰지 않습니다. 최초 게재일이 기준일로부터 7일보다 오래됐으면 수정일… → (삭제)
- #7 `_common.md`: - 가격 이력 요청 사이에 간격을 두고, 429가 나면 재시도하거나 다른 출처(Nasdaq 등)로 채우고 본문에 밝힙니다. → (삭제)
- #11 `_common.md`: . "쉽게 말하면" 칸에는 풀어 쓴 설명만 → (삭제)
- #9 `_common.md`: - "그래서 어떻게 볼까" 안에서도 사실 문장("지금 가격은 구간 위", "목표가가 45% 높다")에는 (확인)/(산출)/(계산)을 붙이고, (의견)은 판단 문장에만 붙입니다. → (삭제)
- #4 `_common.md`: - 200일선이 없는 종목(종가 200개 미만): 200일선을 쓰는 항목만 200일선→50일선, 50일선→20일선으로 바꿉니다. 관심의 분할 매수 구간(20~50일선)과 차익 실현·손절 식은 그대로. 한 줄 판단 옆과 판단 근거 첫 줄에 `상장 N거래… → (삭제)
- #2 `_common.md`: 분할 매수 구간 하단의 **반올림 전 값** − 2 × ATR(14), 결과를 마지막에 한 번만 내림. → `분할 매수 구간 하단 − 2 × ATR(14).`
- #3 `_common.md`: - 반올림: 매수 구간 하단·차익 실현 하단·손절선은 내림, 매수 구간 상단·차익 실현 상단은 올림. 주식·ETF는 1달러(가격 100달러 미만이면 0.1달러), BTC 100달러, ETH 10달러 단위. → `- 반올림: 매수 구간 하단·손절선은 내림, 매수 구간 상단은 올림. 주식·ETF는 1달러(가격 100달러 미만이면 0.1달러), BTC 100달러, ETH 10달러 단위.`
- #12·13 `_verifier.md`: - 수치가 맞고 출처 칸에 `(비공식 경로)` 표기만 빠졌으면 **WARNING**입니다(출처 종류가 틀린 것은 아니므로). → (삭제)
- #12·13 `_verifier.md`: - 뉴스의 최초 게재일이 7일보다 오래됐거나 행에 적힌 날짜와 다르면 **ERROR**입니다. → (삭제)
- #12·13 `_verifier.md`: ## 판정 기준 보충 (2026-09-26 첫 정규 실행에서 정함) → (삭제)

두 판본 모두에서 뺀 것(평가 범위 밖): _common.md '과거 판단 성과 참고' 절(#17) — 과거 성과 표가 fixture에 없어 판정할 수 없음; _verifier.md '과거 참고' 줄 판정 기준(#17) — 같은 이유

## 해석 (사람이 쓴 메모, 2026-09-27)

- **규칙 효과는 결함 검출보다 오탐에서 더 크게 보였다.** 검출률 차이는 +16.7%p(2건: F09 #2 손절 반올림, F16 #12 비공식 경로)로 표본 12건의 두 건이다. 반면 ablated는 정상 8건 중 2건을 잡았는데, 그중 F08(SpaceX, 상장 72거래일)은 #4 대체 규칙이 없으니 "50일선 기준 판단"을 임의 규칙으로 보고 ERROR를 줬다. 이슈 기록이 만든 규칙이 **올바른 예외 처리를 통과시키는 역할**도 한다는 사례다.
- **이슈 무관 대조군 4건은 두 판본이 같았다(3/4).** 규칙 제거가 전반적인 판정 능력을 떨어뜨린 것이 아니라, 뺀 규칙에 해당하는 결함에서만 차이가 났다는 뜻으로 읽힌다(n이 작아 방향만).
- **두 판본 모두 놓친 결함 4건**: F05 고지 누락(ERROR), F07 출처 칸 제목 축약(#10), F14 '쉽게 말하면' 칸 값(#11), F17 차익 실현 하단 올림(#3). 넷 다 "숫자 재계산" 밖의 **형식 점검**이다. 검증 지시문의 '반드시 할 것' 5항목이 가격·지표·구간·태그·뉴스만 다루고 고지·출처 칸 제목·표 칸 내용·차익 실현 반올림 방향을 명시하지 않는다. F17은 모델이 "52주 최고 올림"을 규칙대로라고 잘못 읽었다.
- **반복 흔들림**: full 2회차에서 F13(#9, 사실 문장에 (의견))이 ERROR→PASS로 바뀌었다. 태그 점검은 '반드시 할 것' 4번에 있는데도 한 번은 건너뛰었다.
- **fixture 버그 1건을 고쳤다**: GOOGL 두 행(F01·F04)의 손절 식이 `323.9989`를 둘째 자리 `324.00`으로 표시해 식과 결과(323)가 어긋났다. full이 이를 ERROR로 잡아 정상 행 F04가 오탐처럼 보였다. 표시만 넷째 자리로 고치고 F01·F04 full을 다시 돌렸다(처음 기록도 결과 파일에 남김). 고친 표시(`342.01 − 2 × ATR 9.01 = 323.9990`)를 ablated는 입력·결과 자릿수가 맞지 않는다며 WARNING으로 봤다 — ablated F04 오탐 1건은 fixture 표기 탓도 있다.
- **검증 지시문 보완 후보**(총괄 판단): '반드시 할 것'에 ⑥ 고지 문구 ⑦ 출처 칸 기사 제목 = 원문 전체 ⑧ 지표 표 '쉽게 말하면' 칸에 수치 없음 ⑨ 차익 실현 하단 내림·상단 올림을 넣고, 이 eval로 다시 잰다.

## 2차 해석 (2026-09-28, 총괄)

- 1차에서 두 판본이 모두 놓친 4유형(고지·기사 제목·'쉽게 말하면' 칸·반올림 방향)을 검증 담당의 "반드시 할 것" 6~9번으로 넣었다(`routines/_verifier.md`, 국내는 `_kr_verifier.md` 11~13번). 1차 판본 프롬프트는 `eval/prompts/full.md`·`ablated.md`로 고정해 기준선이 바뀌지 않게 했다.
- 기존 20행: 검출률 66.7% → 91.7%, 오탐 0 → 0, 일치율 80% → 95%. 규칙이 겨냥한 4건 중 3건(고지·'쉽게 말하면'·반올림)이 새로 잡혔다.
- holdout 8행(규칙을 고친 뒤 새로 만든 행): 검출률 33.3% → 66.7%, target 4건 1 → 3, control 2건 1 → 1, 오탐 0 → 0. 기존 세트(91.7%)보다 낮은 것은 기존 세트를 보고 규칙을 고친 효과가 섞였다는 뜻이다. 일반화된 개선 폭은 holdout 쪽 수치로 읽는다.
- **기사 제목 대조는 규칙을 넣어도 두 세트 모두 놓쳤다(F07·H06).** 출처 칸의 제목과 원자료의 원문 제목을 글자 단위로 맞대는 일은 프롬프트 규칙으로는 안정적이지 않다. 이런 항목은 스크립트(문자열 비교)로 옮기는 것이 맞다 — 다음 개선 후보.
- control H07(뉴스 인용 문장에 (확인) 태그)은 두 판본 모두 놓쳤다. 기존 태그 규칙(4번)이 "사실 문장에 (의견)" 방향만 적고 있어 (보도)↔(확인) 혼동은 보지 않는다 — 두 번째 개선 후보.
- 호출: 1차 60회 + 2차 36회 = 96회(상한 100). 비용 합계는 REPORT.md 핵심 수치 참고.

## 한계

- n = 20(결함 12, 정상 8). 검출률 1건 = 8.3%p, 오탐률 1건 = 12.5%p라 차이의 신뢰구간이 넓다. 방향만 보는 수치로 읽는다.
- fixture는 실제 가격 이력·뉴스로 만들었지만 결함은 한 행에 하나만 심었다. 실제 행은 결함이 여럿 섞이고 본문이 길다.
- 도구 없이 판정하므로 이동평균·ATR은 `원자료`에 넣어 준 재계산값과 비교하는 능력만 잰다. 실제 루틴은 python으로 직접 계산한다.
- 일부 뉴스 제목·URL은 평가용으로 만든 것(F-행 GOOGL #13 사례 등, labels.json note). 원자료 블록 안에서는 서로 모순이 없게 맞췄다.
- ablated는 '이슈 기록 이전 규칙'을 문장 단위로 되돌린 근사치다. 이슈가 생긴 뒤 담당 지시문 쪽 표현이 바뀐 효과는 재지 않는다.

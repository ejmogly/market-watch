# market-watch 예약 실행 (claude.ai 루틴)

프롬프트 = 역할 파일 + 공통 규칙 → `<역할>.prompt.md`(B 방식: 규칙 전체를 프롬프트에 넣음). 규칙은 역할 파일·공통 규칙만 고치고 다시 조립한다.

## 조립 (`build.py`)
1. 규칙을 고친다: 해외는 이 폴더의 `_common.md`·`_stock.md`·`_etf.md`·`_crypto.md`·`_verifier.md`·`_brief.md`·`_event.md`, 국내는 `kr/routines/_kr_*.md`.
2. (월 1회) `python3 scripts/backfill_history.py && python3 scripts/history_insights.py && python3 scripts/label_context.py`로 과거 판단 성과 표를 갱신한다.
2-1. (월 1회, 포트폴리오 지표) 총괄이 RemoteTrigger 실행 기록을 `metrics/runs.jsonl`에 덧붙이고 Market Daily·Events를 view 모드로 다시 읽어 스냅숏(`metrics/verdicts.jsonl`, `metrics/events_snapshot.jsonl`)을 새로 만든 뒤 `python3 scripts/forward_track.py && python3 scripts/event_study.py && python3 scripts/signal_eval.py && python3 scripts/ops_metrics.py && python3 docs/build_case_study.py`를 돌린다. 다음 갱신 2026-10-25(KOSPI 가격 이력 추가 예정)
3. `python3 routines/build.py`를 실행한다 → 이 폴더에 `*.prompt.md` 9개(stock·etf·crypto·verifier·weekly·monthly·event·kr_desk·kr_verifier)가 다시 만들어지고 글자 수가 찍힌다.
4. 바뀐 `*.prompt.md`를 루틴에 다시 올려 달라고 총괄에게 요청한다(루틴 등록·수정은 총괄만).

국내 프롬프트: 원본 규칙은 `kr/routines/`(`_kr_common.md`, `_kr_desk.md`, `_kr_verifier.md`), 조립 결과(`kr_desk.prompt.md`, `kr_verifier.prompt.md`)는 이 폴더에 생긴다.

## 루틴 9개

| 루틴 | ID | cron(UTC) | KST |
|---|---|---|---|
| stock-desk | <TRIGGER_ID> | `0 22 * * 1-5` | 화~토 07:00 |
| etf-desk | <TRIGGER_ID> | `0 22 * * 1-5` | 화~토 07:00 |
| crypto-desk | <TRIGGER_ID> | `0 22 * * *` | 매일 07:00 |
| market-verifier (+일간 브리핑, 주간·월간 검증) | <TRIGGER_ID> | `40 22 * * *` | 매일 07:40 |
| kr-desk | <TRIGGER_ID> | `30 11 * * 1-5` | 평일 20:30 |
| kr-verifier | <TRIGGER_ID> | `10 12 * * 1-5` | 평일 21:10 |
| weekly-brief (+가치 지표 주간 리포트, `_value_report.md`, 모델 Opus) | <TRIGGER_ID> | `30 0 * * 6` | 토 09:30 |
| monthly-brief | <TRIGGER_ID> | `30 0 1 * *` | 매월 1일 09:30 |
| event-desk | <TRIGGER_ID> | `0 10 * * *` | 매일 19:00 |
| stocknews-refresh (Stock News 페이지 수치·차트 갱신, `routines/stocknews.prompt.md`, 환경 `stocknews` <ENV_ID>) | <TRIGGER_ID> | `10 23 * * *` | 매일 08:10 |

- 환경: `Default` (<ENV_ID>), 네트워크 Full, Notion 인증은 커넥터 우선 → API 토큰 대체. stocknews-refresh만 전용 환경 `stocknews` (<ENV_ID>, 네트워크 Full, 셋업 스크립트 = `stocknews_setup.sh` 전체)
- 2026-09-25 21:10 시험 1회(주식·ETF는 새 종가 없음으로 갱신 없음, BTC PASS · ETH WARNING) 후 같은 날 반복으로 바꿈. 2026-09-26 07:00 첫 정규 실행
- 실제 시작은 예약 시각보다 8~12분 늦음. 검증 담당은 담당들보다 40분 뒤라 겹치지 않음
- 삭제는 https://claude.ai/code/routines 에서만 가능
- 2026-09-26 13:00 KST 9개 프롬프트 재조립·재등록(AAPL 추가, view 모드, 비공식 경로·뉴스 날짜·최신 칸, Rerun 검토 7건 반영). event-desk 신규 등록 후 시험 1회
- 2026-09-26 오후: 과거 참고 줄, `[루틴]` view 전용 읽기, Team 검토 14건을 반영해 9개 모두 재등록
- 2026-09-26 21:05 event-desk·market-verifier 재등록(SEC 8-K 접수 시각으로 발표 시점 결정·자동 재측정, CLAUDE.md #20). stocknews-refresh는 전용 환경 `stocknews`로 옮겨 시험 통과
- 2026-09-26 21:45 10개 루틴 모두 재등록: PushNotification 차단(`disallowed_tools`)·알림 금지·이메일 규칙(CLAUDE.md #22), 날짜 출처 SEC 줄 보완(3-2단계)
- 2026-09-27 09:37 stocknews-refresh 재등록: 1단계에서 설치된 스크립트의 연락처가 gmail이 아니면 외부 요청 전에 멈춤(환경 셋업 스크립트 교체 전까지 갱신 중단)
- 2026-09-27 09:55 stocknews 새 셋업 스크립트 적용 확인(시험 통과, 연락처 gmail). event-desk 재등록: 보조 에이전트·예약 깨우기 차단(`disallowed_tools`에 Agent·ScheduleWakeup), 조사는 직접(CLAUDE.md #23)
- 2026-09-27 10:57 나머지 9개 루틴도 `Agent`·`ScheduleWakeup` 차단. 10개 모두 저장된 프롬프트가 `*.prompt.md`와 일치함을 스크립트로 확인
- 2026-09-28 market-verifier·kr-verifier 재등록: 검증 '반드시 할 것'에 고지·기사 제목·'쉽게 말하면' 칸·반올림 방향 4항목 추가(CLAUDE.md #24, eval 2차). 10개 모두 저장된 프롬프트가 `*.prompt.md`와 일치함을 스크립트로 확인
- 2026-09-30 kr-desk 16:30→18:30(`30 9 * * 1-5`), kr-verifier 17:10→19:10(`10 10 * * 1-5`)로 예약 시각만 변경. 네이버가 16:00~18:00 시간외 가격을 당일 값에 반영해 기록·검증 값이 어긋났음(CLAUDE.md #25). 프롬프트 변경 없음
- 2026-10-04 kr-desk 20:30(`30 11 * * 1-5`)·kr-verifier 21:10(`10 12 * * 1-5`)으로 재등록. 원인 정정: NXT 애프터마켓이 20:00까지라 그 전엔 네이버 시세가 계속 바뀜(CLAUDE.md #25). 뉴스 옮겨 적기 규칙 추가(#26). 10개 모두 저장된 프롬프트가 `*.prompt.md`와 일치함을 스크립트로 확인
- 등록본 대조: RemoteTrigger `list` 응답을 파일로 저장한 뒤 `python3 routines/check_deployed.py <파일>` (10개 프롬프트 글자 대조 + 차단 도구 확인, 2026-10-04 추가)

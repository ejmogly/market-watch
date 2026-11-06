"""루틴 프롬프트 조립: 역할 파일 + 공통 규칙 → *.prompt.md. 규칙을 고친 뒤 실행하고, 결과를 루틴에 다시 올린다."""
from pathlib import Path

HERE = Path(__file__).parent
KR = HERE.parent / "kr" / "routines"
common = (HERE / "_common.md").read_text()
kr_common = (KR / "_kr_common.md").read_text()
brief = (HERE / "_brief.md").read_text()
value_report = (HERE / "_value_report.md").read_text()  # 주간에만 붙는 2단계
# 과거 판단 성과 표 — scripts/label_context.py 가 만든다(월 1회 갱신)
label = "\n## 과거 판단 성과 표\n" + (HERE / "_label_context.md").read_text()
kr_label = "\n## 과거 판단 성과 표\n" + (KR / "_kr_label_context.md").read_text()

BRIEFS = {
    "weekly": dict(
        KIND="주간", WRITER="weekly-brief", TITLE="주간-YYYY-MM-DD~MM-DD (기간 시작~끝)",
        PERIOD=(
            "- 기간 = 이번 주. 해외 주식·ETF·국내는 실행일(KST) 기준 직전 월요일~금요일 시장 날짜, 크립토는 직전 토요일~금요일 UTC 날짜입니다.\n"
            "- `기간 시작` = 월요일 날짜, `기간 끝` = 금요일 날짜."),
        EXTRA_CALC="",
        EXTRA_SECTIONS="5. **순위** — 해외 10종목 수익률 상위 3·하위 3, 국내 4종목 수익률 순위 (계산)",
        EXTRA_STEP=value_report,
    ),
    "monthly": dict(
        KIND="월간", WRITER="monthly-brief", TITLE="월간-YYYY-MM",
        PERIOD=(
            "- 기간 = 지난 달 1일~말일(시장 날짜). 실행일이 1일이 아니면(수동 시험) 이번 달 1일~실행 전날로 하고 제목 끝에 `(진행 중)`을 붙입니다.\n"
            "- `기간 시작` = 그 달 1일, `기간 끝` = 말일(진행 중이면 실행 전날)."),
        EXTRA_CALC=(
            "- 월중 최고·최저 = 기간 안 행들의 가격 중 최고·최저(날짜 포함). 일간 등락률 표준편차 = 기간 안 `등락률(%)` 값의 표본 표준편차.\n"
            "- 판단 유지 일수 = 자산별로 관심·관망·비중 축소였던 시장 날짜 수."),
        EXTRA_SECTIONS=(
            "5. **한 달 흐름** — 자산별 월중 최고·최저(날짜), 일간 등락률 표준편차, 판단 유지 일수 표. "
            "주차별 검증 ERROR·NEED MORE INFO 수 (계산)"),
        EXTRA_STEP="",
    ),
}

def write(name, text):
    (HERE / f"{name}.prompt.md").write_text(text)
    print(f"{name}.prompt.md  {len(text):,} chars")

for role in ["stock", "etf", "crypto", "verifier"]:
    write(role, (HERE / f"_{role}.md").read_text() + "\n\n" + common + label)
for key, v in BRIEFS.items():
    t = brief
    for k, val in v.items():
        t = t.replace("{{" + k + "}}", val)
    assert "{{" not in t, key
    env_only = common.split("## DB 속성")[0].rstrip() + "\n"  # 브리핑은 조사하지 않으므로 환경 규칙만
    write(key, t + "\n\n" + env_only)
write("event", (HERE / "_event.md").read_text() + "\n\n" + common.split("## DB 속성")[0].rstrip() + "\n")
write("kr_desk", (KR / "_kr_desk.md").read_text() + "\n\n" + kr_common + kr_label)
write("kr_verifier", (KR / "_kr_verifier.md").read_text() + "\n\n" + kr_common + kr_label)

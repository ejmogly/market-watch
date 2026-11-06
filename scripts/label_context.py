"""data/history/insights.json → 루틴 프롬프트용 '과거 판단 성과' 표 두 개.

- routines/_label_context.md            해외 10종목 (stock·etf·crypto·verifier가 읽음)
- kr/routines/_kr_label_context.md   국내 4종목 (kr-desk·kr-verifier가 읽음)
history_insights.py 를 다시 돌린 뒤 이 스크립트 → build.py 순서로 실행하고 루틴을 갱신한다(월 1회).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KR_DIR = ROOT / "kr" / "routines"
ins = json.loads((ROOT / "data" / "history" / "insights.json").read_text())
LABELS = ("관심", "관망", "비중 축소")
US = ["TSLA", "GOOGL", "NVDA", "AAPL", "SpaceX", "VOO", "SMH", "QQQM", "BTC", "ETH"]
KR = ["삼성전자", "SK하이닉스", "현대차", "두산에너빌리티"]


def table(assets, crypto_note=""):
    first = min(ins["assets"][a]["first"] for a in assets)
    last = max(ins["assets"][a]["last"] for a in assets)
    lines = [
        f"기간 {first}~{last} 일봉에 이 프롬프트의 한 줄 판단 규칙을 매일 적용한 결과다{crypto_note}.",
        "칸 = 그 판단이었던 날 수 · 그날 뒤 60거래일 평균 수익률 · 60거래일 뒤 오른 비율. 날이 겹쳐 세므로 독립 표본이 아니다.",
        "",
        "| 자산 | 관심 | 관망 | 비중 축소 |",
        "|---|---|---|---|",
    ]
    for a in assets:
        f60 = ins["assets"][a]["fwd"].get("60", {})
        cells = []
        for k in LABELS:
            v = f60.get(k)
            cells.append(f"{v['n']}일 · {v['mean']:+.1f}% · {v['win']:.0f}%" if v else "없음")
        lines.append(f"| {a} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


(ROOT / "routines" / "_label_context.md").write_text(table(US, "(크립토는 거래일 대신 일)"))
(KR_DIR / "_kr_label_context.md").write_text(table(KR))


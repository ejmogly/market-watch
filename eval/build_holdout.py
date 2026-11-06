"""2차 평가용 holdout fixture 8건(결함 6 · 정상 2) — 규칙 4개를 추가한 뒤 과적합을 보려고 새로 만든 행.

1차 fixture(F01~F20)와 같은 원자료·렌더러를 쓰되, 종목과 결함의 모양을 바꿨다.
- target 4건: 이번에 검증 규칙에 넣은 유형(고지·기사 제목·쉽게 말하면 칸·반올림 방향)을 1차와 다른 모양으로
- control 2건: 이번 규칙과 무관한 유형(52주 위치 수치, 뉴스 태그 종류)
- 정상 2건

사용법: python3 eval/build_holdout.py → eval/fixtures_holdout/H01.md ~ H08.md, eval/labels_holdout.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_fixtures as bf  # noqa: E402

EVAL = bf.EVAL


def main():
    R = {a: bf.build_row(a) for a in bf.META}
    for a in R:
        R[a]["news"] = bf.NEWS[a]
    items = []

    # target 1 — 고지 문구를 바꿈(1차는 통째로 누락)
    changed = "참고용 정보이며 투자 판단은 본인의 몫입니다."
    items.append(("QQQM", dict(body_replace=lambda l: changed if l == bf.DISCLAIMER else l), {}, "ERROR",
                  "고지 문구를 다른 문장으로 바꿈", "target", "rule6", f"고정 문구 대신 '{changed}'"))

    # target 2 — 출처 칸 기사 제목을 말줄임(1차는 다른 문장으로 축약, TSLA)
    t0 = R["NVDA"]["news"][0][2]
    short = " ".join(t0.split()[:4]) + "…"
    items.append(("NVDA", dict(short_title=short), {}, "WARNING", "출처 칸 기사 제목 말줄임", "target", "rule7", f"원문 '{t0}' → '{short}'"))

    # target 3 — '쉽게 말하면' 칸에 그 행의 값(1차는 52주 최고·최저 출처값, ETH)
    b = R["BTC"]
    items.append(("BTC", dict(easy_override=(7, f"지금 가격은 1년 범위의 {b['pos']:.0f}% 근처")), {}, "WARNING",
                  "'쉽게 말하면' 칸에 그 행의 52주 위치 값", "target", "rule8", "52주 위치 행 설명 칸에 값"))

    # target 4 — 차익 실현 **상단**을 내림(1차는 하단을 올림, SMH)
    g = R["GOOGL"]
    lo_t, hi_t, lo_tr, hi_tr = g["take"]
    wrong = bf.floor_u(hi_t, g["u"])
    assert wrong != hi_tr, "상단이 정수라 방향 오류가 드러나지 않음"
    ok_txt, bad_txt = f"~ {bf.money(hi_tr, g['u'])}(", f"~ {bf.money(wrong, g['u'])}("

    def take_hi_down(line):
        if "차익 실현 검토 구간" in line and ok_txt in line:
            line = line.replace(ok_txt, bad_txt)
            i = line.rfind("단위 올림)")
            line = line[:i] + "단위 내림)" + line[i + len("단위 올림)"):]
        return line
    items.append(("GOOGL", dict(body_replace=take_hi_down), {}, "ERROR", "차익 실현 상단 반올림 방향 오류(내림)", "target", "rule9",
                  f"상단 {hi_t:.2f}를 내림 → {wrong:.0f} (옳은 값 {hi_tr:.0f})"))

    # control 1 — 52주 위치 수치 오류(원자료의 52주 최고·최저·가격으로 재계산하면 드러남)
    v = R["VOO"]
    items.append(("VOO", {}, {"pos": v["pos"] - 9.0}, "ERROR", "52주 위치 수치 불일치", "control", None,
                  f"옳은 값 {v['pos']:.1f}%, 행 값 {v['pos'] - 9.0:.1f}%"))

    # control 2 — 뉴스 문장에 (보도) 대신 (확인)
    rep = (bf.T("보도"), bf.T("확인"))
    items.append(("TSLA", dict(body_replace=lambda l: l.replace(*rep) if l.startswith("- 2026") and rep[0] in l else l), {}, "ERROR",
                  "뉴스 인용 문장에 (확인) 태그", "control", None, "기사 인용은 (보도)"))

    # 정상 2건
    items.append(("SpaceX", {}, {}, "PASS", "정상", "normal", None, ""))
    items.append(("ETH", {}, {}, "PASS", "정상", "normal", None, ""))

    order = [3, 6, 0, 4, 7, 1, 5, 2]  # 섞는 순서 고정
    items = [items[i] for i in order]
    out = EVAL / "fixtures_holdout"
    out.mkdir(exist_ok=True)
    labels = []
    for n, (a, mz, rpatch, exp, ft, group, rule, note) in enumerate(items, 1):
        fid = f"H{n:02d}"
        r = dict(R[a], **rpatch)
        if "short_title" in mz:
            mz = dict(mz, sources=bf.sources(r, short_title=mz["short_title"]))
        props, body, rawblk = bf.render(r, mz)
        if rpatch.get("pos") is not None:  # 원자료는 옳은 값 기준이어야 한다(render는 r['pos']를 쓰지 않음)
            pass
        (out / f"{fid}.md").write_text(bf.to_markdown(fid, props, body, rawblk))
        labels.append({"id": fid, "asset": a, "expected": exp, "fault_type": ft, "group": group, "target_rule": rule,
                       "issue_no": None, "note": note})
    (EVAL / "labels_holdout.json").write_text(json.dumps(labels, ensure_ascii=False, indent=1))
    for l in labels:
        print(l["id"], l["asset"], l["expected"], l["group"], l["fault_type"])


if __name__ == "__main__":
    main()

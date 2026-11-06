"""검증 담당 평가 실행기 — full(규칙 그대로) vs ablated(이슈 기록에서 생긴 규칙 문장 제거).

로컬 `claude -p`를 도구 없이(--tools "") · CLAUDE.md/MCP/스킬 없이(--safe-mode, --strict-mcp-config) 부른다.
시스템 프롬프트 = routines/_verifier.md 행 검증 부분 + routines/_common.md (공통 제외·ablation은 eval/ablation.json).

사용법:
    python3 eval/run_eval.py prompts                    # eval/prompts/{full,ablated}.md 만들기(호출 없음)
    python3 eval/run_eval.py run full --ids F01         # 호출
    python3 eval/run_eval.py run ablated --tag r1 --workers 4
    python3 eval/run_eval.py report                     # eval/REPORT.md
호출 상한: eval/results/calls.jsonl 줄 수 기준 60회. 넘으면 호출하지 않는다.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "eval"
RES = EVAL / "results"
KST = timezone(timedelta(hours=9))
MODEL = "claude-sonnet-5"
CALL_CAP = 100  # 1차 60회 + 2차(v2·holdout) 40회 이내, 2026-09-28 사용자 승인
RANK = {"PASS": 0, "WARNING": 1, "ERROR": 2, "NEED MORE INFO": 2}

USER_TMPL = """[평가 모드] 이번 실행은 오프라인 평가입니다. 도구를 쓰지 않습니다.
아래 fixture는 Market Daily의 `검증 = 대기` 행 하나(행 속성 + 행 본문)입니다. fixture 끝의 `원자료` 블록은 검증 담당이 원출처·가격 이력에서 직접 다시 받아 python3로 재계산한 값과, 뉴스 링크를 열어 확인한 값입니다. 원출처 대조·재계산·링크 확인은 이 블록으로 대신합니다.
규칙대로 이 행을 판정하고, 아래 JSON 한 개만 출력하십시오. 다른 글, 코드 블록 표시는 쓰지 않습니다.
{{"verdict": "PASS" | "WARNING" | "ERROR" | "NEED MORE INFO", "reasons": ["판정 사유를 한 줄씩(PASS면 대조한 것)"]}}

{fixture}"""


def load_ablation():
    return json.load(open(EVAL / "ablation.json"))


def build_prompt(variant):
    ab = load_ablation()
    ver = (ROOT / "routines/_verifier.md").read_text()
    com = (ROOT / "routines/_common.md").read_text()
    # 행 검증 부분 = 처음 ~ "## 브리핑 검증" 앞
    ver_rows = ver.split("## 브리핑 검증")[0].rstrip() + "\n\n아래 규칙은 담당들이 따른 규칙입니다. 이 기준으로 검증합니다.\n"
    texts = {"_verifier.md": ver_rows, "_common.md": com}
    edits = list(ab["common_excluded"])
    if variant == "ablated":
        edits += ab["ablated"]
    for e in edits:
        t = texts[e["file"]]
        assert t.count(e["original"]) == 1, (e["file"], e["original"][:60])
        texts[e["file"]] = t.replace(e["original"], e.get("replacement", ""))
    return texts["_verifier.md"] + "\n" + texts["_common.md"]


def calls_used():
    f = RES / "calls.jsonl"
    return sum(1 for _ in open(f)) if f.exists() else 0


def call_claude(system_prompt, user_prompt):
    with tempfile.TemporaryDirectory() as cwd:
        cmd = ["claude", "-p", "--model", MODEL, "--tools", "", "--safe-mode", "--strict-mcp-config",
               "--no-session-persistence", "--output-format", "json", "--system-prompt", system_prompt]
        t0 = time.time()
        p = subprocess.run(cmd, input=user_prompt, capture_output=True, text=True, cwd=cwd, timeout=540)
        return p.returncode, p.stdout, p.stderr, round(time.time() - t0, 1)


def parse_verdict(stdout):
    try:
        outer = json.loads(stdout)
        text = outer.get("result", "")
    except Exception:
        outer, text = None, stdout
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None, text, outer
    try:
        j = json.loads(m.group())
    except Exception:
        return None, text, outer
    v = str(j.get("verdict", "")).strip().upper()
    v = "NEED MORE INFO" if v.startswith("NEED") else v
    return ({"verdict": v, "reasons": j.get("reasons", [])} if v in RANK else None), text, outer


def prompt_for(variant):
    """full·ablated는 1차 평가 때 저장한 프롬프트로 고정(규칙을 고쳐도 기준선이 바뀌지 않게).
    v2는 지금 routines/ 규칙으로 만든다(= 검증 규칙 4개 추가 뒤)."""
    frozen = EVAL / "prompts" / f"{variant}.md"
    if variant in ("full", "ablated") and frozen.exists():
        return frozen.read_text()
    return build_prompt("full")


def sets(holdout):
    if holdout:
        return EVAL / "labels_holdout.json", EVAL / "fixtures_holdout"
    return EVAL / "labels.json", EVAL / "fixtures"


def run(variant, ids, tag, workers, holdout=False):
    lab_f, fx_dir = sets(holdout)
    labels = {l["id"]: l for l in json.load(open(lab_f))}
    ids = ids or sorted(labels)
    sp = prompt_for(variant)
    if holdout:
        tag = "holdout" + ("_" + tag if tag else "")
    RES.mkdir(exist_ok=True)
    budget = CALL_CAP - calls_used()
    if len(ids) > budget:
        sys.exit(f"호출 상한 초과: 남은 {budget}회, 요청 {len(ids)}회")
    day = datetime.now(KST).strftime("%Y-%m-%d")
    out = RES / f"{day}_{variant}{'_' + tag if tag else ''}.jsonl"

    def one(fid):
        fx = (fx_dir / f"{fid}.md").read_text()
        started = datetime.now(KST).isoformat(timespec="seconds")
        rc, so, se, sec = call_claude(sp, USER_TMPL.format(fixture=fx))
        parsed, text, outer = parse_verdict(so)
        rec = {"id": fid, "variant": variant, "tag": tag, "model": MODEL, "started_kst": started, "seconds": sec,
               "returncode": rc, "expected": labels[fid]["expected"], "fault_type": labels[fid]["fault_type"],
               "issue_no": labels[fid]["issue_no"], "verdict": parsed["verdict"] if parsed else None,
               "reasons": parsed["reasons"] if parsed else None, "raw_result": text, "raw_stdout": so, "stderr": se[-2000:],
               "cost_usd": (outer or {}).get("total_cost_usd"), "usage": (outer or {}).get("usage")}
        return rec

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for rec in ex.map(one, ids):
            with open(out, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            with open(RES / "calls.jsonl", "a") as f:
                f.write(json.dumps({"id": rec["id"], "variant": variant, "tag": tag, "started_kst": rec["started_kst"],
                                    "returncode": rec["returncode"]}, ensure_ascii=False) + "\n")
            print(rec["id"], variant, "expected", rec["expected"], "→", rec["verdict"], f"{rec['seconds']}s", "rc", rec["returncode"], flush=True)
    print("결과:", out.relative_to(ROOT), "· 누적 호출", calls_used())


# ---------------------------------------------------------------- 보고서

def latest(variant, tag=""):
    fs = sorted(RES.glob(f"*_{variant}{'_' + tag if tag else ''}.jsonl"))
    if not fs:
        return None, {}
    recs = {}
    for line in open(fs[-1]):
        r = json.loads(line)
        recs[r["id"]] = r
    return fs[-1], recs


def metrics(recs, labels):
    labels = [l for l in labels if l["id"] in recs]  # 그 판본에서 실제로 돌린 행만
    faults = [l for l in labels if l["expected"] != "PASS"]
    normals = [l for l in labels if l["expected"] == "PASS"]
    got = lambda fid: recs.get(fid, {}).get("verdict")
    det = [l for l in faults if got(l["id"]) and RANK[got(l["id"])] >= RANK[l["expected"]]]
    fp = [l for l in normals if got(l["id"]) and RANK[got(l["id"])] >= 1]
    exact = [l for l in labels if got(l["id"]) == l["expected"]]
    missing = [l for l in labels if not got(l["id"])]  # 돌렸지만 JSON 판정을 못 읽은 행
    return {"n": len(labels), "n_fault": len(faults), "n_normal": len(normals), "detected": len(det), "false_pos": len(fp),
            "exact": len(exact), "missing": len(missing), "det_ids": [l["id"] for l in det], "fp_ids": [l["id"] for l in fp]}


def pct(a, b):
    return f"{a / b * 100:.1f}% ({a}/{b})" if b else "-"


def report():
    labels = json.load(open(EVAL / "labels.json"))
    ab = load_ablation()
    runs = {}
    for v, tag in [("full", ""), ("ablated", ""), ("full", "r2"), ("v2", "")]:
        f, recs = latest(v, tag)
        if f:
            runs[f"{v}{'_' + tag if tag else ''}"] = (f, recs, metrics(recs, labels))
    L = ["# 검증 담당 평가 결과 (eval)", ""]
    L.append(f"- 생성: {datetime.now(KST).strftime('%Y-%m-%d %H:%M')} KST · 모델 `{MODEL}` · `claude -p --tools \"\" --safe-mode --strict-mcp-config --no-session-persistence`")
    L.append(f"- 입력: `eval/fixtures/F01~F20.md` (정상 {sum(l['expected']=='PASS' for l in labels)} · 결함 {sum(l['expected']!='PASS' for l in labels)}), 정답 `eval/labels.json`, 판본 `eval/prompts/*.md`(ablation 목록 `eval/ablation.json`)")
    L.append(f"- 누적 `claude -p` 호출 {calls_used()}회 (상한 {CALL_CAP}회, `eval/results/calls.jsonl`)")
    L.append("- 재현: `python3 eval/build_fixtures.py && python3 eval/build_holdout.py && python3 eval/run_eval.py prompts && python3 eval/run_eval.py run full && python3 eval/run_eval.py run ablated && python3 eval/run_eval.py run v2 && python3 eval/run_eval.py run full --holdout && python3 eval/run_eval.py run v2 --holdout && python3 eval/run_eval.py report`")
    L.append("")
    L.append("## 핵심 수치")
    L.append("")
    L.append("| 판본 | 결과 파일 | 돌린 행 | 검출률(결함을 기대 심각도 이상으로) | 오탐률(정상을 WARNING 이상으로) | 심각도 일치율 | 응답 파싱 실패 |")
    L.append("|---|---|---|---|---|---|---|")
    for k, (f, recs, m) in runs.items():
        L.append(f"| {k} | `{f.relative_to(ROOT)}` | {len(recs)} | {pct(m['detected'], m['n_fault'])} | {pct(m['false_pos'], m['n_normal'])} | {pct(m['exact'], m['n'])} | {m['missing']} |")
    if "full" in runs and "ablated" in runs:
        mf, ma = runs["full"][2], runs["ablated"][2]
        L.append("")
        L.append(f"- 검출률 차이(full − ablated): **{(mf['detected'] - ma['detected']) / mf['n_fault'] * 100:+.1f}%p** · 오탐률 차이: {(mf['false_pos'] - ma['false_pos']) / mf['n_normal'] * 100:+.1f}%p · 일치율 차이: {(mf['exact'] - ma['exact']) / mf['n'] * 100:+.1f}%p")
        iss = [l for l in labels if l["issue_no"]]
        ctl = [l for l in labels if l["expected"] != "PASS" and not l["issue_no"]]
        d = lambda m, g: sum(1 for l in g if l["id"] in m["det_ids"])
        L.append(f"- 이슈 기록에서 온 결함 {len(iss)}건: full {pct(d(mf, iss), len(iss))} vs ablated {pct(d(ma, iss), len(iss))}")
        L.append(f"- 이슈와 무관한 대조 결함 {len(ctl)}건(규칙을 빼도 잡혀야 정상): full {pct(d(mf, ctl), len(ctl))} vs ablated {pct(d(ma, ctl), len(ctl))}")
    if "full" in runs and "full_r2" in runs:
        a, b = runs["full"][1], runs["full_r2"][1]
        common = [l for l in labels if l["id"] in a and l["id"] in b]
        same = [l for l in common if a[l["id"]]["verdict"] == b[l["id"]]["verdict"]]
        L.append(f"- full 반복 일치율(1회차 vs 2회차, 두 회차 모두 있는 행): {pct(len(same), len(common))} · 다르게 나온 행: "
                 + (", ".join(f"{l['id']}({a[l['id']]['verdict']}→{b[l['id']]['verdict']})" for l in common if l not in same) or "없음"))
    if "full" in runs and "v2" in runs:
        mf, mv = runs["full"][2], runs["v2"][2]
        L.append(f"- 2차(2026-09-28): 검증 규칙 4개(고지·기사 제목·'쉽게 말하면' 칸·반올림 방향)를 넣은 v2 — 검출률 {pct(mv['detected'], mv['n_fault'])} (full 대비 {(mv['detected'] - mf['detected']) / mf['n_fault'] * 100:+.1f}%p) · 오탐률 {pct(mv['false_pos'], mv['n_normal'])} · 일치율 {pct(mv['exact'], mv['n'])}")
    # holdout: 규칙을 고친 뒤 새로 만든 행(과적합 점검)
    hl_f = EVAL / "labels_holdout.json"
    hold = {}
    if hl_f.exists():
        hl = json.load(open(hl_f))
        for v in ("full", "v2"):
            f, recs = latest(v, "holdout")
            if f:
                hold[v] = (f, recs, metrics(recs, hl))
    cost = sum((json.loads(x).get("cost_usd") or 0) for f in RES.glob("*.jsonl") if f.name != "calls.jsonl" for x in open(f))
    L.append(f"- 호출 비용 합계(claude -p 보고값): {cost:.2f} USD")
    reruns = []
    for k, (f, recs, m) in runs.items():
        ids = [json.loads(x)["id"] for x in open(f)]
        reruns += [f"{k}:{i}" for i in sorted(set(ids)) if ids.count(i) > 1]
    if reruns:
        L.append(f"- 같은 파일에 두 번 기록된 행(마지막 기록을 씀): {', '.join(reruns)} — fixture 표시 버그를 고친 뒤 다시 돌림(`notes.md`)")
    L.append("")
    L.append("## 행별 결과")
    L.append("")
    cols = list(runs)
    L.append("| id | 자산 | 결함 유형 | 이슈 # | 기대 | " + " | ".join(cols) + " |")
    L.append("|---|---|---|---|---|" + "---|" * len(cols))
    for l in labels:
        cells = []
        for k in cols:
            rec = runs[k][1].get(l["id"])
            v = "미실행" if rec is None else (rec.get("verdict") or "파싱 실패")
            if v == "미실행":
                cells.append(v)
                continue
            mark = "" if v == l["expected"] else (" ▲" if v in RANK and RANK[v] > RANK[l["expected"]] else " ▼")
            cells.append(v + mark)
        L.append(f"| {l['id']} | {l['asset']} | {l['fault_type']} | {l['issue_no'] or '-'} | {l['expected']} | " + " | ".join(cells) + " |")
    L.append("")
    L.append("▲ 기대보다 심하게, ▼ 기대보다 약하게 판정. 검출은 '기대 심각도 이상'이면 인정(WARNING 기대 행을 ERROR로 판정해도 검출).")
    L.append("")
    if hold:
        L.append("## holdout — 규칙을 고친 뒤 새로 만든 8행 (과적합 점검)")
        L.append("")
        L.append("1차 fixture를 보고 규칙을 고쳤으므로, 같은 fixture 점수만으로는 과적합을 가릴 수 없다. 그래서 규칙이 겨냥한 4유형을 **다른 종목·다른 모양**으로 심은 행(target)과, 이번 규칙과 무관한 유형(control), 정상 행을 새로 만들었다(`eval/build_holdout.py`).")
        L.append("")
        L.append("| 판본 | 결과 파일 | 검출률 | target 4건 | control 2건 | 오탐률 | 일치율 |")
        L.append("|---|---|---|---|---|---|---|")
        for v, (f, recs, m) in hold.items():
            tg = [l for l in hl if l["group"] == "target"]
            ct = [l for l in hl if l["group"] == "control"]
            d = lambda g: sum(1 for l in g if l["id"] in m["det_ids"])
            L.append(f"| {v} | `{f.relative_to(ROOT)}` | {pct(m['detected'], m['n_fault'])} | {pct(d(tg), len(tg))} | {pct(d(ct), len(ct))} | {pct(m['false_pos'], m['n_normal'])} | {pct(m['exact'], m['n'])} |")
        L.append("")
        L.append("| id | 자산 | 구분 | 결함 유형 | 기대 | " + " | ".join(hold) + " |")
        L.append("|---|---|---|---|---|" + "---|" * len(hold))
        for l in hl:
            cells = []
            for v in hold:
                rec = hold[v][1].get(l["id"])
                vv = "미실행" if rec is None else (rec.get("verdict") or "파싱 실패")
                mark = "" if vv in ("미실행", l["expected"]) else (" ▲" if vv in RANK and RANK[vv] > RANK[l["expected"]] else " ▼")
                cells.append(vv + mark)
            L.append(f"| {l['id']} | {l['asset']} | {l['group']} | {l['fault_type']} | {l['expected']} | " + " | ".join(cells) + " |")
        L.append("")
    L.append("## ablation — ablated 판본에서 뺀 규칙 문장")
    L.append("")
    for e in ab["ablated"]:
        L.append(f"- #{e['issue']} `{e['file']}`: {e['original'][:140].strip()}{'…' if len(e['original']) > 140 else ''}" + (f" → `{e['replacement'].strip()}`" if e.get("replacement") else " → (삭제)"))
    L.append("")
    L.append("두 판본 모두에서 뺀 것(평가 범위 밖): " + "; ".join(e["reason"] for e in ab["common_excluded"]))
    L.append("")
    notes = EVAL / "notes.md"
    if notes.exists():
        L += notes.read_text().rstrip().split("\n") + [""]
    L.append("## 한계")
    L.append("")
    L.append("- n = 20(결함 12, 정상 8). 검출률 1건 = 8.3%p, 오탐률 1건 = 12.5%p라 차이의 신뢰구간이 넓다. 방향만 보는 수치로 읽는다.")
    L.append("- fixture는 실제 가격 이력·뉴스로 만들었지만 결함은 한 행에 하나만 심었다. 실제 행은 결함이 여럿 섞이고 본문이 길다.")
    L.append("- 도구 없이 판정하므로 이동평균·ATR은 `원자료`에 넣어 준 재계산값과 비교하는 능력만 잰다. 실제 루틴은 python으로 직접 계산한다.")
    L.append("- 일부 뉴스 제목·URL은 평가용으로 만든 것(F-행 GOOGL #13 사례 등, labels.json note). 원자료 블록 안에서는 서로 모순이 없게 맞췄다.")
    L.append("- ablated는 '이슈 기록 이전 규칙'을 문장 단위로 되돌린 근사치다. 이슈가 생긴 뒤 담당 지시문 쪽 표현이 바뀐 효과는 재지 않는다.")
    (EVAL / "REPORT.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:20]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prompts", "run", "report"])
    ap.add_argument("variant", nargs="?", choices=["full", "ablated", "v2"])
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--tag", default="")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    if a.cmd == "prompts":
        (EVAL / "prompts").mkdir(exist_ok=True)
        for v in ["full", "ablated", "v2"]:
            f = EVAL / "prompts" / f"{v}.md"
            if v != "v2" and f.exists():
                print(v, "고정(1차 평가 프롬프트 유지)", len(f.read_text()), "chars")
                continue
            p = prompt_for(v)
            f.write_text(p)
            print(v, len(p), "chars")
    elif a.cmd == "run":
        run(a.variant, a.ids, a.tag, a.workers, a.holdout)
    else:
        report()


if __name__ == "__main__":
    main()

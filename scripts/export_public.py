"""공개 저장소 만들기: 허용 목록에 있는 파일만 ../market-watch-public/ 로 복사하고, ID·연락처·로컬 경로를 가린 뒤 금지어를 검사한다.

실행(원본 저장소에서): python3 scripts/export_public.py   (실패하면 exit 1, 결과는 market-watch-public/EXPORT_CHECK.txt)

- 대상 폴더는 매번 지우고 새로 만든다. 지우는 것은 그 폴더 하나뿐이다(경로를 확인한 뒤 지움).
- README.md 는 사람이 쓰는 파일이라 지우지 않고 옮겨 둔다(없으면 건너뜀).
- 숨길 낱말과 표현은 private/export_rules.json에서 읽는다. 이 파일은 공개본에 나가지 않고, 없으면 멈춘다.
- ID와 경로 패턴은 이 파일 자체가 검사에 걸리지 않도록 base64로 적어 두고 실행할 때 푼다. 숨기려는 값이 아니다.
"""
import base64, datetime, fnmatch, json, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # market-watch
KR_SRC = ROOT.parent / "agent-office" / "routines"      # 국내 규칙 원본
OUT = ROOT.parent / "market-watch-public"
KEEP = ["README.md"]                                    # 다시 만들 때 보존하는 사람 작성 파일
PRIVATE_RULES = ROOT / "private" / "export_rules.json"  # 숨길 값. 공개본에 나가지 않는다


def _d(s):
    return base64.b64decode(s).decode("utf-8")


def load_private_rules():
    """없으면 가리지 못한 채 나갈 수 있으니 멈춘다."""
    if not PRIVATE_RULES.is_file():
        sys.exit(f"비공개 규칙 파일이 없어 멈춤: {PRIVATE_RULES}")
    return json.loads(PRIVATE_RULES.read_text(encoding="utf-8"))


PRIVATE = load_private_rules()


# ---- 허용 목록: (원본 glob, 공개본 폴더). 여기 없는 파일은 나가지 않는다 ----
INCLUDE = [
    (ROOT, "routines/_*.md", "routines"),
    (ROOT, "routines/build.py", "routines"),
    (ROOT, "routines/README.md", "routines"),              # 루틴 표·변경 기록(ID는 가림)
    (ROOT, "routines/*.prompt.md", "routines"),           # 조립 결과 예시
    (ROOT, "scripts/*.py", "scripts"),
    (ROOT, "eval/**/*", "eval"),
    (ROOT, "metrics/*.csv", "metrics"),
    (ROOT, "metrics/*.md", "metrics"),
    (ROOT, "metrics/*.jsonl", "metrics"),
    (ROOT, "metrics/*.json", "metrics"),               # 사례 페이지 생성기 입력(스냅숏·요약)
    (ROOT, "docs/**/*", "docs"),
    (ROOT, ".claude/agents/*.md", ".claude/agents"),
    (ROOT, "watchlist.json", "."),
    (KR_SRC, "_kr_*.md", "kr/routines"),
    # 보고서 예시 3개: 주식 담당 행, 크립토 담당 행, 검증 결과
    (ROOT, "output/NVDA_2026-09-24.md", "examples"),
    (ROOT, "output/BTC_2026-09-25.md", "examples"),
    (ROOT, "output/verify_2026-09-25_r3.md", "examples"),
]
EXCLUDE = [                                              # 허용 glob에 걸려도 빼는 것
    "*stocknews*", "docs/portfolio_plan.html", "docs/reading_order.html", "private/*", "*/private/*", "*/__pycache__/*", "*.pyc", "*/.DS_Store",
]
VERBATIM = {"scripts/export_public.py"}              # 자기 자신: 가릴 값은 base64라 그대로 복사(검사는 거침)
TEXT_EXT = {".md", ".py", ".json", ".jsonl", ".csv", ".txt", ".html", ".js", ".css", ".sh", ".toml", ".yaml", ".yml"}

# ---- 가림 규칙 ----
REDACT = [
    (r"collection://[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "collection://<NOTION_ID>"),
    (r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<NOTION_ID>"),
    (r"(?<![0-9A-Za-z])[0-9a-f]{32}(?![0-9A-Za-z])", "<NOTION_ID>"),
    (_d("dHJpZ19bMC05QS1aYS16XXs4LH0="), "<TRIGGER_ID>"),      # 루틴 ID
    (_d("ZW52X1swLTlBLVphLXpdezgsfQ=="), "<ENV_ID>"),          # 실행 환경 ID
    (_d("c2Vzc2lvbl9bMC05QS1aYS16XXs4LH0="), "<SESSION_ID>"),  # 세션 ID
    (_d("Y3NlX1swLTlBLVphLXpdezgsfQ=="), "<SESSION_ID>"),      # 클라우드 세션 ID
    (r"https://claude\.ai/(?:code/)?artifact/[A-Za-z0-9-]+", "<ARTIFACT_URL>"),
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}", "<CONTACT_EMAIL>"),
]
# 공개본 폴더 구조에 맞춘 경로 바꿈 (코드가 공개본에서 그대로 돌게)
PATH_FIX = [
    ('HERE.parent.parent / "agent-office" / "routines"', 'HERE.parent / "kr" / "routines"'),
    ('ROOT.parent / "agent-office" / "routines"', 'ROOT / "kr" / "routines"'),
    ("lab/agent-office/routines/", "kr/routines/"),
    ("lab/agent-office", "agent-office"),
]
# 운영 환경을 드러내는 표현을 일반 표현으로 (공개 요약본과 모든 파일에 적용)
PHRASES = PRIVATE["phrases"]
# ---- 금지어 (하나라도 남으면 실패) ----
FORBIDDEN = PRIVATE["forbidden"] + [
    ("이메일 주소", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"),
    ("루틴 ID", _d("dHJpZ18=")),
    ("환경 ID", _d("ZW52XzA=")),
    ("환경 ID(형식)", _d("ZW52X1swLTlBLVphLXpdezgsfQ==")),
    ("세션 ID", _d("c2Vzc2lvbl9bMC05QS1aYS16XXs4LH0=")),
    ("클라우드 세션 ID", _d("Y3NlXw==")),
    # 모르는 접두도 잡는다: 짧은 접두 + 밑줄 + 숫자와 글자가 섞인 16자 이상
    ("접두 붙은 ID 형식", r"(?<![0-9A-Za-z_])[A-Za-z][0-9A-Za-z]{1,14}_(?=[0-9A-Za-z]*[0-9])(?=[0-9A-Za-z]*[A-Za-z])[0-9A-Za-z]{16,}(?![0-9A-Za-z_])"),
    ("Notion ID(32자리 hex)", r"(?<![0-9A-Za-z])[0-9a-f]{32}(?![0-9A-Za-z])"),
    ("로컬 절대경로", _d("L1VzZXJzLw==")),
]


def local_prefixes():
    """원본 컴퓨터의 절대경로 → 공개본 상대경로. 문자열은 실행할 때 만든다."""
    home = str(Path.home())
    pairs = [
        (str(KR_SRC) + "/", "kr/routines/"),
        (str(ROOT) + "/", ""),
        (str(ROOT), "."),
        (str(ROOT).replace(home, "~") + "/", ""),
        (str(ROOT).replace(home, "~"), "."),
        (str(ROOT.parent.parent), "<LOCAL_PATH>"),
        (str(ROOT.parent.parent).replace(home, "~"), "<LOCAL_PATH>"),
        (home, "~"),
    ]
    return [(a, b) for a, b in pairs if a]


def clean(text):
    for a, b in local_prefixes():
        text = text.replace(a, b)
    text = re.sub(_d("L1VzZXJzL1teL1xzYCdcIildKy8="), "~/", text)  # 남은 다른 사용자 경로
    for a, b in PATH_FIX:
        text = text.replace(a, b)
    for a, b in PHRASES:
        text = re.sub(a, b, text)
    for pat, rep in REDACT:
        text = re.sub(pat, rep, text)
    return text


def excluded(rel):
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch("/" + rel, p) for p in EXCLUDE)


def collect():
    """(원본 Path, 공개본 상대경로) 목록."""
    out = {}
    for base, pattern, dest in INCLUDE:
        if not base.exists():
            continue
        for src in sorted(base.glob(pattern)):
            if not src.is_file():
                continue
            rel_src = src.relative_to(base).as_posix()
            if excluded(rel_src) or excluded(src.name):
                continue
            if pattern.endswith("**/*"):             # 폴더째 복사: 하위 구조 유지
                top = pattern.split("/")[0]
                rel = Path(dest) / src.relative_to(base / top)
            else:
                rel = Path(dest) / src.name
            out[rel.as_posix()] = src
    return out


def rules_summary():
    """CLAUDE.md → docs/rules.md: 행·태그·산출·판단 규칙과 이슈 기록만. 금지어가 남는 줄은 뺀다."""
    src = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    start = src.find("## 행 규칙")
    body = src[start:] if start >= 0 else ""
    kept, dropped = [], []
    for line in clean(body).splitlines():
        hit = [name for name, pat in FORBIDDEN if re.search(pat, line)]
        if hit:
            m = re.match(r"\|\s*(\d+)\s*\|", line)
            dropped.append(f"이슈 #{m.group(1)}" if m else f"줄({', '.join(hit)})")
            continue
        kept.append(line)
    head = ("# 운영 규칙 요약 (공개용)\n\n"
            "원본 운영 지침에서 행·태그·산출 지표·판단 규칙과 이슈 기록만 옮겼습니다. "
            "`scripts/export_public.py`가 만들며, ID와 연락처는 가려 두었습니다.\n\n")
    return head + "\n".join(kept).rstrip() + "\n", dropped


def safe_reset(path):
    """OUT 하나만 지운다. 다른 경로면 멈춘다."""
    path = path.resolve()
    if path.name != "market-watch-public" or path.parent != ROOT.parent.resolve() or path == ROOT:
        sys.exit(f"대상 경로가 예상과 달라 멈춤: {path}")
    # .git(공개 저장소 이력)과 KEEP 파일은 남기고 나머지만 지운다
    path.mkdir(exist_ok=True)
    saved = [k for k in KEEP if (path / k).is_file()]
    for child in path.iterdir():
        if child.name == ".git" or child.name in KEEP:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    return saved


def hidden_terms(line):
    """base64로 적은 값을 풀어 숨길 값을 찾는다. 풀면 바로 읽히므로 base64는 가린 것이 아니다."""
    names = set()
    for token in re.findall(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{8,}={0,2}(?![A-Za-z0-9+/=])", line):
        if len(token) % 4:
            continue
        try:
            text = base64.b64decode(token, validate=True).decode("utf-8")
        except ValueError:
            continue
        names.update(name for name, pat in PRIVATE["forbidden"] if re.search(pat, text))
    return names


def scan(root):
    hits = []
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.name == "EXPORT_CHECK.txt" or ".git" in f.relative_to(root).parts:
            continue
        try:                                                 # 확장자와 상관없이 글자 파일은 모두 검사
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for name, pat in FORBIDDEN:
                if re.search(pat, line):
                    hits.append((f.relative_to(root).as_posix(), n, name))
            for name in hidden_terms(line):
                hits.append((f.relative_to(root).as_posix(), n, f"{name}(base64)"))
    return hits


def main():
    files = collect()
    kept = safe_reset(OUT)
    copied, binary = 0, 0
    for rel, src in files.items():
        dst = OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if rel in VERBATIM:
            shutil.copy2(src, dst)
        elif src.suffix in TEXT_EXT:
            dst.write_text(clean(src.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
        else:
            shutil.copy2(src, dst)
            binary += 1
        copied += 1
    rules, dropped = rules_summary()
    (OUT / "docs").mkdir(exist_ok=True)
    (OUT / "docs" / "rules.md").write_text(rules, encoding="utf-8")

    hits = scan(OUT)
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST")
    by_dir = {}
    for rel in files:
        top = rel.split("/")[0] if "/" in rel else "(최상위)"
        by_dir[top] = by_dir.get(top, 0) + 1
    lines = [
        f"export 시각: {now}",
        f"복사한 파일: {copied}개 (가림 없이 그대로 복사한 비텍스트 {binary}개) + 생성 docs/rules.md 1개"
        + (f" + 보존 {', '.join(kept)}" if kept else ""),
        "폴더별: " + ", ".join(f"{k} {v}" for k, v in sorted(by_dir.items())),
        f"rules.md에서 뺀 줄: {len(dropped)}개" + (f" ({', '.join(dropped)})" if dropped else ""),
        f"금지어 검사: 패턴 {len(FORBIDDEN)}종, 결과 {'0건 — 통과' if not hits else f'{len(hits)}건 — 실패'}",
    ]
    lines += [f"  {p}:{n}  {name}" for p, n, name in hits]
    (OUT / "EXPORT_CHECK.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()

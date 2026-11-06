"""metrics/·eval/ 파일 → docs/case_study.html(아티팩트용 조각), docs/index.html(GitHub Pages용 단독 문서)

터미널·트레이딩 데스크 스타일, 한·영 전환. 수치는 모두 산출물에서 읽고,
손으로 옮기는 문장·값은 docs/case_inputs.json 한 곳에만 둔다.
"""
import csv, html, json, re
from collections import Counter, OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
M = ROOT / "metrics"
ops = json.load(open(M / "ops_metrics.json"))
sig = json.load(open(M / "signal_eval.json"))
verd = [json.loads(l) for l in open(M / "verdicts.jsonl")]
runs = [json.loads(l) for l in open(M / "runs.jsonl")]
ev = list(csv.DictReader(open(M / "events_study.csv")))
inp = json.load(open(ROOT / "docs" / "case_inputs.json"))
esc = html.escape
KST = timezone(timedelta(hours=9))


def T(ko, en, tag="span"):
    """한·영 두 벌. CSS가 현재 언어만 보여 준다."""
    return f'<{tag} class="ko">{ko}</{tag}><{tag} class="en">{en}</{tag}>'


def ST(ko, en, cls="", **attrs):
    """SVG text 두 벌."""
    a = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    return f'<text class="ko {cls}" {a}>{ko}</text><text class="en {cls}" {a}>{en}</text>'


# ---------- 티커 스냅숏 (원자료가 있으면 갱신, 공개본에서는 저장된 스냅숏 사용) ----------
TK = M / "ticker_snapshot.json"
HIST = ROOT / "data" / "history" / "history.csv"
if HIST.exists():
    last = OrderedDict()
    for r in csv.DictReader(open(HIST)):
        last[r["asset"]] = r
    tk = [{"asset": a, "close": float(r["close"]), "ret": float(r["ret"] or 0), "date": r["date"],
           "cur": r["currency"], "label": r["label"]} for a, r in last.items()]
    TK.write_text(json.dumps(tk, ensure_ascii=False, indent=1))
tick = json.load(open(TK))
LBL = {"관심": "WATCH", "관망": "HOLD", "비중 축소": "REDUCE"}

# ---------- 07 포지션용 가격 (아티팩트: 일별 종가 전체 · 공개본: 마지막 종가만) ----------
LCODE = {"관심": 0, "관망": 1, "비중 축소": 2}
px_full = OrderedDict()
if HIST.exists():
    for r in csv.DictReader(open(HIST)):
        s_ = px_full.setdefault(r["asset"], {"cur": r["currency"], "d": [], "c": [], "l": []})
        c_ = float(r["close"])
        s_["d"].append(r["date"]); s_["c"].append(round(c_) if r["currency"] == "KRW" else round(c_, 4)); s_["l"].append(LCODE.get(r["label"], -1))
px_lite = OrderedDict((t["asset"], {"cur": t["cur"], "d": [t["date"]], "c": [t["close"]], "l": [LCODE.get(t["label"], -1)]}) for t in tick)
px_asof = max(t["date"] for t in tick)
FXF = ROOT / "data" / "history" / "fx_usdkrw.csv"   # scripts/fetch_fx.py
fx_full = {"d": [], "c": []}
if FXF.exists():
    for r in csv.DictReader(open(FXF)):
        fx_full["d"].append(r["date"]); fx_full["c"].append(float(r["usdkrw"]))
fx_lite = {"d": fx_full["d"][-1:], "c": fx_full["c"][-1:]}
jsd = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def fmt_px(t):
    c = t["close"]
    return f"{c:,.0f}" if t["cur"] == "KRW" or c >= 10000 else f"{c:,.2f}"


tape_items = "".join(
    f'<span class="tk"><b>{esc(t["asset"])}</b> {fmt_px(t)} <i class="{"up" if t["ret"] >= 0 else "dn"}">{t["ret"]:+.2f}%</i>'
    f'<em>{LBL.get(t["label"], "")}</em></span>' for t in tick)

# ---------- 숫자 ----------
g = ops["guardrails"]
assets = sig["assets"]
n_assets = sig["summary"]["assets"]
beat = len(sig["summary"]["rule_beats_hold_return"])
shallow = len(sig["summary"]["rule_smaller_drawdown"])
p60 = sig["pooled"]["60"]
ev_db = [r for r in ev if r["match"]]
ev_match = sum(1 for r in ev_db if r["match"] == "일치")
E = inp["eval"]
recall_full = E["rows"][-1]["recall"].split(" ")[0]
recall_hold = E["holdout"]["rows"][-1]["recall"].split(" ")[0]
viol_before = g["push_before"][0] + g["company_email_before"][0] + g["agent_before"][0]

ratios = {}
for line in open(M / "events_summary.md"):
    m = re.match(r"\| (\S+) \| (US|KR) \| (\d+) \|.*\| ([\d.]+)배 \(", line)
    if m:
        ratios[m.group(1)] = (m.group(2), int(m.group(3)), float(m.group(4)))
us = sorted(((k, v[2]) for k, v in ratios.items() if v[0] == "US" and v[1] >= 4), key=lambda x: -x[1])
kr = sorted(((k, v[2]) for k, v in ratios.items() if v[0] == "KR" and v[1] >= 4), key=lambda x: -x[1])

# ---------- eval 격자 (eval/REPORT.md 행별 표) ----------
grid, hgrid = [], []
rep = ROOT / "eval" / "REPORT.md"
strip = lambda c: c.replace(" ▲", "").replace(" ▼", "").strip()
if rep.exists():
    cols = None
    for line in open(rep):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("| id | 자산 | 결함 유형"):
            cols = cells
        elif line.startswith("| F") and cols:
            r = dict(zip(cols, cells))
            grid.append(dict(id=r["id"], asset=r["자산"], fault=r["결함 유형"], issue=r["이슈 #"], exp=r["기대"],
                             abl=strip(r.get("ablated", "")), full=strip(r.get("full", "")), v2=strip(r.get("v2", ""))))
        elif line.startswith("| H"):
            c = cells
            hgrid.append(dict(id=c[0], asset=c[1], group=c[2], fault=c[3], exp=c[4], full=strip(c[5]), v2=strip(c[6])))
SEV = {"PASS": 0, "WARNING": 1, "ERROR": 2}


def cell(exp, got):
    if exp == "PASS":
        return ("ok", "✓") if got == "PASS" else ("fa", "!")
    return ("hit", "●") if SEV.get(got, -1) >= SEV[exp] else ("miss", "○")


def grid_row(x, keys, hold=False):
    if x["exp"] == "PASS":
        desc = T("정상 행", "clean row")
    else:
        desc = esc(x["fault"])
    tag = f' <i>#{esc(x["issue"])}</i>' if not hold and x.get("issue", "-") != "-" else ""
    if hold and x["group"] != "normal":
        tag = f' <i>{"target" if x["group"] == "target" else "control"}</i>'
    cells = "".join(f'<span class="gc {c}" title="{k}: {esc(x[k])}">{s_}</span>' for k in keys for c, s_ in [cell(x["exp"], x[k])])
    return (f'<div class="gr g{len(keys)}"><span class="gid">{x["id"]}</span><span class="gas">{esc(x["asset"])}</span>'
            f'<span class="gft">{desc}{tag}</span>{cells}</div>')


grid_html = "".join(grid_row(x, ("abl", "full", "v2")) for x in grid)
hgrid_html = "".join(grid_row(x, ("full", "v2"), hold=True) for x in hgrid)

# ---------- 실행 로그 ----------
def kst(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(KST)


log_lines = []
for r in sorted(runs, key=lambda r: r["created_at"]):
    t = kst(r["created_at"])
    tag = {"success": ("ok", "OK"), "not_fetched": ("dim", "--")}.get(r["result_status"], ("bad", "ERR"))
    flags = []
    if r.get("push_notification_uses"):
        flags.append('<b class="fl bad">PUSH</b>')
    if r.get("company_email_in_ua"):
        flags.append('<b class="fl bad">EMAIL</b>')
    if r.get("agent_tool_uses"):
        flags.append(f'<b class="fl warn">AGENT×{r["agent_tool_uses"]}</b>')
    dur = f'{r["duration_s"] / 60:.1f}m' if r["duration_s"] else ""
    en_note = f'{r["turns"]} turns · {dur}' if r["turns"] else f"{dur} · log not read"
    kind = "SCHED" if r["trigger_kind"] == "scheduled" else r["trigger_kind"].upper()
    log_lines.append(
        f'<div class="ll"><span class="lt">{t:%m-%d %H:%M}</span><span class="lk {tag[0]}">{tag[1]}</span>'
        f'<span class="lr">{esc(r["routine"])}</span><span class="lm">{kind}</span>'
        f'<span class="ln">{"".join(flags)} {T(esc(r["note"]), esc(en_note))}</span></div>')

# ---------- 24시간 스케줄 ----------
# (시각, 이름, 종류, 위/아래, 라벨 정렬) — 가까운 아침 세 개는 좌·중·우로 벌린다
SCHED = [("07:00", "stock · etf · crypto", "desk", "", "ar"), ("07:40", "market-verifier", "ver", "lo", ""), ("08:10", "stocknews", "page", "", "al"),
         ("19:00", "event-desk", "event", "", "ar"), ("20:30", "kr-desk", "desk", "lo", ""), ("21:10", "kr-verifier", "ver", "", "al")]
sched_html = "".join(
    f'<div class="sm {k} {pos} {al}" style="left:{(int(h[:2]) * 60 + int(h[3:])) / 1440 * 100:.2f}%"><span class="st">{h}</span><span class="sn">{esc(n)}</span></div>'
    for h, n, k, pos, al in SCHED)
hours = "".join(f'<span class="hr" style="left:{h / 24 * 100:.2f}%">{h:02d}</span>' for h in range(0, 25, 3))

# ---------- 판정 추이 ----------
vc = Counter(("-".join(v["title"].split("-")[1:4]), v["mode"], v["verdict"]) for v in verd)
vkeys = sorted({(d, m) for d, m, _ in vc})


def vrow(d, m):
    segs = "".join(f'<span class="{c}" style="flex:{n}">{n}</span>'
                   for n, c in ((vc.get((d, m, "PASS"), 0), "p"), (vc.get((d, m, "WARNING"), 0), "w"), (vc.get((d, m, "ERROR"), 0), "e")) if n)
    mode = T("수동", "manual") if m == "수동" else T("예약", "sched")
    return f'<div class="vrow"><span class="vd">{d[5:].replace("-", "/")} {mode}</span><span class="vb">{segs}</span></div>'


vbars = "".join(vrow(d, m) for d, m in vkeys)

# ---------- 가드레일 diff ----------
def diff(ko, en, b, a, when):
    return (f'<div class="df"><div class="dh">{T(ko, en)}</div>'
            f'<div class="dm">- {b[0]}/{b[1]} {T("실행", "runs")}</div><div class="dp">+ {a[0]}/{a[1]} {T("실행", "runs")}</div>'
            f'<div class="dw">{when}</div></div>')


diffs = (diff("무단 휴대폰 알림", "unrequested phone push", g["push_before"], g["push_after"], "PushNotification blocked · 09-26 21:45")
         + diff("외부 요청에 회사 이메일", "company e-mail in outbound UA", g["company_email_before"], g["company_email_after"], "contact rule + pre-request check · 09-26 21:45")
         + diff("보조 에이전트에 위임", "delegation to sub-agent", g["agent_before"], g["agent_after"], "Agent · ScheduleWakeup blocked · 09-27 10:57"))

# ---------- 사고 = git log ----------
TYPE = {"12·13": "fix(desk)", "브리핑": "fix(brief)", "20": "fix(event)", "22": "sec(guard)", "23": "sec(guard)", "15·18": "perf(notion)"}


def gl(i):
    no = "brief" if i["no"] == "브리핑" else i["no"]
    return (f'<div class="gl"><span class="gh">#{esc(no)}</span><span class="gt">{TYPE.get(i["no"], "fix")}</span>'
            f'<div class="gb"><p class="gw">{T(esc(i["what"]), esc(i["what_en"]))}</p>'
            f'<p class="gx"><span>{T("발견", "found by")}</span> {T(esc(i["caught"]), esc(i["caught_en"]))}</p>'
            f'<p class="gx"><span>{T("조치", "fix")}</span> {T(esc(i["fix"]), esc(i["fix_en"]))}</p>'
            f'<p class="ga {i["state"]}">→ {T(esc(i["after"]), esc(i["after_en"]))}</p></div></div>')


glog = "".join(gl(i) for i in inp["incidents"])

# ---------- 차트 ----------
def mdd_chart():
    rows = sorted(assets.items(), key=lambda kv: kv[1]["rule"]["mdd"] - kv[1]["hold"]["mdd"], reverse=True)
    W, L, R, top, rh = 760, 124, 80, 44, 30
    Hh = top + rh * len(rows) + 30
    sx = (W - L - R) / 70
    o = [f'<svg viewBox="0 0 {W} {Hh}" role="img" aria-label="max drawdown hold vs rule">']
    for t in range(0, 71, 10):
        x = L + t * sx
        o.append(f'<line x1="{x:.1f}" y1="{top - 8}" x2="{x:.1f}" y2="{Hh - 24}" class="gridl"/><text x="{x:.1f}" y="{Hh - 6}" class="ax" text-anchor="middle">{"0" if t == 0 else f"-{t}%"}</text>')
    o.append(f'<circle cx="{L + 5}" cy="14" r="5" class="dh"/>' + ST("단순 보유", "buy &amp; hold", cls="ax", x=L + 16, y=18)
             + f'<circle cx="{L + 130}" cy="14" r="5" class="dr"/>' + ST("규칙 전략", "rule strategy", cls="ax", x=L + 141, y=18))
    for i, (a, s) in enumerate(rows):
        y = top + i * rh + rh / 2
        h, r = -s["hold"]["mdd"], -s["rule"]["mdd"]
        cls = "sg" if r < h - .05 else ("sb" if r > h + .05 else "sf")
        d = h - r
        lab = "0.0" if abs(d) < .05 else f"{d:+.1f}"
        tone = "up" if d > .05 else ("dn" if d < -.05 else "")
        o.append(f'<text x="{L - 14}" y="{y + 4}" class="lb" text-anchor="end">{esc(a)}</text>'
                 f'<line x1="{L + h * sx:.1f}" y1="{y}" x2="{L + r * sx:.1f}" y2="{y}" class="{cls}"/>'
                 f'<circle cx="{L + h * sx:.1f}" cy="{y}" r="5" class="dh"/><circle cx="{L + r * sx:.1f}" cy="{y}" r="5" class="dr"/>'
                 f'<text x="{L + max(h, r) * sx + 12:.1f}" y="{y + 4}" class="nv {tone}">{lab}pp</text>')
    return "".join(o) + "</svg>"


def ci_chart():
    base = p60["base_mean"]
    W, L, R, top, rh = 760, 124, 40, 34, 46
    lo, hi = -5, 30
    sx = (W - L - R) / (hi - lo)
    X = lambda v: L + (v - lo) * sx
    Hh = top + rh * 3 + 30
    o = [f'<svg viewBox="0 0 {W} {Hh}" role="img" aria-label="60-day forward return by label with 90% CI">']
    for t in range(lo, hi + 1, 5):
        o.append(f'<line x1="{X(t):.1f}" y1="{top - 8}" x2="{X(t):.1f}" y2="{Hh - 24}" class="gridl"/><text x="{X(t):.1f}" y="{Hh - 6}" class="ax" text-anchor="middle">{t:+d}%</text>')
    o.append(f'<line x1="{X(base):.1f}" y1="{top - 16}" x2="{X(base):.1f}" y2="{Hh - 24}" class="bl"/>'
             + ST(f"전체 평균 {base:+.1f}%", f"all windows {base:+.1f}%", cls="ax", x=f"{X(base) + 6:.1f}", y=top - 6))
    for i, (k, en) in enumerate((("관심", "WATCH"), ("관망", "HOLD"), ("비중 축소", "REDUCE"))):
        v = p60[k]
        y = top + 16 + i * rh
        a, b = v["ci90"]
        o.append(ST(k, en, cls="lb", x=L - 14, y=y + 4, text_anchor="end")
                 + f'<rect x="{X(a):.1f}" y="{y - 7}" width="{X(b) - X(a):.1f}" height="14" rx="2" class="ci"/>'
                 f'<circle cx="{X(v["mean"]):.1f}" cy="{y}" r="5" class="dr"/><text x="{X(b) + 10:.1f}" y="{y + 4}" class="nv">{v["mean"]:+.1f}% n={v["n"]}</text>')
    return "".join(o) + "</svg>"


def ratio_chart():
    rows = [(a, r, "us") for a, r in us] + [(a, r, "kr") for a, r in kr]
    W, L, R, top, rh = 760, 124, 60, 10, 28
    Hh = top + rh * len(rows) + 28
    sx = (W - L - R) / 4
    o = [f'<svg viewBox="0 0 {W} {Hh}" role="img" aria-label="day-after-earnings move vs typical day">']
    for t in range(0, 5):
        o.append(f'<line x1="{L + t * sx:.1f}" y1="{top - 4}" x2="{L + t * sx:.1f}" y2="{Hh - 22}" class="gridl"/><text x="{L + t * sx:.1f}" y="{Hh - 4}" class="ax" text-anchor="middle">{t}x</text>')
    for i, (a, r, k) in enumerate(rows):
        y = top + i * rh
        o.append(f'<text x="{L - 14}" y="{y + 15}" class="lb" text-anchor="end">{esc(a)}</text>'
                 f'<rect x="{L}" y="{y + 5}" width="{r * sx:.1f}" height="14" class="b{k}"/><text x="{L + r * sx + 8:.1f}" y="{y + 16}" class="nv">{r:.1f}x</text>')
    o.append(f'<line x1="{L + sx:.1f}" y1="{top - 4}" x2="{L + sx:.1f}" y2="{Hh - 22}" class="bl"/>')
    return "".join(o) + "</svg>"


sig_rows = "".join(
    f'<tr><td>{esc(a)}</td><td>{s["hold"]["total"]:+.1f}%</td><td>{s["rule"]["total"]:+.1f}%</td>'
    f'<td class="{"up" if s["rule"]["total"] > s["hold"]["total"] else "dn"}">{s["rule"]["total"] - s["hold"]["total"]:+.1f}</td>'
    f'<td>{s["hold"]["mdd"]:.1f}%</td><td>{s["rule"]["mdd"]:.1f}%</td><td>{s["exposure"]:.0f}%</td></tr>' for a, s in assets.items())

eval_rows = "".join(
    f'<tr class="{"hl" if i == len(E["rows"]) - 1 else ""}"><td>{T(esc(r["variant"]), esc(r["variant_en"]))}</td>'
    f'<td class="big {"c-cy" if i == len(E["rows"]) - 1 else ""}">{esc(r["recall"].split(" ")[0])}</td>'
    f'<td class="big {"dn" if r["fpr"].startswith("25") else "c-up"}">{esc(r["fpr"].split(" ")[0])}</td><td>{esc(r["sev"].split(" ")[0])}</td></tr>'
    for i, r in enumerate(E["rows"]))
hold_rows = "".join(
    f'<tr class="{"hl" if i == 1 else ""}"><td>{T(esc(r["variant"]), esc(r["variant_en"]))}</td><td class="big {"c-cy" if i == 1 else ""}">{esc(r["recall"].split(" ")[0])}</td>'
    f'<td>{esc(r["target"])}</td><td class="big c-up">{esc(r["fpr"].split(" ")[0])}</td></tr>' for i, r in enumerate(E["holdout"]["rows"]))

roles = "".join(
    f'<article class="role"><div class="rh">$ whoami --role={r["tag"].lower()}</div><h3>{T(esc(r["title"]), esc(r["title_en"]))}</h3><ul>'
    + "".join(f"<li>{T(esc(k), esc(e))}</li>" for k, e in zip(r["bullets"], r["bullets_en"])) + "</ul></article>" for r in inp["roles"])

snap = ops["snapshot_at_utc"][:10]
CSS = open(ROOT / "docs" / "case_study.css").read()
POSJS = open(ROOT / "docs" / "positions.js").read()

pos_section = f"""<section id="pos">
  <div class="sh"><span class="idx">07 / {T("포지션", "positions")}</span><h2>{T("내 매매 기록으로 보는 지금 손익", "What my own trades are worth now")}</h2>
  <p>{T("산 종목만 적으면 됩니다. 수량·단가·금액 중 둘을 적으면 나머지를 계산하고, 단가를 비우면 그날 종가로 추정합니다. 평균 단가는 이동평균법, 현재가는 마지막 종가이며 직접 바꿀 수 있습니다.",
    "Log only what you bought. Enter two of quantity, price and amount and the third is derived; leave price blank to use that day's close (marked as an estimate). Average cost uses the moving-average method; current price is the last close and can be overridden.")}</p></div>
  <div class="pmode demo" id="pmode"></div>
  <div class="win"><div class="wt"><span>$ trade add</span><span>{T("종가 기준", "closes as of")} <b id="pxasof"></b></span></div><div class="wb">
    <form id="pf" class="pf" autocomplete="off">
      <label>{T("날짜", "date")}<input type="date" name="date" required></label>
      <label>{T("종목", "asset")}<select name="asset"></select></label>
      <div class="side"><span class="lbl">{T("구분", "side")}</span><input type="hidden" name="side" value="buy"><div class="seg" role="group"><button type="button" data-side="buy" aria-pressed="true">{T("매수", "BUY")}</button><button type="button" data-side="sell" aria-pressed="false">{T("매도", "SELL")}</button></div></div>
      <label>{T("수량", "quantity")}<input type="number" name="qty" step="any" min="0" inputmode="decimal"></label>
      <label>{T("단가", "price")}<input type="number" name="price" step="any" min="0" inputmode="decimal"></label>
      <label>{T("금액", "amount")}<input type="number" name="amount" step="any" min="0" inputmode="decimal"></label>
      <label>{T("수수료", "fee")}<input type="number" name="fee" step="any" min="0" inputmode="decimal"></label>
      <label>{T("메모", "memo")}<input type="text" name="memo" maxlength="200"></label>
      <div class="act"><button class="btn" type="submit">{T("기록 추가", "add trade")}</button><span class="pmsg" id="pmsg" role="status"></span></div>
    </form>
    <p class="note">{T("통화는 종목 통화 그대로입니다(미국 주식·ETF·크립토 USD, 국내 KRW). 세금은 넣지 않습니다. 'VOO 대비'는 같은 날 같은 돈을 VOO에 넣고 같은 비율로 팔았을 때와의 총수익률 차이입니다.",
      "Amounts stay in the asset's currency (US stocks · ETFs · crypto in USD, Korean stocks in KRW). Taxes are not modeled. 'vs VOO' compares total return with putting the same money into VOO on the same days and selling the same fractions.")}</p>
  </div></div>
  <div class="ins" id="pins" hidden></div>
  <div class="pk" id="pk"></div>
  <div class="win" id="pwrap"><div class="wt"><span>positions</span><span>{T("가진 종목만", "held assets only")}</span></div><div class="tb"><table class="st" id="ptab"></table></div>
    <details class="ovr-d"><summary>{T("현재가 직접 입력 · 환율", "override price · FX")}</summary><div class="ovr" id="povr"></div></details></div>
  <div class="win"><div class="wt"><span>trades</span><span id="tcount"></span></div><div class="tb"><table class="st" id="ttab"></table></div></div>
  <p class="note">{T("투자 권유가 아닌 개인 기록용 계산입니다. 추정 표시가 붙은 값은 실제 체결가와 다를 수 있습니다.", "Personal bookkeeping, not investment advice. Values marked as estimates may differ from actual fills.")}</p>
</section>
"""

page = f"""<title>market-watch 사례 연구</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700;800&family=Noto+Sans+KR:wght@400;500;700;900&display=swap">
<style>
{CSS}
</style>
<div class="bar"><div class="w">
<span class="dots" aria-hidden="true"><i></i><i></i><i></i></span>
<span class="path">~/<b>market-watch</b> — case-study</span>
<nav class="nav" aria-label="sections"><a href="#arch">{T("구조", "arch")}</a><a href="#eval">eval</a><a href="#ops">{T("운영", "ops")}</a><a href="#find">{T("발견", "findings")}</a><a href="#roles">{T("한 일", "role")}</a><a href="#pos">{T("포지션", "positions")}</a></nav>
<button class="lang" id="lang" type="button" aria-label="Switch language"><span class="lk">KO</span> / <span class="le">EN</span></button>
<span class="live">SNAP {snap}</span>
</div></div>
<div class="tape" aria-label="watchlist ticker"><div class="run">{tape_items}{tape_items}</div></div>
<main class="w">
<header class="hero">
  <div class="prompt">cat README --lang={T("ko", "en")}</div>
  <h1>{T('AI 에이전트 10개가<br>매일 시장을 조사하고,<br><span class="hl">서로의 숫자를 다시 계산한다.</span>',
         "Ten AI agents research<br>the market every morning<br><span class=\"hl\">and recompute each other's numbers.</span>")}</h1>
  <p class="lede">{T("관심 종목 14개를 클라우드 예약 루틴 10개가 <b>조사 → 검증 → 요약</b>해 Notion에 쌓습니다. 이 페이지는 돌아간다는 사실보다 <b>무엇을 재어 봤고, 무엇을 발견했는지</b>를 보여 줍니다.",
    "Ten scheduled cloud routines <b>research → verify → summarize</b> 14 assets into Notion. This page is less about the fact that it runs and more about <b>what was measured and what turned up</b>.")}</p>
  <div class="kp">
    <div><span class="k">{T("검증 검출률", "verifier recall")}</span><span class="v c-cy">{recall_full}</span><span class="c">{T(f"처음 보는 행 {recall_hold} · 오탐 0", f"unseen rows {recall_hold} · 0 false alarms")}</span></div>
    <div><span class="k">{T("예약 실행", "scheduled runs")}</span><span class="v c-up">{ops['scheduled_success']}<small>/{ops['scheduled_runs']}</small></span><span class="c">{T(f"시작 지연 중앙값 {ops['start_delay_min_median']}분", f"median start delay {ops['start_delay_min_median']} min")}</span></div>
    <div><span class="k">{T("가드레일 뒤 위반", "violations after fix")}</span><span class="v c-up">0</span><span class="c">{T(f"적용 전 {viol_before}건", f"{viol_before} before")}</span></div>
    <div><span class="k">{T("낙폭 줄인 자산", "lower drawdown")}</span><span class="v c-amb">{shallow}<small>/{n_assets}</small></span><span class="c">{T(f"수익 우위는 {beat}/{n_assets}", f"higher return only {beat}/{n_assets}")}</span></div>
    <div><span class="k">{T("재계산 일치", "recomputed match")}</span><span class="v c-vi">{ev_match}<small>/{len(ev_db)}</small></span><span class="c">{T("이벤트 반응 행", "event reaction rows")}</span></div>
  </div>
  <p class="note">{T(f"스냅숏 {snap} · 운영 데이터 이틀치 초기값 · 투자 권유 아님", f"snapshot {snap} · two days of ops data, early numbers · not investment advice")}</p>
</header>

<section id="arch">
  <div class="sh"><span class="idx">01 / {T("구조", "architecture")}</span><h2>{T("하루 여섯 번, 사람 없이 돕니다", "Six runs a day, no human in the loop")}</h2>
  <p>{T("담당은 원출처에서 값을 모으고, 검증은 담당이 쓴 숫자를 믿지 않고 <b>원출처에서 다시 받아 다시 계산</b>합니다. 규칙은 버전 관리되는 프롬프트 파일에 있고, 배포한 뒤 저장본을 원본과 글자 단위로 대조합니다.",
    "Desks collect values from the source. The verifier doesn't trust them — it <b>refetches and recomputes</b>. Rules live in versioned prompt files, and the deployed prompt is diffed character-by-character against source.")}</p></div>
  <div class="win"><div class="wt"><span>crontab · KST</span><span>00:00 ─ 24:00</span></div><div class="wb">
    <div class="dayw"><div class="day"><div class="axis"></div>{hours}{sched_html}</div></div>
    <p class="note">{T("+ 토 09:30 주간 브리핑(Opus) · 매월 1일 09:30 월간 브리핑 · 다음 날 07:40 검증 담당이 브리핑 숫자를 다시 계산", "+ Sat 09:30 weekly brief (Opus) · 1st of month 09:30 monthly brief · verified next morning at 07:40")}</p>
  </div></div>
  <div class="pipe">
    <div><span class="pn">[1] research</span><h3>{T("조사", "Research")}</h3><ul><li><code>stock</code> <code>etf</code> <code>crypto</code> · {T("해외 10종목", "10 global assets")}</li><li><code>kr-desk</code> · {T("국내 4종목", "4 Korean stocks")}</li><li>{T("종목당 한 행, 출처·조회 시각 필수", "one row per asset, source + fetch time")}</li></ul></div>
    <div><span class="pn">[2] verify</span><h3>{T("검증", "Verify")}</h3><ul><li>{T("가격·이동평균·ATR 재계산", "recompute price · MA · ATR")}</li><li>{T("태그·뉴스 게재일·판단 규칙 대조", "check tags · news dates · rule")}</li><li>PASS · WARNING · ERROR</li></ul></div>
    <div><span class="pn">[3] summarize</span><h3>{T("요약", "Summarize")}</h3><ul><li>{T("일간·주간·월간 브리핑", "daily · weekly · monthly briefs")}</li><li>{T("가치 지표 리포트, 검산 5종", "valuation report, 5 self-checks")}</li><li>{T("다음 날 다시 검증", "re-verified next day")}</li></ul></div>
    <div><span class="pn">[4] events</span><h3>{T("이벤트", "Events")}</h3><ul><li>{T("실적·FOMC·CPI·고용 달력", "earnings · FOMC · CPI · jobs")}</li><li>{T("발표 시점 = SEC 8-K 접수 시각", "timing = SEC 8-K acceptance")}</li><li>{T("D+1·D+5 반응 측정", "D+1 · D+5 reaction")}</li></ul></div>
  </div>
</section>

<section id="eval">
  <div class="sh"><span class="idx">02 / eval</span><h2>{T("검증 담당은 오류를 얼마나 잡나", "How much does the verifier actually catch?")}</h2></div>
  <div class="ev">
    <div class="evl">
      <p class="bigq">{T(esc(E["headline"]), esc(E["headline_en"]))}</p>
      <div class="win"><div class="wt"><span>eval/REPORT.md · F01–F20</span><span>claude-sonnet-5 · 96 calls · $4.99</span></div><div class="wb">
      <table class="evt"><thead><tr><th>{T("판본", "variant")}</th><th>{T("검출률", "recall")}</th><th>{T("오탐", "false alarm")}</th><th>{T("일치", "severity")}</th></tr></thead><tbody>{eval_rows}</tbody></table></div></div>
      <div class="win"><div class="wt"><span>holdout H01–H08 · {T("규칙을 고친 뒤 새로 만든 행", "written after the patch")}</span><span>{T("과적합 점검", "overfit check")}</span></div><div class="wb">
      <table class="evt"><thead><tr><th>{T("판본", "variant")}</th><th>{T("검출률", "recall")}</th><th>{T("겨냥 유형", "targeted")}</th><th>{T("오탐", "false alarm")}</th></tr></thead><tbody>{hold_rows}</tbody></table></div></div>
      <p class="note">{T(esc(E["note"]), esc(E["note_en"]))}</p>
    </div>
    <div class="win"><div class="wt"><span>F01–F20 · H01–H08</span><span>A = ablated · 1 = v1 · 2 = v2</span></div><div class="wb">
      <div class="gh2 g3"><span>id</span><span>asset</span><span>{T("심은 결함", "planted defect")}</span><span>A</span><span>1</span><span>2</span></div>
      <div class="grid">{grid_html}</div>
      <div class="gh2 g2" style="margin-top:14px"><span>id</span><span>asset</span><span>holdout</span><span>1</span><span>2</span></div>
      <div class="grid">{hgrid_html}</div>
      <div class="leg"><span><b class="gc hit">●</b>{T("잡음", "caught")}</span><span><b class="gc miss">○</b>{T("놓침", "missed")}</span><span><b class="gc ok">✓</b>{T("정상 통과", "clean pass")}</span><span><b class="gc fa">!</b>{T("오탐", "false alarm")}</span></div>
    </div></div>
  </div>
  <div class="win"><div class="wt"><span>Market Daily · {T("실제 운영 판정", "production verdicts")}</span><span>22 rows</span></div><div class="wb">
    <div class="vl">{vbars}</div>
    <div class="leg"><span><b class="gc" style="background:var(--up)"></b>PASS</span><span><b class="gc" style="background:var(--amb)"></b>WARNING</span><span><b class="gc" style="background:var(--dn)"></b>ERROR</span></div>
    <p class="note">{T("9/26 ERROR 4건은 수치가 아니라 출처 표기 누락과 뉴스 게재일 오기였고, 규칙을 고친 다음 날 행은 모두 PASS였습니다.", "The four ERRORs on 9/26 were a missing source note and a wrong news date, not numbers; after the rule fix, next-day rows all passed.")}</p>
  </div></div>
</section>

<section id="ops">
  <div class="sh"><span class="idx">03 / {T("운영", "operations")}</span><h2>{T("사고는 규칙 문장이 아니라 권한과 검사로 막았다", "Incidents were closed with permissions and checks, not more prose")}</h2>
  <p>{T(f"루틴 실행 {ops['runs_total']}회를 장부로 모았습니다({ops['runs_log_read']}회는 로그 전체 확인). 적용 뒤 표본은 작아서 '재발 없음'이 아니라 '아직 관측되지 않음'으로 읽어야 합니다.",
    f"{ops['runs_total']} routine runs went into a ledger ({ops['runs_log_read']} logs read in full). The post-fix sample is small: read it as 'not yet observed', not 'never again'.")}</p></div>
  <div class="diffs">{diffs}</div>
  <div class="win"><div class="wt"><span>tail -n {len(runs)} metrics/runs.jsonl</span><span>KST</span></div><div class="wb log">{"".join(log_lines)}</div></div>
  <div class="stats">
    <div><b>47</b><span>{T("분류한 이슈 (09-24~27)", "issues classified (09-24~27)")}</span></div>
    <div><b>55%</b><span>{T("검증 담당이 먼저 잡음 (발견자 확인 33건)", "caught first by the verifier (33 with known finder)")}</span></div>
    <div><b>39%</b><span>{T("규칙을 적은 뒤에도 재발 (13/33)", "recurred after a rule was written (13/33)")}</span></div>
    <div><b>12/13</b><span>{T("재발을 드러낸 것: 검증의 재계산·대조", "recurrences exposed by recompute & cross-check")}</span></div>
  </div>
  <p>{T(esc(inp["issues"]["summary"]), esc(inp["issues"]["summary_en"]))}</p>
  <div class="win"><div class="wt"><span>git log --incidents</span><span>{len(inp['incidents'])} commits</span></div><div class="gitlog">{glog}</div></div>
</section>

<section id="find">
  <div class="sh"><span class="idx">04 / {T("발견", "findings")}</span><h2>{T("판단 규칙은 수익 신호가 아니라 위험 관리 도구였다", "The trading rule was a risk control, not a return signal")}</h2>
  <p>{T(f"매일의 판단 뒤 60일을 겹쳐 세면 <b>'비중 축소' 뒤가 가장 좋아</b> 규칙이 거꾸로 작동하는 것처럼 보였습니다. 겹치지 않는 창으로 다시 뽑자 차이는 신뢰구간 안에서 사라졌습니다. 규칙을 비중으로 쓰면 수익은 {n_assets - beat}개 자산에서 줄었지만 낙폭은 {shallow}개 자산에서 얕아졌습니다.",
    f"Counting overlapping 60-day windows made <b>'REDUCE' look like the best entry</b> — as if the rule worked backwards. With non-overlapping windows the gap vanished inside the confidence intervals. Used as position sizing, the rule lowered return on {n_assets - beat} assets but reduced max drawdown on {shallow}.")}</p></div>
  <div class="win"><div class="wt"><span>{T("최대 낙폭 · 보유 vs 규칙", "max drawdown · hold vs rule")}</span><span>2025-01 → 2026-09</span></div><div class="wb ch">{mdd_chart()}</div></div>
  <div class="two">
      <div class="win"><div class="wt"><span>{T("판단별 60일 뒤 · 90% 구간", "60d forward · 90% CI")}</span><span>bootstrap 2000</span></div><div class="wb ch">{ci_chart()}</div></div>
      <div class="win"><div class="wt"><span>{T("실적 다음 날 움직임 ÷ 평소 하루", "day-after-earnings move ÷ typical day")}</span><span>US · KR</span></div><div class="wb ch">{ratio_chart()}</div></div>
  </div>
  <p class="note">{T(f"비중 = 관심 100% · 관망 50% · 비중 축소 0%, 거래 비용 0. 사후 점검이며 표본 밖 성과는 2026-09-26부터 따로 쌓습니다. 미국 종목은 실적 다음 날 평소 하루의 {us[-1][1]:.1f}~{us[0][1]:.1f}배를 움직였지만 방향은 일정하지 않아, 이벤트 전날 브리핑은 방향이 아니라 흔들림의 크기를 알립니다.",
    f"Sizing = WATCH 100% · HOLD 50% · REDUCE 0%, zero costs. In-sample check; out-of-sample tracking started 2026-09-26. US names moved {us[-1][1]:.1f}–{us[0][1]:.1f}× a typical day after earnings with no consistent direction, so the pre-event brief flags the size of the move, not its sign.")}</p>
  <details><summary>{T("자산별 수익률·낙폭 표", "per-asset return & drawdown table")}</summary><div class="tb"><table class="st"><thead><tr><th>asset</th><th>hold</th><th>rule</th><th>Δpp</th><th>hold MDD</th><th>rule MDD</th><th>exposure</th></tr></thead><tbody>{sig_rows}</tbody></table></div></details>
</section>

<section id="roles">
  <div class="sh"><span class="idx">05 / {T("한 일", "what I did")}</span><h2>{T("직무별로 보면", "By role")}</h2></div>
  <div class="roles">{roles}</div>
</section>

<section>
  <div class="sh"><span class="idx">06 / {T("한계", "limits")}</span><h2>{T("아직 말할 수 없는 것", "What this can't claim yet")}</h2></div>
  <ul class="lim">
    <li>{T("운영 데이터가 이틀치입니다. 성공률과 재발 여부는 아직 다시 재지 않았습니다.", "Two days of operations data; success and recurrence have not been re-measured yet.")}</li>
    <li>{T("평가 세트는 20행+holdout 8행이라 결함 1건이 8~17%p입니다. 문장 판정은 같은 계열 모델이 합니다.", "The eval set has 20 + 8 holdout rows (one defect = 8–17 pp), and sentence-level judgments come from the same model family.")}</li>
    <li>{T("토큰·비용은 실행 로그에 나오지 않아 재지 못했습니다.", "Token cost isn't exposed in run logs, so it wasn't measured.")}</li>
    <li>{T("가격 일부는 비공식 경로에서 받았고, 모든 행에 그 사실을 적습니다. 투자 권유가 아닙니다.", "Some prices come from unofficial endpoints, flagged on every row. Not investment advice.")}</li>
  </ul>
</section>
{pos_section}<footer>{T("수치", "data")}: metrics/ops_metrics.json · runs.jsonl · verdicts.jsonl · signal_eval.json · events_study.csv · issues_summary.md · eval/REPORT.md — {T("생성", "built by")} docs/build_case_study.py · <a href="https://github.com/ejmogly/market-watch">github.com/ejmogly/market-watch</a></footer>
</main>
<script type="application/json" id="px-data">__PXDATA__</script>
<script type="application/json" id="px-demo">[]</script>
<script>
{POSJS}
</script>
<script>
(function(){{
  var root=document.documentElement,btn=document.getElementById('lang');
  function set(l){{root.setAttribute('data-lang',l);root.setAttribute('lang',l);try{{localStorage.setItem('mw-lang',l)}}catch(e){{}}}}
  var saved=null;try{{saved=localStorage.getItem('mw-lang')}}catch(e){{}}
  set(saved==='en'?'en':'ko');
  btn.addEventListener('click',function(){{set(root.getAttribute('data-lang')==='en'?'ko':'en')}});
}})();
</script>
"""
full_payload = jsd({"asof": px_asof, "assets": px_full or px_lite, "fx": fx_full})
lite_payload = jsd({"asof": px_asof, "assets": px_lite, "fx": fx_lite})
(ROOT / "docs" / "case_study.html").write_text(page.replace("__PXDATA__", full_payload))
page = page.replace("__PXDATA__", lite_payload)
head, body = page.split('<div class="bar">', 1)
standalone = ('<!doctype html>\n<html lang="ko" data-lang="ko">\n<head>\n<meta charset="utf-8">\n'
              '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
              '<meta name="description" content="Ten AI agents research the market daily and recompute each other\'s numbers — eval set, run ledger, guardrails and findings.">\n'
              + head + '</head>\n<body>\n<div class="bar">' + body + '</body>\n</html>\n')
(ROOT / "docs" / "index.html").write_text(standalone)
# ---------- 로컬 전용: private/trades.csv → private/positions.html (공개·아티팩트로 나가지 않음) ----------
TR = ROOT / "private" / "trades.csv"
if TR.exists() and px_full:
    mine = []
    for i, r in enumerate(csv.DictReader(open(TR, encoding="utf-8"))):
        x = {k: v.strip() for k, v in r.items() if k and v and v.strip()}
        for k in ("qty", "price", "amount", "fee"):
            if k in x:
                x[k] = float(x[k].replace(",", ""))
        x["created"] = f"{i:04d}"
        mine.append(x)
    head_local = head.replace("<title>market-watch 사례 연구</title>", "<title>내 포지션</title>")
    local = ('<!doctype html>\n<html lang="ko" data-lang="ko">\n<head>\n<meta charset="utf-8">\n'
             '<meta name="viewport" content="width=device-width, initial-scale=1">\n' + head_local
             + '</head>\n<body>\n<main class="w">' + pos_section + '</main>\n'
             + '<script>window.MW_LOCAL = true;</script>\n'
             + f'<script type="application/json" id="px-data">{full_payload}</script>\n'
             + f'<script type="application/json" id="px-demo">{jsd(mine)}</script>\n<script>\n{POSJS}\n</script>\n</body>\n</html>\n')
    out = ROOT / "private" / "positions.html"
    out.write_text(local)
    out.chmod(0o600)
    print("local", out, len(mine), "trades")
print("ok", len(page), "grid", len(grid), "log", len(log_lines), "tick", len(tick))

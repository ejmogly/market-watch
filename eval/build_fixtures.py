"""검증 담당 평가용 fixture 20건을 만든다 (정상 8 · 결함 12).

실제 가격 이력(data/prices_*.json)과 실제 행(output/*_2026-09-2*.md)의 뉴스·목표가로
규칙(routines/_common.md)을 모두 지킨 정상 행을 만들고, 결함 행은 정상 행에 결함 하나만 심는다.
각 fixture에는 오프라인 판정용 `원자료` 블록(가격 이력 발췌·재계산값·원출처 표기값·뉴스 원문 게재일)을 넣는다.

사용법: python3 eval/build_fixtures.py   → eval/fixtures/F01.md ~ F20.md, eval/labels.json
"""

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "eval"
T = lambda tag: f' <span color="gray">({tag})</span>'
DISCLAIMER = "참고용 시나리오이며 투자 판단과 책임은 본인에게 있습니다."

# ---------------------------------------------------------------- 원자료 읽기

def load_bars(asset):
    f = {"BTC": "prices_BTC_2026-09-25.json", "ETH": "prices_ETH_2026-09-25.json"}.get(asset, f"prices_{asset}_2026-09-24.json")
    d = json.load(open(ROOT / "data" / f))
    bars = d.get("bars") or d.get("rows") or d.get("candles")
    bars = [{"date": b["date"], "high": float(b["high"]), "low": float(b["low"]), "close": float(b["close"])} for b in bars]
    return d, bars


def indicators(bars):
    closes = [b["close"] for b in bars]
    ma = lambda n: sum(closes[-n:]) / n if len(closes) >= n else None
    tr = [max(b["high"] - b["low"], abs(b["high"] - p["close"]), abs(b["low"] - p["close"])) for p, b in zip(bars, bars[1:])]
    atr = sum(tr[:14]) / 14
    for x in tr[14:]:
        atr = (atr * 13 + x) / 14
    return {"n": len(bars), "ma20": ma(20), "ma50": ma(50), "ma200": ma(200), "atr": atr,
            "hi52": max(b["high"] for b in bars[-252:]), "lo52": min(b["low"] for b in bars[-252:])}


def unit(asset, price):
    return {"BTC": 100.0, "ETH": 10.0}.get(asset, 1.0 if price >= 100 else 0.1)


def floor_u(x, u):
    return math.floor(round(x / u, 9)) * u


def ceil_u(x, u):
    return math.ceil(round(x / u, 9)) * u


def money(x, u):
    if u >= 1:
        return f"{x:,.0f}달러"
    return f"{x:,.1f}달러"


def num(x, d=2):
    return f"{x:,.{d}f}"


def stop_txt(x, u):
    """손절 식 결과 표시. 소수 둘째 자리 표시값을 내림한 결과가 실제 내림과 다르면(예: 323.9989 → 324.00) 넷째 자리까지 쓴다."""
    return num(x) if floor_u(round(x, 2), u) == floor_u(x, u) else num(x, 4)

# ---------------------------------------------------------------- 자산별 고정 자료 (실제 행에서 옮김)

META = {
    "VOO": dict(kind="ETF", desk="etf-desk", name="Vanguard S&P 500 ETF"),
    "QQQM": dict(kind="ETF", desk="etf-desk", name="Invesco NASDAQ 100 ETF"),
    "SMH": dict(kind="ETF", desk="etf-desk", name="VanEck Semiconductor ETF"),
    "GOOGL": dict(kind="주식", desk="stock-desk", name="Alphabet Class A", target=429.46),
    "NVDA": dict(kind="주식", desk="stock-desk", name="NVIDIA", target=327.70),
    "TSLA": dict(kind="주식", desk="stock-desk", name="Tesla", target=396.94),
    "SpaceX": dict(kind="주식", desk="stock-desk", name="SpaceX (SPCX)", target=222.42, ticker="SPCX"),
    "BTC": dict(kind="크립토", desk="crypto-desk", name="Bitcoin", ticker="BTC-USD"),
    "ETH": dict(kind="크립토", desk="crypto-desk", name="Ethereum", ticker="ETH-USD"),
}

NEWS = {
    "VOO": [("2026-09-23", "Yahoo Finance", "10-year Treasury yield hits highest level since 2007 as market prices in another Fed rate hike",
             "미국 10년물 국채 금리가 5.12%까지 올라 2007년 이후 최고치를 기록했다고 보도했다.", "https://finance.yahoo.com/news/10-year-treasury-yield-2007-fed-rate-hike"),
            ("2026-09-21", "The Motley Fool", "History Says You Should Know These 3 Things Before Buying the Vanguard S&P 500 ETF (VOO) in September",
             "VOO 상위 10종목 비중이 38%로 집중도가 높다고 짚었다.", "https://www.fool.com/investing/2026/09/21/vanguard-sp-500-etf-voo-september/")],
    "QQQM": [("2026-09-22", "Reuters", "Nasdaq hits intraday record high as tech stocks regain footing",
              "나스닥 종합지수가 장중 27,212.68로 사상 최고치를 새로 썼다고 보도했다.", "https://www.investing.com/news/stock-market-news/nasdaq-hits-intraday-record-high"),
             ("2026-09-21", "Semafor", "AMD reaches a $1 trillion market cap as chip stocks drive rally",
              "AMD가 미국 반도체 기업 가운데 네 번째로 시가총액 1조 달러를 넘었다고 보도했다.", "https://www.semafor.com/article/09/21/2026/amd-1-trillion-market-cap")],
    "SMH": [("2026-09-24", "StockStory", "Lam Research, Marvell Technology, Western Digital, FormFactor, and Penguin Solutions Shares Are Falling, What You Need To Know",
             "10년물 국채 금리가 5.14%로 오르며 반도체주가 내렸다고 보도했다.", "https://finance.yahoo.com/news/lam-research-marvell-western-digital-falling"),
            ("2026-09-21", "Semafor", "AMD reaches a $1 trillion market cap as chip stocks drive rally",
             "AMD가 시가총액 1조 달러를 넘었다고 보도했다.", "https://www.semafor.com/article/09/21/2026/amd-1-trillion-market-cap")],
    "GOOGL": [("2026-09-24", "TechCrunch", "Waymo is scaling fast: Here’s what the fleet data shows",
               "웨이모가 미국 15개 도시에서 로보택시 약 4,000대를 운영한다고 보도했다.", "https://techcrunch.com/2026/09/24/waymo-is-scaling-fast/"),
              ("2026-09-24", "TechCrunch", "Google tests letting Gemini call businesses for you",
               "구글이 제미나이가 사용자 대신 업체에 전화를 거는 기능을 시험한다고 보도했다.", "https://techcrunch.com/2026/09/24/google-tests-gemini-call-businesses/")],
    "NVDA": [("2026-09-23", "Invezz", "Why Nvidia stock is down around 2% after a six-day rally",
              "엔비디아 주가가 9월 23일 2% 넘게 내려 6거래일 연속 상승이 끊길 상황이라고 보도했다.", "https://invezz.com/news/2026/09/23/why-nvidia-stock-is-down/"),
             ("2026-09-22", "CNBC", "Nvidia options are doing something unusual ahead of two catalysts. Here's how one trader is playing it",
              "엔비디아 옵션의 내재변동성이 최근 1년 중 가장 낮은 수준 근처라고 전했다.", "https://www.cnbc.com/2026/09/22/nvidia-options-unusual-ahead-of-catalysts.html")],
    "TSLA": [("2026-09-24", "CNBC", "Tesla poised to scale production of heavy-duty Semi trucks with opening of Nevada factory",
              "테슬라가 네바다주에서 대형 전기 트럭 세미의 첫 대량 생산 공장을 열었다고 보도했다.", "https://www.cnbc.com/2026/09/24/tesla-semi-nevada-factory.html"),
             ("2026-09-22", "CNBC", "Tesla makes a move on Southeast Asia's largest EV market. A homegrown giant awaits",
              "테슬라가 이달 베트남 현지 법인을 등록했다고 보도했다.", "https://www.cnbc.com/2026/09/22/tesla-vietnam-ev-market.html")],
    "SpaceX": [("2026-09-24", "Invezz", "SpaceX stock falls as 328 million shares unlock: is more selling coming?",
                "매도가 제한됐던 주식 약 3억 2,800만 주가 매도 가능해지면서 SPCX가 장전 거래에서 내렸다고 보도했다.", "https://invezz.com/news/2026/09/24/spacex-stock-falls-shares-unlock/"),
               ("2026-09-23", "TipRanks", "SpaceX (SPCX) President Sells More Than $50 Million of Company Stock",
                "그윈 숏웰 사장이 9월 22일 34만 2,170주를 매도했다고 전했다.", "https://www.tipranks.com/news/insider-trading/spacex-spcx-president-sells")],
    "BTC": [("2026-09-24", "Yahoo Finance", "Bitcoin and ethereum prices today, Thursday, September 24, 2026: Crypto prices lose ground as rate-hike expectations grow",
             "비트코인이 이날 84,370.41달러에 출발해 전날 시가보다 2.1% 낮았다고 전했다.", "https://finance.yahoo.com/news/bitcoin-ethereum-prices-today-september-24-2026"),
            ("2026-09-23", "BeInCrypto", "Bitcoin Is Up 13% Since the Fed Hike. Here's Why the Funds That Sold Came Back",
             "9월 16일 연준의 금리 인상 뒤 비트코인이 약 13% 올랐다고 전했다.", "https://beincrypto.com/bitcoin-up-13-since-fed-hike/")],
    "ETH": [("2026-09-24", "Yahoo Finance", "Bitcoin and ethereum prices today, Thursday, September 24, 2026: Crypto prices lose ground as rate-hike expectations grow",
             "이더리움 가격이 금리 인상 기대 속에 내렸다고 전했다.", "https://finance.yahoo.com/news/bitcoin-ethereum-prices-today-september-24-2026"),
            ("2026-09-23", "CoinDesk", "Ether holds above $2,650 as staking inflows climb",
             "이더리움 스테이킹 유입이 늘었다고 보도했다.", "https://www.coindesk.com/markets/2026/09/23/ether-holds-above-2650")],
}

# ---------------------------------------------------------------- 정상 행 만들기


def build_row(asset):
    m = META[asset]
    raw, bars = load_bars(asset)
    crypto = m["kind"] == "크립토"
    if crypto:
        calc = bars  # 완료 일봉(마지막 = 9/24 UTC)
        price = float(raw["partial"]["close"])
        prev_close = calc[-1]["close"]
        base_time = "2026-09-25T14:20:00+09:00"
        base_label = "2026-09-25 14:20 KST(가격 조회 시각)"
    else:
        calc = bars
        price = calc[-1]["close"]
        prev_close = calc[-2]["close"]
        base_time = "2026-09-25T05:00:00+09:00"
        base_label = "2026-09-24 뉴욕 16:00 종가(= 2026-09-25 05:00 KST)"
    ind = indicators(calc)
    if crypto:  # 52주 범위는 부분 봉 포함
        ind["hi52"] = max(ind["hi52"], float(raw["partial"]["high"]))
        ind["lo52"] = min(ind["lo52"], float(raw["partial"]["low"]))
    chg = (price / prev_close - 1) * 100
    u = unit(asset, price)
    pos = (price - ind["lo52"]) / (ind["hi52"] - ind["lo52"]) * 100
    fifty_mode = ind["ma200"] is None  # 상장 200거래일 미만
    long_ma, mid_ma = (ind["ma50"], ind["ma20"]) if fifty_mode else (ind["ma200"], ind["ma50"])
    long_nm, mid_nm = ("50일선", "20일선") if fifty_mode else ("200일선", "50일선")
    if price >= long_ma and mid_ma >= long_ma:
        judg = "관심"
    elif price < long_ma and mid_ma < long_ma:
        judg = "비중 축소"
    else:
        judg = "관망"
    r = dict(asset=asset, meta=m, bars=calc, raw=raw, price=price, prev_close=prev_close, chg=chg, ind=ind, u=u, pos=pos,
             judg=judg, fifty=fifty_mode, long_ma=long_ma, mid_ma=mid_ma, long_nm=long_nm, mid_nm=mid_nm,
             base_time=base_time, base_label=base_label, crypto=crypto)
    # 구간
    if judg == "관심":
        lo_raw, hi_raw = min(ind["ma20"], ind["ma50"]), max(ind["ma20"], ind["ma50"])
        lo_nm = "20일선" if ind["ma20"] <= ind["ma50"] else "50일선"
        hi_nm = "50일선" if lo_nm == "20일선" else "20일선"
        r["buy"] = (lo_raw, hi_raw, lo_nm, hi_nm, floor_u(lo_raw, u), ceil_u(hi_raw, u))
        r["stop_raw"] = lo_raw - 2 * ind["atr"]
        r["stop"] = floor_u(r["stop_raw"], u)
    elif judg == "관망":
        lo_raw, hi_raw = long_ma, long_ma + ind["atr"]
        r["buy"] = (lo_raw, hi_raw, long_nm, f"{long_nm}+1 ATR", floor_u(lo_raw, u), ceil_u(hi_raw, u))
        r["stop_raw"] = lo_raw - 2 * ind["atr"]
        r["stop"] = floor_u(r["stop_raw"], u)
    else:
        r["buy"] = None
    if m["kind"] == "주식":
        t = m["target"]
        lo_t, hi_t = min(ind["hi52"], t), max(ind["hi52"], t)
        r["take"] = (lo_t, hi_t, floor_u(lo_t, u), ceil_u(hi_t, u))
        r["target_gap"] = (t / price - 1) * 100
    else:
        lo_t, hi_t = ind["hi52"], ind["hi52"] + 2 * ind["atr"]
        r["take"] = (lo_t, hi_t, floor_u(lo_t, u), ceil_u(hi_t, u))
    return r


def sources(r, unofficial=True, short_title=None):
    a = r["asset"]
    tk = r["meta"].get("ticker", a)
    tag = " (비공식 경로)" if unofficial else ""
    lines = [f"1. Yahoo Finance chart API — https://query1.finance.yahoo.com/v8/finance/chart/{tk}?range=2y&interval=1d — 조회 2026-09-25 14:10 KST — 가격·1년 일봉{tag}",
             f"2. Yahoo Finance 시세 페이지 — https://finance.yahoo.com/quote/{tk}/ — 조회 2026-09-25 14:11 KST — 종가·등락률 대조"]
    n = 3
    if r["meta"]["kind"] == "주식":
        lines.append(f"{n}. stockanalysis 개요 페이지 — https://stockanalysis.com/stocks/{tk.lower()}/ — 조회 2026-09-25 14:12 KST — 애널리스트 목표가 평균")
        n += 1
    for i, (d, media, title, _, url) in enumerate(r["news"]):
        tt = short_title if (short_title and i == 0) else title
        lines.append(f'{n}. {media} — "{tt}" — {url} — 조회 2026-09-25 14:15 KST')
        n += 1
    return lines


def render(r, mutate=None):
    """정상 행을 텍스트로 만든다. mutate(dict)는 결함 주입용 훅."""
    mz = mutate or {}
    a, ind, u = r["asset"], r["ind"], r["u"]
    P = lambda x: money(x, u)
    ma200_txt = "없음(상장 {}거래일)".format(ind["n"]) if r["fifty"] else f"{num(ind['ma200'])}달러"
    # --- 본문
    body = ["## 요약"]
    body.append(f"{a}의 기준 가격은 {num(r['price'])}달러다.{T('확인')}")
    body.append(f"전일 대비 등락률은 {r['chg']:+.2f}%다.{T('확인')}")
    body.append(mz.get("summary3", f"52주 위치는 {r['pos']:.1f}%다.{T('산출')}"))
    body.append("## 지표")
    rows = [("기준 가격", f"{num(r['price'])}달러", "기준 시각의 가격", "확인"),
            ("전일 대비 등락률", f"{r['chg']:+.2f}%", "하루 사이 움직임", "확인"),
            ("20일선", f"{num(ind['ma20'])}달러", "최근 20거래일 종가 평균", "산출"),
            ("50일선", f"{num(mz.get('ma50_shown', ind['ma50']))}달러", "최근 50거래일 종가 평균", "산출"),
            ("200일선", ma200_txt if not mz.get("ma200_shown") else f"{num(mz['ma200_shown'])}달러", "최근 200거래일 종가 평균(장기 추세)", "산출"),
            ("ATR(14)", f"{num(ind['atr'])}달러", "하루에 보통 움직이는 폭", "산출"),
            ("52주 최고 / 최저", f"{num(ind['hi52'])}달러 / {num(ind['lo52'])}달러", "최근 1년 가장 높았던·낮았던 가격(가격 이력 고가·저가)", "산출"),
            ("52주 위치", f"{r['pos']:.1f}%", "0%는 1년 최저, 100%는 1년 최고", "산출")]
    if r["meta"]["kind"] == "주식":
        rows.append(("애널리스트 목표가 평균", f"{num(r['meta']['target'])}달러", "증권사 분석가 12개월 목표 주가의 평균", "확인"))
    if "easy_override" in mz:
        i, txt = mz["easy_override"]
        rows[i] = (rows[i][0], rows[i][1], txt, rows[i][3])
    body.append('<table header-row="true">')
    body.append("\t<tr><td>지표</td><td>값</td><td>쉽게 말하면</td><td>태그</td></tr>")
    for k, v, e, t in rows:
        body.append(f'\t<tr><td>{k}</td><td>{v}</td><td>{e}</td><td><span color="gray">({t})</span></td></tr>')
    body.append("</table>")
    body.append("## 뉴스")
    for i, (d, media, title, summ, _) in enumerate(r["news"]):
        dd = mz.get("news_date", {}).get(i, d)
        body.append(f'- {dd} · {media} · "{title}" — {summ}{T("보도")}')
    body.append("## 그래서 어떻게 볼까")
    lm, mm = r["long_ma"], mz.get("mid_ma_shown", r["mid_ma"])
    body.append(f"- 가격 {num(r['price'])}달러는 {r['long_nm']} {num(lm)}달러 {'이상' if r['price'] >= lm else '미만'}이다.{T('계산')}")
    body.append(f"- {r['mid_nm']} {num(mm)}달러는 {r['long_nm']} {'이상' if mm >= lm else '미만'}이다.{T('계산')}")
    judg = mz.get("judg", r["judg"])
    extra = f" (상장 {ind['n']}거래일, 50일선 기준)" if r["fifty"] else ""
    body.append(mz.get("judg_line", f"- **한 줄 판단: {judg}**{extra} — 위 두 조건에 따라 판단 규칙상 {judg}{'로' if judg.endswith('소') else '으로'} 본다.{T('의견')}"))
    if r["buy"]:
        lo_raw, hi_raw, lo_nm, hi_nm, lo, hi = r["buy"]
        cond = f"가격이 {r['long_nm']} 위로 마감하면 " if r["judg"] == "관망" else ""
        body.append(f"- **분할 매수 검토 구간:** {cond}{P(lo)}({lo_nm} {num(lo_raw)} → {u:g}달러 단위 내림) ~ {P(hi)}({hi_nm} {num(hi_raw)} → {u:g}달러 단위 올림).{T('의견')}")
    else:
        body.append(f"- **분할 매수 검토 구간:** 신규 매수 검토 안 함.{T('의견')}")
    lo_t, hi_t, lo_tr, hi_tr = r["take"]
    lo_tr = mz.get("take_lo", lo_tr)
    if r["meta"]["kind"] == "주식":
        lo_src = "52주 최고" if lo_t == ind["hi52"] else "목표가 평균"
        hi_src = "목표가 평균" if lo_src == "52주 최고" else "52주 최고"
        dirn = mz.get("take_lo_dir", "내림")
        body.append(f"- **차익 실현 검토 구간:** {P(lo_tr)}({lo_src} {num(lo_t)} → {u:g}달러 단위 {dirn}) ~ {P(hi_tr)}({hi_src} {num(hi_t)} → {u:g}달러 단위 올림).{T('의견')}")
        gap = r["target_gap"]
        body.append(mz.get("gap_line", f"- 목표가 평균은 가격보다 {gap:.2f}% 높다.{T('계산')}"))
        if gap > 50:
            body.append(f"- 목표가 편차가 커서 하단만 참고한다.{T('의견')}")
    else:
        dirn = mz.get("take_lo_dir", "내림")
        body.append(f"- **차익 실현 검토 구간:** {P(lo_tr)}(52주 최고 {num(lo_t)} → {u:g}달러 단위 {dirn}) ~ {P(hi_tr)}(52주 최고 + 2 ATR {num(hi_t)} → {u:g}달러 단위 올림).{T('의견')}")
    if r["buy"]:
        stop_raw, stop = mz.get("stop_raw", r["stop_raw"]), mz.get("stop", r["stop"])
        base = mz.get("stop_base", r["buy"][0])
        body.append(f"- **생각을 바꿀 조건(손절 기준):** 가격이 {P(stop)} 아래로 마감하면 판단을 다시 본다(분할 매수 구간 하단 {num(base)} − 2 × ATR {num(ind['atr'])} = {stop_txt(stop_raw, u)} → {u:g}달러 단위 내림).{T('의견')}")
    else:
        body.append(f"- **생각을 바꿀 조건:** 가격이 200일선 위로 두 번 연속 마감하면 관망으로 올린다.{T('의견')}")
    for extra_line in mz.get("extra_judgement_lines", []):
        body.append(extra_line)
    body.append("## 용어 풀이")
    terms = [("기준 가격", "주식·ETF는 미국장 종가, 크립토는 가격을 받은 시각의 가격"), ("등락률", "전일 종가 대비 오르내린 비율"),
             ("20일선·50일선·200일선", "최근 20·50·200거래일 종가의 단순 평균"), ("ATR(14)", "하루 가격 변동 폭(True Range)의 14일 와일더 평활 평균"),
             ("52주 위치", "1년 최저를 0%, 최고를 100%로 놓았을 때 지금 가격의 자리"), ("분할 매수", "한 번에 사지 않고 나눠 사는 것"),
             ("차익 실현", "오른 가격에서 팔아 이익을 확정하는 것"), ("손절", "손실이 더 커지기 전에 파는 것")]
    if r["meta"]["kind"] == "주식":
        terms.append(("애널리스트 목표가 평균", "증권사 분석가들이 제시한 12개월 목표 주가의 평균"))
    for k, v in terms:
        body.append(f"- **{k}**: {v}")
    if not mz.get("drop_disclaimer"):
        body.append(DISCLAIMER)
    if "body_replace" in mz:
        body = [mz["body_replace"](line) for line in body]
    # --- 속성
    tk = r["meta"].get("ticker", a)
    basis = [f"1) 가격 {num(r['price'])} {'≥' if r['price'] >= r['long_ma'] else '<'} {r['long_nm']} {num(r['long_ma'])}",
             f"2) {r['mid_nm']} {num(r['mid_ma'])} {'≥' if r['mid_ma'] >= r['long_ma'] else '<'} {r['long_nm']} {num(r['long_ma'])}"]
    if r["fifty"]:
        basis.insert(0, f"상장 {ind['n']}거래일, 50일선 기준")
    props = {
        "제목": f"{a}-2026-09-25-14:25",
        "자산": a, "종류": r["meta"]["kind"], "담당": r["meta"]["desk"],
        "기준 시각": f"{r['base_time']} ({r['base_label']})",
        "가격(USD)": round(r["price"], 2), "등락률(%)": round(r["chg"], 2),
        "주요 지표": f"20일선 {num(ind['ma20'])} · 50일선 {num(ind['ma50'])} · 200일선 {ma200_txt if r['fifty'] else num(ind['ma200'])} · ATR(14) {num(ind['atr'])} · 52주 위치 {r['pos']:.1f}%",
        "뉴스 요약": " / ".join(f"{d} {m}" for d, m, *_ in r["news"]),
        "한 줄 판단": mz.get("prop_judg", judg),
        "판단 근거": "<br>".join(mz.get("basis", basis)),
        "출처": "<br>".join(mz.get("sources", sources(r))),
        "검증": "대기", "실행 방식": "수동",
    }
    # --- 원자료
    last = r["bars"][-16:]
    rawblk = ["## 원자료 (검증 하네스가 원출처에서 받아 둔 값 — 이 블록만 근거로 판정)",
              f"- 원출처 가격: {num(r['price'])} (Yahoo chart API meta, {r['base_label']}) · 전일 종가 {num(r['prev_close'])} · 등락률 {r['chg']:+.2f}%",
              f"- 가격 이력: {r['bars'][0]['date']} ~ {r['bars'][-1]['date']} 일봉 {ind['n']}개 (Yahoo chart API)"
              + (" · 크립토는 완료 UTC 일봉 기준, 기준 가격은 2026-09-25 부분 봉" if r["crypto"] else ""),
              "- 가격 이력으로 python3 재계산한 값(정해진 식 그대로):",
              f"  - 20일선 {ind['ma20']:.4f} · 50일선 {ind['ma50']:.4f} · 200일선 {('없음(종가 ' + str(ind['n']) + '개)') if ind['ma200'] is None else format(ind['ma200'], '.4f')}",
              f"  - ATR(14, 와일더) {ind['atr']:.4f}",
              f"  - 52주 최고 {ind['hi52']:.4f} · 52주 최저 {ind['lo52']:.4f} (가격 이력 고가·저가, 출처 표기값과 같음)",
              "- 최근 16개 일봉 (날짜, 고가, 저가, 종가):"]
    rawblk += [f"  - {b['date']}, {b['high']:.2f}, {b['low']:.2f}, {b['close']:.2f}" for b in last]
    if r["meta"]["kind"] == "주식":
        rawblk.append(f"- 애널리스트 목표가 평균: {num(r['meta']['target'])} (stockanalysis 개요 페이지, 조회 2026-09-25 14:12 KST)")
    rawblk.append("- 뉴스 원문 확인(링크를 열어 확인한 값):")
    for i, (d, media, title, summ, url) in enumerate(r["news"]):
        pub = mz.get("news_pub", {}).get(i, d)
        rawblk.append(f'  - {media} · 원문 제목 "{title}" · 원문 최초 게재일 {pub} · {url} · 요지: {summ}')
    for extra_raw in mz.get("extra_raw", []):
        rawblk.append(extra_raw)
    return props, body, rawblk


def to_markdown(fid, props, body, rawblk):
    out = [f"# fixture {fid}", "", "## 행 속성 (Market Daily)"]
    for k, v in props.items():
        out.append(f"- **{k}**: {v}")
    out += ["", "## 행 본문", ""] + body + [""] + rawblk
    return "\n".join(out) + "\n"

# ---------------------------------------------------------------- 결함 정의


def defects(R):
    D = {}
    # 1) #9 사실 문장에 (의견)
    D["op_tag"] = ("NVDA", dict(gap_line=f"- 목표가 평균은 가격보다 {R['NVDA']['target_gap']:.2f}% 높다.{T('의견')}"),
                   "ERROR", "사실 문장에 (의견) 태그", 9, "목표가 괴리 %는 계산 사실인데 (의견)을 붙임")
    # 2) #13 뉴스 게재일 오기(검색 결과 날짜)
    g = R["GOOGL"]
    D["news_date"] = ("GOOGL", dict(news_override=[("2026-09-21", "Android Authority", "Google's Googlebook laptop: Everything we know so far",
                                                   "구글이 준비 중인 노트북 '구글북'에 대해 알려진 내용을 정리했다.",
                                                   "https://www.androidauthority.com/google-googlebook-laptop-everything-we-know/")],
                                    news_pub={0: "2026-08-19 (2026-09-02 수정, 검색 결과 표시일 2026-09-21)"}),
                      "ERROR", "뉴스 날짜를 검색 결과 날짜로 적음(원문 게재 7일 초과)", 13, "원문 최초 게재일 2026-08-19, 행은 2026-09-21. 기사 제목은 eval용 가상")
    # 3) #2 손절선을 반올림 후 하단으로 계산
    v = R["VOO"]; lo_rounded = v["buy"][4]
    D["stop_rounded"] = ("VOO", dict(stop_base=lo_rounded, stop_raw=lo_rounded - 2 * v["ind"]["atr"], stop=floor_u(lo_rounded - 2 * v["ind"]["atr"], v["u"])),
                         "ERROR", "손절선을 반올림 후 하단으로 계산", 2, f"옳은 값 {v['stop']:.0f}, 행 값 {floor_u(lo_rounded - 2 * v['ind']['atr'], v['u']):.0f}")
    # 4) #12 (비공식 경로) 누락
    D["unofficial"] = ("QQQM", dict(sources=None), "WARNING", "출처 (비공식 경로) 표기 누락", 12, "수치는 모두 맞음")
    # 5) 수치 불일치(50일선) — 이슈 무관 대조군
    s = R["SMH"]
    D["ma_mismatch"] = ("SMH", dict(ma50_shown=s["ind"]["ma50"] - 12.0, mid_ma_shown=s["ind"]["ma50"] - 12.0),
                        "ERROR", "이동평균 수치 불일치", None, "50일선을 재계산값보다 12달러 낮게 적음(판단 라벨은 그대로)")
    # 6) #4 200일선 없는 종목을 판단 보류
    D["no200"] = ("SpaceX", dict(judg_line=f"- **한 줄 판단: 판단 보류** — 200일선이 없어(상장 {R['SpaceX']['ind']['n']}거래일) 판단 규칙을 적용할 수 없다.{T('의견')}",
                                 prop_judg="(비움)"),
                  "ERROR", "200일선 없는 종목 판단 보류", 4, "50일선 기준 대체 규칙을 쓰지 않고 칸을 비움")
    # 7) #10 출처 기사 제목 축약
    D["short_title"] = ("TSLA", dict(short_title="Tesla poised to scale production of Semi trucks"),
                        "WARNING", "출처 칸 기사 제목 축약", 10, "원문 제목 전체와 다름")
    # 8) #11 '쉽게 말하면' 칸에 값
    e = R["ETH"]["ind"]
    D["easy_value"] = ("ETH", dict(easy_override=(6, f"최근 1년 가장 높았던·낮았던 가격. Yahoo 시세 페이지 표기도 {num(e['hi52'])}달러 / {num(e['lo52'])}달러")),
                       "WARNING", "'쉽게 말하면' 칸에 출처별 값", 11, "설명 칸에 수치를 넣음")
    # 9) 판단 밖 단정 — 이슈 무관 대조군
    D["forecast"] = ("BTC", dict(summary3=f"금리 인상 우려가 걷히면 비트코인은 곧 9만 달러를 회복할 것이다.{T('보도')}"),
                     "ERROR", "판단 섹션 밖 전망 단정", None, "요약에 전망 단정(요약 3번째 문장을 바꿈)")
    # 10) 고지 누락 — 이슈 무관 대조군
    D["no_disclaimer"] = ("ETH", dict(drop_disclaimer=True), "ERROR", "고지 문구 누락", None, "")
    # 11) #3 차익 실현 하단을 올림
    q = R["SMH"]
    lo_t = q["take"][0]
    D["take_round"] = ("SMH", dict(take_lo=ceil_u(lo_t, q["u"]), take_lo_dir="올림"),
                       "ERROR", "차익 실현 하단 반올림 방향 오류", 3, f"하단 {lo_t:.2f}를 올림 → {ceil_u(lo_t, q['u']):.0f}")
    # 12) 판단 라벨 규칙 위반 — 이슈 무관 대조군
    D["label"] = ("TSLA", dict(judg="관망", prop_judg="관망"), "ERROR", "한 줄 판단 라벨 규칙 위반", None, "가격<200일선, 50일선<200일선인데 관망")
    return D


def main():
    assets = list(META)
    R = {a: build_row(a) for a in assets}
    for a in assets:
        R[a]["news"] = NEWS[a]
    normal = ["VOO", "QQQM", "SMH", "GOOGL", "NVDA", "TSLA", "SpaceX", "BTC"]
    D = defects(R)
    items = [("normal", a, {}, "PASS", "정상", None, "") for a in normal]
    for key, (a, mz, exp, ft, issue, note) in D.items():
        items.append((key, a, mz, exp, ft, issue, note))
    # 섞는 순서 고정(정답 추측 방지)
    order = [9, 0, 12, 3, 17, 1, 14, 6, 10, 2, 19, 4, 8, 15, 5, 11, 18, 7, 13, 16]
    items = [items[i] for i in order]
    (EVAL / "fixtures").mkdir(parents=True, exist_ok=True)
    labels = []
    for n, (key, a, mz, exp, ft, issue, note) in enumerate(items, 1):
        fid = f"F{n:02d}"
        r = dict(R[a])
        if "news_override" in mz:
            r["news"] = mz["news_override"] + R[a]["news"][1:]
        if mz.get("sources", "x") is None:
            mz = dict(mz, sources=sources(r, unofficial=False))
        elif "short_title" in mz:
            mz = dict(mz, sources=sources(r, short_title=mz["short_title"]))
        props, body, rawblk = render(r, mz)
        (EVAL / "fixtures" / f"{fid}.md").write_text(to_markdown(fid, props, body, rawblk))
        labels.append({"id": fid, "asset": a, "expected": exp, "fault_key": key, "fault_type": ft, "issue_no": issue, "note": note})
    (EVAL / "labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=1))
    for l in labels:
        print(l["id"], l["asset"], l["expected"], l["fault_type"], l["issue_no"])


if __name__ == "__main__":
    main()

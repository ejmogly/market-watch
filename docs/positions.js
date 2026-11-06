/* 07 포지션 — 매수·매도 기록으로 지금 손익을 계산한다.
 * 아티팩트·GitHub Pages: 저장하지 않고 입력한 거래를 그 자리에서 계산만 한다(새로고침하면 사라짐).
 * 로컬 private/positions.html: private/trades.csv가 원본이고 화면 입력칸은 숨긴다(window.MW_LOCAL).
 * 평균 단가는 이동평균법, 수수료·세금은 입력한 수수료만 반영, 통화는 종목 통화 그대로(환율 입력 시 원화 합계 추가). */
(function () {
  'use strict';
  var PX = JSON.parse(document.getElementById('px-data').textContent);
  var DEMO = JSON.parse(document.getElementById('px-demo').textContent);
  var A = PX.assets, NAMES = Object.keys(A);
  var LBL = [['관심', 'WATCH', 'up'], ['관망', 'HOLD', 'amb'], ['비중 축소', 'REDUCE', 'dn']];
  var $ = function (id) { return document.getElementById(id); };

  var state = { mode: 'loading', trades: DEMO.slice(), settings: { fx: null, px: {} } };
  var store = null; // {col, set}

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function t(ko, en) { return '<span class="ko">' + ko + '</span><span class="en">' + en + '</span>'; }
  function num(v) { if (v === '' || v == null) return null; var n = Number(v); return isFinite(n) ? n : null; }
  function today() { var d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); }

  // ---- 가격·환율 조회: date 이하 마지막 거래일 ----
  function find(d, date) {
    var lo = 0, hi = d.length - 1, r = -1;
    while (lo <= hi) { var m = (lo + hi) >> 1; if (d[m] <= date) { r = m; lo = m + 1; } else hi = m - 1; }
    return r;
  }
  function at(a, date) {
    var s = A[a]; if (!s) return null;
    var r = find(s.d, date);
    return r < 0 ? null : { p: s.c[r], d: s.d[r], l: s.l[r] };
  }
  var FX = PX.fx && PX.fx.d && PX.fx.d.length ? PX.fx : null;
  function fxAt(date) { if (!FX) return null; var r = find(FX.d, date); return r < 0 ? null : { r: FX.c[r], d: FX.d[r] }; }
  function fxNow() {
    var o = num(state.settings.fx);
    if (o > 0) return { r: o, d: null };
    return FX ? { r: FX.c[FX.c.length - 1], d: FX.d[FX.d.length - 1] } : null;
  }
  function last(a) { var s = A[a]; return s ? { p: s.c[s.c.length - 1], d: s.d[s.d.length - 1] } : null; }
  function cur(a) { return A[a] ? A[a].cur : 'USD'; }

  // ---- 표기 ----
  function money(v, c) {
    if (v == null || !isFinite(v)) return '—';
    var k = c === 'KRW', o = { minimumFractionDigits: k ? 0 : 2, maximumFractionDigits: k ? 0 : 2 };
    return (v < 0 ? '−' : '') + (k ? '₩' : '$') + Math.abs(v).toLocaleString('en-US', o);
  }
  function signed(v, c) { return v == null || !isFinite(v) ? '—' : (v > 0 ? '+' : '') + money(v, c); }
  function pct(v) { return v == null || !isFinite(v) ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(2) + '%'; }
  function qty(q) { return (+q.toFixed(8)).toLocaleString('en-US', { maximumFractionDigits: 8 }); }
  function tone(v) { return v > 1e-9 ? 'up' : v < -1e-9 ? 'dn' : ''; }
  function rule(code) { var x = LBL[code]; return x ? '<span class="rl ' + x[2] + '">' + t(x[0], x[1]) + '</span>' : '<span class="dim">—</span>'; }

  // ---- 한 거래 풀기: 수량·단가·금액 중 둘이면 나머지 계산, 단가가 없으면 그날 종가(추정) ----
  function resolve(tr) {
    var q = num(tr.qty), p = num(tr.price), m = num(tr.amount), est = false;
    if (p == null && q != null && m != null && q > 0) p = m / q;
    if (p == null) {
      var c = at(tr.asset, tr.date);
      if (!c) return { err: t('그날 종가가 없어 단가를 적어야 합니다', 'no close on file for that date — enter a price') };
      p = c.p; est = true;
    }
    if (q == null && m != null) q = m / p;
    if (!(q > 0) || !(p > 0)) return { err: t('수량·단가·금액 중 둘을 적어 주세요', 'enter two of quantity, price, amount') };
    return { q: q, p: p, est: est };
  }

  // ---- 계산 ----
  function compute() {
    var tr = state.trades.slice().sort(function (x, y) {
      return x.date < y.date ? -1 : x.date > y.date ? 1 : (x.created || '') < (y.created || '') ? -1 : 1;
    });
    var P = {}, rows = [], vNow = state.settings.px.VOO || (last('VOO') || {}).p;
    tr.forEach(function (x) {
      var r = resolve(x), row = { x: x, r: r };
      var c = at(x.asset, x.date);
      row.rule = x.rule != null ? x.rule : c ? c.l : null;
      rows.push(row);
      if (r.err) return;
      var s = P[x.asset] || (P[x.asset] = { a: x.asset, c: cur(x.asset), q: 0, cost: 0, real: 0, inv: 0, proc: 0, vsh: 0, vproc: 0, vok: cur(x.asset) === 'USD' && !!vNow, est: false, realKrw: 0, sales: [] });
      if (r.est) s.est = true;
      var fee = num(x.fee) || 0, v = at('VOO', x.date);
      if (!v) s.vok = false;
      if (x.side === 'sell') {
        if (s.q <= 1e-12) { row.r = { err: t('팔 수량이 없습니다(이 날짜 전 보유 0)', 'nothing held before this date') }; return; }
        var q = r.q;
        if (q > s.q + 1e-9) { row.warn = t('보유보다 많이 팔아 보유 수량까지만 반영', 'sold more than held — capped at holding'); q = s.q; }
        var avg = s.cost / s.q, proceeds = q * r.p - fee, frac = q / s.q;
        var gain = proceeds - q * avg;
        s.real += gain; s.cost -= q * avg; s.proc += proceeds; s.q -= q;
        if (s.c === 'USD') { // 매도일 환율로 원화 환산(없으면 현재 환율)
          var f = fxAt(x.date) || fxNow();
          if (f) s.realKrw += gain * f.r;
          s.sales.push({ d: x.date, g: gain, f: f });
        } else s.realKrw += gain;
        if (s.vok) { var vs = s.vsh * frac; s.vproc += vs * v.p; s.vsh -= vs; }
        if (s.q < 1e-12) { s.q = 0; s.cost = 0; }
      } else {
        var paid = r.q * r.p + fee;
        s.q += r.q; s.cost += paid; s.inv += paid;
        if (s.vok) s.vsh += paid / v.p;
      }
    });
    var list = Object.keys(P).map(function (a) {
      var s = P[a], o = num(state.settings.px[a]), L = last(a);
      s.now = o > 0 ? o : L ? L.p : null; s.nowd = o > 0 ? null : L ? L.d : null;
      s.value = s.now != null ? s.q * s.now : null;
      s.unreal = s.value != null ? s.value - s.cost : null;
      s.upct = s.cost > 0 && s.unreal != null ? s.unreal / s.cost * 100 : null;
      s.total = s.value != null ? s.value + s.proc - s.inv : null;
      s.tpct = s.inv > 0 && s.total != null ? s.total / s.inv * 100 : null;
      if (s.vok && s.inv > 0 && s.tpct != null) { var b = (s.vsh * vNow + s.vproc - s.inv) / s.inv * 100; s.vs = s.tpct - b; } else s.vs = null;
      return s;
    }).filter(function (s) { return s.q > 0 || Math.abs(s.real) > 1e-9; });
    list.sort(function (x, y) { return x.c === y.c ? (y.value || 0) - (x.value || 0) : x.c < y.c ? 1 : -1; });
    return { rows: rows, list: list };
  }

  // ---- 그리기 ----
  function renderMode() {
    var el = $('pmode'), n = state.trades.length;
    if (state.mode === 'local') {
      el.className = 'pmode';
      el.innerHTML = '<b>●</b>' + t('로컬 파일 private/trades.csv · ' + n + '건 · 이 컴퓨터에만 있습니다. 고치려면 CSV를 수정하고 python3 docs/build_case_study.py 를 다시 실행하세요',
        'local file private/trades.csv · ' + n + ' trades · on this machine only. Edit the CSV and rerun python3 docs/build_case_study.py');
    } else if (state.mode === 'db') {
      el.className = 'pmode';
      el.innerHTML = '<b>●</b>' + t('내 기록 ' + n + '건 · 이 페이지의 개인 저장 공간에 있어 공유받은 사람도 볼 수 없습니다',
        'my ledger · ' + n + ' trades · stored in your private space on this page — people it is shared with cannot see it');
    } else {
      el.className = 'pmode demo';
      el.innerHTML = '<b>●</b>' + (state.mode === 'loading'
        ? t('불러오는 중', 'loading')
        : t('이 페이지는 기록을 저장하지 않습니다 · 입력하면 계산만 해 보고, 새로고침하면 사라집니다', 'this page stores nothing · entries are calculated in place and vanish on reload'));
    }
  }

  function renderKpi(list) {
    var by = {};
    list.forEach(function (s) {
      var b = by[s.c] || (by[s.c] = { cost: 0, value: 0, unreal: 0, real: 0, total: 0, inv: 0 });
      b.cost += s.cost; b.value += s.value || 0; b.unreal += s.unreal || 0; b.real += s.real; b.total += s.total || 0; b.inv += s.inv;
    });
    var html = '';
    ['USD', 'KRW'].forEach(function (c) {
      var b = by[c]; if (!b) return;
      html += '<div><span class="cur">' + c + '</span><span class="tot ' + tone(b.unreal) + '">' + signed(b.unreal, c) +
        ' <small>' + pct(b.cost > 0 ? b.unreal / b.cost * 100 : null) + '</small></span><dl>' +
        '<dt>' + t('평가금액', 'market value') + '</dt><dd>' + money(b.value, c) + '</dd>' +
        '<dt>' + t('남은 원금', 'cost basis') + '</dt><dd>' + money(b.cost, c) + '</dd>' +
        '<dt>' + t('실현손익', 'realized') + '</dt><dd class="' + tone(b.real) + '">' + signed(b.real, c) + '</dd>' +
        '<dt>' + t('총손익(실현+평가)', 'total P&amp;L') + '</dt><dd class="' + tone(b.total) + '">' + signed(b.total, c) + ' · ' + pct(b.inv > 0 ? b.total / b.inv * 100 : null) + '</dd></dl></div>';
    });
    if (by.USD) { // 원화 환산 합계: 실현손익은 매도일 환율, 평가는 현재 환율
      var fn = fxNow(), sales = [], rUsdK = 0, rK = by.KRW ? by.KRW.real : 0;
      list.forEach(function (s) { if (s.c === 'USD') { rUsdK += s.realKrw; sales = sales.concat(s.sales.map(function (x) { x.a = s.a; return x; })); } });
      var rTot = rUsdK + rK, rows = '';
      sales.sort(function (x, y) { return x.d < y.d ? -1 : 1; }).forEach(function (x) {
        rows += '<dt>' + esc(x.a) + ' ' + t('매도', 'sold') + ' ' + x.d.slice(2).replace(/-/g, '/') + '</dt><dd class="' + tone(x.g) + '">' + (x.f ? signed(x.g * x.f.r, 'KRW') : '—') +
          '<i class="sub blk">' + signed(x.g, 'USD') + (x.f ? ' × ' + x.f.r.toLocaleString('en-US', { minimumFractionDigits: 2 }) : '') + '</i></dd>';
      });
      if (by.KRW) rows += '<dt>' + t('원화 종목 실현', 'KRW realized') + '</dt><dd class="' + tone(rK) + '">' + signed(rK, 'KRW') + '</dd>';
      if (fn) {
        var u = (by.KRW ? by.KRW.unreal : 0) + by.USD.unreal * fn.r, v = (by.KRW ? by.KRW.value : 0) + by.USD.value * fn.r;
        rows += '<dt>' + t('평가손익 합계', 'unrealized, total') + '</dt><dd class="' + tone(u) + '">' + signed(u, 'KRW') + '</dd>' +
          '<dt>' + t('평가금액 합계', 'market value, total') + '</dt><dd>' + money(v, 'KRW') + '</dd>' +
          '<dt>' + t('현재 환율', 'FX now') + '</dt><dd>' + fn.r.toLocaleString('en-US', { minimumFractionDigits: 2 }) + ' ' + (fn.d ? '<i class="sub">' + fn.d.slice(5).replace('-', '/') + '</i>' : '<i class="sub amb">' + t('직접', 'manual') + '</i>') + '</dd>';
      }
      html += '<div class="kr"><span class="cur">' + t('원화 환산 · 실현손익 합계', 'in KRW · realized, total') + '</span><span class="tot ' + tone(rTot) + '">' + signed(rTot, 'KRW') + '</span><dl>' + rows + '</dl>' +
        '<p class="fxn">' + t('달러 실현손익은 매도일 환율로 환산했습니다. 매수·매도 사이 환율 변동(환차손익)은 넣지 않아 세금 계산 기준과 다를 수 있습니다.',
          'USD gains are converted at the sale-date rate; FX gains between buy and sell are not included, so this differs from the tax basis.') + '</p></div>';
    }
    $('pk').innerHTML = html || '<p class="note">' + t('아직 보유 종목이 없습니다. 위에서 첫 거래를 추가하세요.', 'No positions yet — add your first trade above.') + '</p>';
  }

  function renderPos(list) {
    var h = '<thead><tr><th>' + t('종목', 'asset') + '</th><th>' + t('수량', 'qty') + '</th><th>' + t('평균 단가', 'avg cost') + '</th><th>' + t('현재가', 'price') +
      '</th><th>' + t('평가금액', 'value') + '</th><th>' + t('평가손익', 'unrealized') + '</th><th>%</th><th>' + t('실현손익', 'realized') + '</th><th>' + t('VOO 대비', 'vs VOO') + '</th></tr></thead><tbody>';
    list.forEach(function (s) {
      var pd = s.nowd ? '<i class="sub">' + s.nowd.slice(5).replace('-', '/') + '</i>' : '<i class="sub amb">' + t('직접', 'manual') + '</i>';
      h += '<tr><td>' + esc(s.a) + (s.est ? '<span class="bd">' + t('추정', 'est') + '</span>' : '') + '</td>' +
        '<td>' + (s.q > 0 ? qty(s.q) : '<span class="dim">' + t('청산', 'closed') + '</span>') + '</td>' +
        '<td>' + (s.q > 0 ? money(s.cost / s.q, s.c) : '—') + '</td><td>' + money(s.now, s.c) + ' ' + pd + '</td>' +
        '<td>' + (s.q > 0 ? money(s.value, s.c) : '—') + '</td><td class="' + tone(s.unreal) + '">' + (s.q > 0 ? signed(s.unreal, s.c) : '—') + '</td>' +
        '<td class="' + tone(s.unreal) + '">' + (s.q > 0 ? pct(s.upct) : '—') + '</td><td class="' + tone(s.real) + '">' + signed(s.real, s.c) + '</td>' +
        '<td class="' + tone(s.vs) + '">' + (s.vs == null ? '—' : (s.vs > 0 ? '+' : s.vs < 0 ? '−' : '') + Math.abs(s.vs).toFixed(1) + 'pp') + '</td></tr>';
    });
    $('ptab').innerHTML = h + '</tbody>';
    $('pwrap').hidden = !list.length;
  }

  function renderTrades(rows) {
    var h = '<thead><tr><th>' + t('날짜', 'date') + '</th><th>' + t('종목', 'asset') + '</th><th class="l">' + t('구분', 'side') + '</th><th>' + t('수량', 'qty') + '</th><th>' + t('단가', 'price') +
      '</th><th>' + t('금액', 'amount') + '</th><th class="l">' + t('그날 규칙', 'rule that day') + '</th><th class="l">' + t('메모', 'memo') + '</th><th></th></tr></thead><tbody>';
    rows.slice().reverse().forEach(function (row) {
      var x = row.x, r = row.r, c = cur(x.asset), sell = x.side === 'sell';
      var side = '<span class="' + (sell ? 'dn' : 'up') + '">' + (sell ? t('매도', 'SELL') : t('매수', 'BUY')) + '</span>';
      var del = x.id ? '<button type="button" class="xb" data-del="' + esc(x.id) + '">' + t('삭제', 'delete') + '</button>' : '';
      if (r.err) {
        h += '<tr class="bad"><td>' + esc(x.date) + '</td><td>' + esc(x.asset) + '</td><td class="l">' + side + '</td><td class="l" colspan="5">' + r.err + '</td><td>' + del + '</td></tr>';
        return;
      }
      h += '<tr><td>' + esc(x.date) + '</td><td>' + esc(x.asset) + '</td><td class="l">' + side + '</td><td>' + qty(r.q) + (num(x.qty) == null ? '<span class="bd">' + t('계산', 'calc') + '</span>' : '') +
        '</td><td>' + money(r.p, c) + (r.est ? '<span class="bd">' + t('종가 추정', 'close est') + '</span>' : '') + '</td><td>' + money(r.q * r.p, c) +
        '</td><td class="l">' + rule(row.rule) + '</td><td class="l memo">' + esc(x.memo || '') + (row.warn ? ' <span class="amb">' + row.warn + '</span>' : '') + '</td><td>' + del + '</td></tr>';
    });
    $('ttab').innerHTML = h + '</tbody>';
    $('tcount').textContent = rows.length + ' rows';
  }

  function renderOverrides(list) {
    var held = list.filter(function (s) { return s.q > 0; });
    var h = '<label>' + t('환율 USD→KRW', 'FX USD→KRW') + '<input type="number" step="any" min="0" inputmode="decimal" data-fx value="' + esc(state.settings.fx || '') + '" placeholder="' + (FX ? FX.c[FX.c.length - 1] : '') + '"></label>';
    held.forEach(function (s) {
      var L = last(s.a);
      h += '<label>' + esc(s.a) + ' ' + t('현재가', 'price') + '<input type="number" step="any" min="0" inputmode="decimal" data-px="' + esc(s.a) + '" value="' + esc(state.settings.px[s.a] || '') + '" placeholder="' + (L ? L.p : '') + '"></label>';
    });
    var box = $('povr'), f = document.activeElement;
    if (box.contains(f)) return; // 입력 중에는 다시 그리지 않는다
    box.innerHTML = h;
  }

  // ---- 인사이트: 원화 기준으로 한 번에 읽는 요약 ----
  function kor(v) {
    var a = Math.abs(v), e = Math.floor(a / 1e8), m = Math.round((a % 1e8) / 1e4);
    if (m === 10000) { e++; m = 0; }
    var o = (e ? e + '억 ' : '') + (m ? m.toLocaleString('en-US') + '만' : '');
    return (v < 0 ? '−' : '') + (o.trim() || '0') + ' 원';
  }
  function mil(v) { return (v < 0 ? '−' : '') + '₩' + (Math.abs(v) / 1e6).toFixed(1) + 'M'; }
  function both(v) { return t('약 ' + kor(v), '≈ ' + mil(v)); }
  function renderInsight(list) {
    var box = $('pins');
    if (!list.length) { box.hidden = true; return; }
    var fn = fxNow(), hasUsd = list.some(function (s) { return s.c === 'USD'; });
    if (hasUsd && !fn) { box.hidden = true; return; }
    var fx = fn ? fn.r : 1, real = 0, value = 0, cost = 0, usdVal = 0, held = [], realParts = [];
    list.forEach(function (s) {
      var k = s.c === 'USD' ? fx : 1;
      real += s.realKrw;
      if (Math.abs(s.realKrw) > 0.5) realParts.push(esc(s.a) + ' ' + signed(s.realKrw, 'KRW'));
      if (s.q > 0 && s.value != null) {
        value += s.value * k; cost += s.cost * k;
        if (s.c === 'USD') usdVal += s.value;
        var L = A[s.a]; held.push({ a: s.a, v: s.value * k, l: L ? L.l[L.l.length - 1] : null });
      }
    });
    var unreal = value - cost, total = real + unreal;
    held.sort(function (x, y) { return y.v - x.v; });
    var li = [];
    li.push(['실현', 'realized', t('지금까지 판 거래에서 확정된 이익은 <b class="' + tone(real) + '">' + signed(real, 'KRW') + '</b>(' + kor(real) + ')입니다.',
      'Gains locked in by past sales total <b class="' + tone(real) + '">' + signed(real, 'KRW') + '</b>.') +
      (realParts.length ? ' <span class="sub">' + realParts.join(' · ') + '</span>' : '')]);
    if (held.length) {
      li.push(['전부 정리', 'if sold', t('지금 가진 것을 현재가·현재 환율로 모두 팔면 <b>' + money(value, 'KRW') + '</b>(' + kor(value) + ')을 받습니다. 그중 <b class="' + tone(unreal) + '">' + signed(unreal, 'KRW') + '</b>는 아직 확정되지 않은 이익으로, 남은 원금 ' + money(cost, 'KRW') + ' 대비 ' + pct(cost > 0 ? unreal / cost * 100 : null) + '입니다.',
        'Selling everything at current prices and FX would bring in <b>' + money(value, 'KRW') + '</b>; <b class="' + tone(unreal) + '">' + signed(unreal, 'KRW') + '</b> of that is unrealized gain, ' + pct(cost > 0 ? unreal / cost * 100 : null) + ' on remaining cost.')]);
      li.push(['총이익', 'total', t('확정 이익까지 합친 총이익은 <b class="' + tone(total) + '">' + signed(total, 'KRW') + '</b>(' + kor(total) + ')입니다.',
        'Realized plus unrealized: <b class="' + tone(total) + '">' + signed(total, 'KRW') + '</b> (' + mil(total) + ').')]);
      var top = held[0], share = value > 0 ? top.v / value * 100 : 0;
      if (held.length > 1 || share < 100) li.push(['집중도', 'concentration', t('보유 금액의 <b>' + share.toFixed(1) + '%</b>가 ' + esc(top.a) + ' 한 종목입니다.' + (share >= 50 ? ' 이 종목의 움직임이 전체 손익을 거의 결정합니다.' : ''),
        '<b>' + share.toFixed(1) + '%</b> of holdings is ' + esc(top.a) + (share >= 50 ? ', so it drives most of the P&amp;L.' : '.'))]);
      else li.push(['집중도', 'concentration', t('보유 금액 전부가 ' + esc(top.a) + ' 한 종목입니다.', 'All holdings are in ' + esc(top.a) + '.')]);
      if (usdVal > 0) li.push(['환율', 'FX', t('달러 자산이 ' + money(usdVal, 'USD') + '라 환율이 10원 오르내리면 원화 평가액이 약 <b>' + money(usdVal * 10, 'KRW') + '</b> 바뀝니다.',
        'With ' + money(usdVal, 'USD') + ' in USD assets, a ₩10 move in USD/KRW shifts the KRW value by about <b>' + money(usdVal * 10, 'KRW') + '</b>.')]);
      li.push(['규칙 판단', 'rule now', t('이 프로젝트 판단 규칙의 최신 판단: ', 'Latest call from this project\'s rule: ') + held.map(function (h) { return esc(h.a) + ' ' + rule(h.l); }).join(' · ') +
        ' <span class="sub">' + t('규칙 기준 참고, 투자 권유 아님', 'reference only, not advice') + '</span>']);
    }
    box.innerHTML = '<div class="ih"><span class="cur">' + t('인사이트 · 원화 기준', 'insights · in KRW') + '</span><span class="sub">' +
      (fn ? t('환율 ', 'FX ') + fn.r.toLocaleString('en-US', { minimumFractionDigits: 2 }) + (fn.d ? ' (' + fn.d.slice(5).replace('-', '/') + ')' : t(' (직접 입력)', ' (manual)')) + ' · ' : '') +
      t('세금·수수료 전', 'before tax &amp; fees') + '</span></div><ul>' +
      li.map(function (x) { return '<li><span class="il">' + t(x[0], x[1]) + '</span><span class="ix">' + x[2] + '</span></li>'; }).join('') + '</ul>';
    box.hidden = false;
  }

  function render() {
    var out = compute();
    renderMode(); renderInsight(out.list); renderKpi(out.list); renderPos(out.list); renderTrades(out.rows); renderOverrides(out.list);
  }

  // ---- 저장 ----
  function msg(html, cls) { var m = $('pmsg'); m.className = 'pmsg ' + (cls || ''); m.innerHTML = html; }
  function failMsg(e) {
    var c = e && e.code;
    if (c === 'invalid_argument') return t('이 계정에서는 저장할 수 없습니다(보기 권한이거나 개인 공간이 없음)', 'this account cannot save here (view-only or no private space)');
    if (c === 'quota_exceeded') return t('저장 공간이 가득 찼습니다. 오래된 기록을 지워 주세요', 'storage is full — delete old rows');
    return t('저장하지 못했습니다. 잠시 뒤 다시 시도해 주세요', 'could not save — try again shortly');
  }
  var pending = Promise.resolve(), timer = null;
  function saveSettings() {
    clearTimeout(timer);
    timer = setTimeout(function () {
      if (!store) { render(); return; }
      var body = JSON.parse(JSON.stringify(state.settings));
      pending = pending.then(function () { return store.settings.set(body); }).catch(function (e) { msg(failMsg(e), 'err'); });
    }, 600);
  }

  $('pf').addEventListener('submit', function (ev) {
    ev.preventDefault();
    var f = ev.target, x = {
      date: f.date.value, asset: f.asset.value, side: f.side.value,
      qty: num(f.qty.value), price: num(f.price.value), amount: num(f.amount.value), fee: num(f.fee.value), memo: f.memo.value.trim().slice(0, 200)
    };
    if (!x.date || !x.asset) return msg(t('날짜와 종목을 골라 주세요', 'pick a date and an asset'), 'err');
    if (x.date > today()) return msg(t('미래 날짜는 넣을 수 없습니다', 'date is in the future'), 'err');
    if (x.qty == null && x.amount == null) return msg(t('수량이나 금액 중 하나는 적어야 합니다', 'enter a quantity or an amount'), 'err');
    var r = resolve(x);
    if (r.err) return msg(r.err, 'err');
    x.created = new Date().toISOString();
    var reset = function () { f.qty.value = f.price.value = f.amount.value = f.fee.value = f.memo.value = ''; };
    if (!store) {
      x.id = 'local-' + Date.now(); state.trades.push(x); reset(); render();
      return msg(t('추가했습니다(예시 화면이라 저장되지 않음)', 'added (example view — not saved)'), 'ok');
    }
    var clean = {}; Object.keys(x).forEach(function (k) { if (x[k] !== null && x[k] !== '') clean[k] = x[k]; });
    msg(t('저장 중…', 'saving…'));
    store.col.add(clean).then(function () { reset(); msg(t('저장했습니다', 'saved'), 'ok'); }, function (e) { msg(failMsg(e), 'err'); });
  });

  $('ttab').addEventListener('click', function (ev) {
    var b = ev.target.closest('[data-del]'); if (!b) return;
    if (!b.classList.contains('arm')) {
      b.classList.add('arm'); b.innerHTML = t('확인', 'confirm');
      setTimeout(function () { if (b.isConnected) { b.classList.remove('arm'); b.innerHTML = t('삭제', 'delete'); } }, 3000);
      return;
    }
    var id = b.getAttribute('data-del');
    if (!store) { state.trades = state.trades.filter(function (x) { return x.id !== id; }); render(); return; }
    store.col.doc(id).delete().catch(function (e) { msg(failMsg(e), 'err'); });
  });

  $('povr').addEventListener('change', function (ev) {
    var i = ev.target, v = num(i.value);
    if (i.hasAttribute('data-fx')) state.settings.fx = v > 0 ? v : null;
    else if (i.hasAttribute('data-px')) { var a = i.getAttribute('data-px'); if (v > 0) state.settings.px[a] = v; else delete state.settings.px[a]; }
    else return;
    render(); saveSettings();
  });

  // ---- 폼 준비 ----
  $('pf').addEventListener('click', function (ev) {
    var b = ev.target.closest('[data-side]'); if (!b) return;
    $('pf').side.value = b.getAttribute('data-side');
    $('pf').querySelectorAll('[data-side]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
  });
  var sel = $('pf').asset;
  sel.innerHTML = NAMES.map(function (a) { return '<option value="' + esc(a) + '">' + esc(a) + ' · ' + A[a].cur + '</option>'; }).join('');
  $('pf').date.value = today(); $('pf').date.max = today();
  $('pxasof').textContent = PX.asof;
  render();

  // ---- 저장소 연결 (없으면 예시로 남는다) ----
  if (window.MW_LOCAL) { // 로컬 페이지: CSV가 원본, 화면에서는 추가·삭제하지 않는다
    state.mode = 'local'; $('pf').closest('.win').hidden = true; render(); return;
  }
  function demo() { state.mode = 'demo'; render(); }
  var C = window.claude;
  if (!C || typeof C.use !== 'function') return demo();
  Promise.all([C.use('db'), C.use('user')]).then(function (cap) {
    var db = cap[0], user = cap[1];
    if (!db || !user) return demo();
    return user.id().then(function (uid) {
      if (!uid) return demo();
      var base = 'data/users/' + uid;
      store = { col: db.doc(base + '/book').collection('trades'), settings: db.doc(base + '/settings') };
      state.mode = 'db'; state.trades = []; render();
      store.col.onSnapshot(function (snap) {
        state.trades = snap.docs.map(function (d) { var o = Object.assign({}, d.data()); o.id = d.id; return o; });
        render();
      }, function (e) { store = null; state.mode = 'demo'; state.trades = DEMO.slice(); render(); msg(failMsg(e), 'err'); });
      store.settings.onSnapshot(function (d) {
        if (!d.exists) return;
        var s = d.data() || {};
        state.settings = { fx: s.fx || null, px: Object.assign({}, s.px || {}) };
        render();
      }, function () {});
    });
  }).catch(demo);
})();

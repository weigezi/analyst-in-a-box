// Hand-written SVG/HTML charts. Drawn at the container's real pixel width, so text is true size on every screen.
// Colours come from CSS classes (c-*), so both prototypes share the code and differ only in their stylesheet.
(function () {
  const { num, money, MINUS, zh } = window.AIB;
  const NS = "http://www.w3.org/2000/svg";
  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");
  const textW = (s, fs) => [...String(s)].reduce((a, ch) => a + (/[\u3000-\u9fff\uff00-\uffef]/.test(ch) ? fs : fs * 0.58), 0);
  const svg = (w, h, body, label) =>
    `<svg xmlns="${NS}" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label || "")}">${body}</svg>`;
  const t = (x, y, s, cls = "c-text", anchor = "start") => `<text x="${x}" y="${y}" class="${cls}" text-anchor="${anchor}">${esc(s)}</text>`;
  // Axis ticks: 万 in Chinese ("−4 万"), k in English.
  const tick = (v) => {
    if (v === 0) return "0";
    const s = v < 0 ? MINUS : "";
    return zh() ? s + +(Math.abs(v) / 1e4).toFixed(1) + " 万" : s + Math.round(Math.abs(v) / 1e3) + "k";
  };
  function ticks(lo, hi, n = 4) {
    const raw = (hi - lo) / n, p = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * p).find((s) => s >= raw);
    const out = [];
    for (let v = Math.ceil(lo / step - 1e-9) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
    return out;
  }
  const W = (el) => Math.max(240, Math.floor(el.clientWidth));
  const month = (m) => (zh() ? m + " 月" : ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m - 1]);
  // Month labels; on narrow charts only every other month, so labels never touch.
  function monthTicks(starts, x, y, narrow) {
    let g = "", last = "", k = 0;
    starts.forEach((s, i) => {
      const m = s.slice(5, 7);
      if (m !== last && +s.slice(8) <= 7) { if (!narrow || k % 2 === 1) g += t(x(i), y, month(+m), "c-tick", "middle"); k++; }
      last = m;
    });
    return g;
  }

  // ---- mini trend: weekly year-on-year growth; holiday-shifted weeks drawn grey, last point marked
  function spark(el, o) {
    const w = W(el), h = o.height || 44, s = o.series, pad = 5, grey = new Set(o.grey || []);
    const lo = Math.min(...s, 0), hi = Math.max(...s, 0);
    const x = (i) => pad + (i * (w - 2 * pad)) / (s.length - 1);
    const y = (v) => pad + ((hi - v) * (h - 2 * pad)) / (hi - lo);
    let g = `<line x1="${pad}" x2="${w - pad}" y1="${y(0)}" y2="${y(0)}" class="c-zero"/>`;
    for (let i = 1; i < s.length; i++) {
      const cls = grey.has(i) || grey.has(i - 1) ? "c-line muted" : "c-line";
      g += `<line x1="${x(i - 1)}" y1="${y(s[i - 1])}" x2="${x(i)}" y2="${y(s[i])}" class="${cls}"/>`;
    }
    const last = s.length - 1;
    g += `<circle cx="${x(last)}" cy="${y(s[last])}" r="3.5" class="c-negfill"/>`;
    el.innerHTML = svg(w, h, g, o.label);
  }

  // ---- horizontal waterfall from zero: signed steps then a total; every bar labelled
  function waterfall(el, o) {
    const w = W(el), fs = 13, rowH = o.rowH || 34, barH = Math.round(rowH * 0.56);
    const LW = Math.max(...o.rows.map((r) => textW(r.label, fs))) + 14;
    let run = 0;
    const segs = o.rows.map((r) => {
      if (r.kind === "total") return { ...r, a: 0, b: r.value };
      const a = run; run += r.value; return { ...r, a, b: run };
    });
    const vals = segs.flatMap((s) => [s.a, s.b]);
    const lo = Math.min(0, ...vals), hi = Math.max(0, ...vals);
    const VW = 96, top = 6, axisH = 22;
    const LP = lo < 0 ? VW : 0, RP = hi > 0 ? VW : 12;
    const pw = w - LW - LP - RP;
    const x = (v) => LW + LP + ((v - lo) / (hi - lo)) * pw;
    const h = top + segs.length * rowH + axisH;
    let g = "";
    ticks(lo, hi, w < 420 ? 2 : 4).forEach((v) => {
      g += `<line x1="${x(v)}" x2="${x(v)}" y1="${top}" y2="${h - axisH}" class="${v === 0 ? "c-zero" : "c-grid"}"/>`;
      g += t(x(v), h - 6, tick(v), "c-tick", "middle");
    });
    segs.forEach((s, i) => {
      const y0 = top + i * rowH + (rowH - barH) / 2, xa = x(Math.min(s.a, s.b)), xb = x(Math.max(s.a, s.b));
      const cls = s.kind === "total" ? "c-totalfill" : s.value < 0 ? "c-negfill" : "c-posfill";
      g += t(0, y0 + barH / 2 + 4.5, s.label, s.kind === "total" ? "c-label strong" : "c-label");
      g += `<rect x="${xa}" y="${y0}" width="${Math.max(1.5, xb - xa)}" height="${barH}" class="${cls}" rx="1"/>`;
      const vc = s.kind === "total" ? "c-value strong" : "c-value " + (s.value < 0 ? "neg" : "pos");
      const v = money(s.value, true);
      g += s.value < 0 ? t(xa - 6, y0 + barH / 2 + 4.5, v, vc, "end") : t(xb + 6, y0 + barH / 2 + 4.5, v, vc);
      if (i < segs.length - 1 && s.kind !== "total") {
        const yn = top + (i + 1) * rowH + (rowH - barH) / 2;
        g += `<line x1="${x(s.b)}" x2="${x(s.b)}" y1="${y0 + barH}" y2="${yn}" class="c-connector"/>`;
      }
    });
    el.innerHTML = svg(w, h, g, o.label);
  }

  // ---- diverging bars around a centred zero line
  function diverging(el, o) {
    const w = W(el), fs = 13, rowH = 30, barH = 16, top = 4, axisH = 22;
    const LW = Math.max(...o.rows.map((r) => textW(r.label, fs))) + 12;
    const VW = 92, m = o.domain;
    const pw = w - LW - 2 * VW, x0 = LW + VW + pw / 2;
    const x = (v) => x0 + (v / m) * (pw / 2);
    const h = top + o.rows.length * rowH + axisH;
    let g = "";
    (pw < 300 ? [-m, 0, m] : [-m, -m / 2, 0, m / 2, m]).forEach((v) => {
      g += `<line x1="${x(v)}" x2="${x(v)}" y1="${top}" y2="${h - axisH}" class="${v ? "c-grid" : "c-zero"}"/>`;
      g += t(x(v), h - 6, tick(v), "c-tick", "middle");
    });
    o.rows.forEach((r, i) => {
      const y0 = top + i * rowH + (rowH - barH) / 2, xa = x(Math.min(0, r.value)), xb = x(Math.max(0, r.value));
      const tone = r.value < 0 ? "neg" : "pos";
      g += t(0, y0 + barH / 2 + 4.5, r.label, "c-label" + (r.emph ? " strong" : ""));
      g += `<rect x="${xa}" y="${y0}" width="${Math.max(1.5, xb - xa)}" height="${barH}" rx="1" class="c-${tone}fill${r.emph ? "" : " soft"}"/>`;
      const v = money(r.value, true);
      g += r.value < 0 ? t(xa - 6, y0 + barH / 2 + 4.5, v, "c-value " + tone, "end") : t(xb + 6, y0 + barH / 2 + 4.5, v, "c-value " + tone);
    });
    el.innerHTML = svg(w, h, g, o.label);
  }
  // ---- 26 weeks of history + this week. Dashed lines = what a week must cross to be called unusual;
  // light fill = the middle half of the 26 weeks; holiday-shifted weeks boxed and grey.
  function band(el, o) {
    const w = W(el), h = o.height || 260, L = 44, R = 16, T = w < 520 ? 36 : 24, B = 30;
    const s = o.weeks.map((x) => x.yoy), n = s.length, grey = new Set(o.grey || []);
    const lo0 = Math.min(...s, o.lines[0]), hi0 = Math.max(...s, o.lines[1]);
    let tk = ticks(lo0, hi0, 5);
    const step = tk[1] - tk[0];
    while (tk[0] > lo0 + 1e-9) tk.unshift(+(tk[0] - step).toFixed(10));
    while (tk[tk.length - 1] < hi0 - 1e-9) tk.push(+(tk[tk.length - 1] + step).toFixed(10));
    const lo = tk[0], hi = tk[tk.length - 1];
    const x = (i) => L + (i * (w - L - R)) / (n - 1);
    const y = (v) => T + ((hi - v) * (h - T - B)) / (hi - lo);
    let g = "";
    tk.forEach((v) => {
      g += `<line x1="${L}" x2="${w - R}" y1="${y(v)}" y2="${y(v)}" class="${v === 0 ? "c-zero" : "c-grid"}"/>`;
      g += t(L - 6, y(v) + 4, (v < 0 ? MINUS : "") + Math.abs(Math.round(v * 100)) + "%", "c-tick", "end");
    });
    if (o.iqr) g += `<rect x="${L}" y="${y(o.iqr[1])}" width="${w - L - R}" height="${y(o.iqr[0]) - y(o.iqr[1])}" class="c-iqr"/>`;
    o.lines.forEach((v) => (g += `<line x1="${L}" x2="${w - R}" y1="${y(v)}" y2="${y(v)}" class="c-threshold"/>`));
    if (grey.size) {
      const idx = [...grey].sort((a, b) => a - b), a = x(idx[0]) - 6, b = x(idx[idx.length - 1]) + 6;
      g += `<rect x="${a}" y="${T - 16}" width="${b - a}" height="${h - T - B + 16}" class="c-holiday"/>`;
      g += w < 520 ? t(b, T - 20, o.holidayLabel, "c-note", "end") : t(a - 6, T - 5, o.holidayLabel, "c-note", "end");
    }
    for (let i = 1; i < n; i++) {
      const cls = grey.has(i) || grey.has(i - 1) ? "c-line muted" : "c-line";
      g += `<line x1="${x(i - 1)}" y1="${y(s[i - 1])}" x2="${x(i)}" y2="${y(s[i])}" class="${cls}"/>`;
    }
    s.forEach((v, i) => { if (i < n - 1) g += `<circle cx="${x(i)}" cy="${y(v)}" r="2.2" class="${grey.has(i) ? "c-dot muted" : "c-dot"}"/>`; });
    g += monthTicks(o.weeks.map((x) => x.start), x, h - 8, w < 520);
    const xl = x(n - 1), yl = y(s[n - 1]);
    const ly = Math.min(h - B - 8, yl + 36), lx = grey.size ? x(Math.min(...grey)) - 14 : xl - 12;
    g += `<line x1="${xl}" y1="${yl + 6}" x2="${lx + 4}" y2="${ly - 4}" class="c-connector"/>`;
    g += t(lx, ly - 2, o.lastLabel, "c-value neg strong", "end");
    g += t(lx, ly + 14, o.lastSub, "c-note", "end");
    g += `<circle cx="${xl}" cy="${yl}" r="5" class="c-negfill c-ring"/>`;
    el.innerHTML = svg(w, h, g, o.label);
  }

  // ---- weekly values this year (solid) against the same weeks a year earlier (dashed), with a dated marker
  function weekly(el, o) {
    const w = W(el), h = o.height || 220, L = 48, R = w < 520 ? 52 : 70, T = 24, B = 30, n = o.weeks.length;
    const a = o.weeks.map((x) => x.revenue), b = o.weeks.map((x) => x.base_revenue);
    const tk = ticks(0, Math.max(...a, ...b), 4), hi = tk[tk.length - 1];
    const x = (i) => L + (i * (w - L - R)) / (n - 1), y = (v) => T + ((hi - v) * (h - T - B)) / hi;
    const path = (s) => s.map((v, i) => (i ? "L" : "M") + x(i).toFixed(1) + "," + y(v).toFixed(1)).join("");
    let g = "";
    tk.forEach((v) => {
      g += `<line x1="${L}" x2="${w - R}" y1="${y(v)}" y2="${y(v)}" class="${v === 0 ? "c-zero" : "c-grid"}"/>`;
      g += t(L - 6, y(v) + 4, tick(v), "c-tick", "end");
    });
    const xm = x(o.markAt);
    g += `<line x1="${xm}" x2="${xm}" y1="${T - 10}" y2="${h - B}" class="c-marker"/>`;
    g += t(xm - 6, T - 2, o.markLabel, "c-note strong", "end");
    g += `<path d="${path(b)}" class="c-line base" fill="none"/>`;
    g += `<path d="${path(a)}" class="c-line" fill="none"/>`;
    g += t(x(n - 1) + 8, y(b[n - 1]) + (y(b[n - 1]) < y(a[n - 1]) - 14 ? 4 : -10), o.baseLabel, "c-note");
    g += t(x(n - 1) + 8, y(a[n - 1]) + 4, o.curLabel, "c-value neg strong");
    g += `<circle cx="${x(n - 1)}" cy="${y(a[n - 1])}" r="3.5" class="c-negfill"/>`;
    g += monthTicks(o.weeks.map((x) => x.start), x, h - 8, w < 520);
    el.innerHTML = svg(w, h, g, o.label);
  }

  // ---- one bar table: a parent row and indented child rows, all negative, one shared axis (HTML, so text wraps)
  function barTable(el, o) {
    const m = o.domain;
    const head = `<div class="bt-row bt-head"><span></span><span></span>${o.cols.map((c, k) => `<span class="bt-num${k === 2 ? " bt-opt" : ""}">${esc(c)}</span>`).join("")}</div>`;
    const rows = o.rows.map((r) => `<div class="bt-row${r.indent ? " indent" : " parent"}"><span class="bt-label">${esc(r.label)}</span>
      <span class="bt-bar"><i style="width:${((Math.abs(r.value) / m) * 100).toFixed(2)}%"></i></span>
      ${r.cells.map((c, k) => `<span class="bt-num${k === 0 ? " neg" : ""}${k === 2 ? " bt-opt" : ""}">${esc(c)}</span>`).join("")}</div>`).join("");
    const axis = `<div class="bt-row bt-axis"><span></span><span class="bt-bar">${[1, 0.5, 0].map((f) => `<b style="right:${(f * 100).toFixed(0)}%">${tick(-m * f)}</b>`).join("")}</span></div>`;
    el.innerHTML = `<div class="bt" role="table" aria-label="${esc(o.label)}">${head}${rows}${axis}</div>`;
  }

  // ---- two rows of seven days: this week and the same weekdays a year earlier, holidays marked
  function dayPairs(el, o) {
    const wd = (k) => (zh() ? "周" + "一二三四五六日"[k - 1] : ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][k - 1]);
    const row = (label, days) => `<div class="dp-row"><span class="dp-label">${esc(label)}</span>${days.map((d) =>
      `<span class="dp-day${d.holiday.length ? " hol" : ""}"><b>${d.date.slice(5)}</b><em>${wd(d.weekday)}</em><small>${tick(d.revenue)}</small></span>`).join("")}</div>`;
    el.innerHTML = `<div class="dp">${row(o.curLabel, o.current)}${row(o.baseLabel, o.base)}</div><p class="dp-note">${esc(o.note)}</p>`;
  }

  const charts = { spark, waterfall, diverging, band, weekly, barTable, dayPairs };
  const live = [];
  function draw(el, kind, opts) {
    if (!el) return;
    charts[kind](el, opts);
    live.push([el, kind, opts]);
  }
  let rt;
  window.addEventListener("resize", () => {
    clearTimeout(rt);
    rt = setTimeout(() => live.forEach(([el, k, o]) => el.isConnected && charts[k](el, o)), 120);
  });
  window.AIBCharts = { draw, ...charts };
})();

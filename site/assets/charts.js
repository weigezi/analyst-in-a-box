// Hand-written SVG charts, drawn at the container's real pixel width so text is true size on every screen.
// <div data-chart="<id>"> reads its numbers from window.AIB_SITE.charts[id] (build.py, engine fields only) and its
// wording from its own data-* attributes (templates), so a spec is the same for both languages. Colours: CSS c-*.
(function () {
  "use strict";
  var F = window.AIBFmt, NS = "http://www.w3.org/2000/svg";
  var pick = function (x) { return x && typeof x === "object" && "zh" in x ? x[F.lang()] : x; };
  var WD = { zh: ["周日", "周一", "周二", "周三", "周四", "周五", "周六"], en: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] };
  var weekday = function (iso) { var p = iso.split("-").map(Number); return WD[F.lang()][new Date(Date.UTC(p[0], p[1] - 1, p[2])).getUTCDay()]; };
  var esc = function (s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;"); };
  var textW = function (s, fs) {
    return Array.from(String(s)).reduce(function (a, ch) { return a + (/[\u3000-\u9fff\uff00-\uffef]/.test(ch) ? fs : fs * 0.6); }, 0);
  };
  var svg = function (w, h, body, label) {
    return '<svg xmlns="' + NS + '" width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + " " + h + '" role="img" aria-label="' + esc(label || "") + '">' + body + "</svg>";
  };
  var t = function (x, y, s, cls, anchor) {
    return '<text x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" class="' + (cls || "c-label") + '" text-anchor="' + (anchor || "start") + '">' + esc(s) + "</text>";
  };
  var line = function (x1, y1, x2, y2, cls) {
    return '<line x1="' + x1.toFixed(1) + '" y1="' + y1.toFixed(1) + '" x2="' + x2.toFixed(1) + '" y2="' + y2.toFixed(1) + '" class="' + cls + '"/>';
  };
  function ticks(lo, hi, n) {
    if (hi - lo < 1e-12) return [lo];
    var raw = (hi - lo) / n, p = Math.pow(10, Math.floor(Math.log10(raw)));
    var step = [1, 2, 2.5, 5, 10].map(function (m) { return m * p; }).find(function (s) { return s >= raw; });
    var out = [];
    for (var v = Math.ceil(lo / step - 1e-9) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
    return out;
  }
  var W = function (el) { return Math.max(240, Math.floor(el.clientWidth)); };

  // ---- mini trend of past changes plus this period; last point marked
  function spark(el, o) {
    var w = W(el), h = o.height || 44, s = o.series, pad = 5;
    var lo = Math.min.apply(null, s.concat([0])), hi = Math.max.apply(null, s.concat([0]));
    var x = function (i) { return pad + (i * (w - 2 * pad)) / (s.length - 1); };
    var y = function (v) { return pad + ((hi - v) * (h - 2 * pad)) / (hi - lo || 1); };
    var g = line(pad, y(0), w - pad, y(0), "c-zero");
    for (var i = 1; i < s.length; i++) g += line(x(i - 1), y(s[i - 1]), x(i), y(s[i]), "c-line");
    var last = s.length - 1;
    g += '<circle cx="' + x(last) + '" cy="' + y(s[last]) + '" r="3.5" class="' + (s[last] < 0 ? "c-negfill" : "c-posfill") + '"/>';
    el.innerHTML = svg(w, h, g, el.dataset.label);
  }

  // ---- horizontal waterfall from zero: signed steps, then the total change; every bar labelled
  // rows: {label:{zh,en}} | {kind:"others", n} | {kind:"total"}; wording for the last two from data-total / data-others ("{n}").
  function waterfall(el, o) {
    var w = W(el), fs = 13, rowH = 34, barH = 19, narrow = w < 480, ds = el.dataset;
    var rows = o.rows.map(function (r) {
      var label = r.kind === "total" ? ds.total : r.kind === "others" ? ds.others.replace("{n}", r.n) : pick(r.label);
      return Object.assign({}, r, { label: label });
    });
    var LW = Math.min(narrow ? 132 : 220, Math.max.apply(null, rows.map(function (r) { return textW(r.label, fs); })) + 14);
    var run = 0;
    var segs = rows.map(function (r) {
      if (r.kind === "total") return Object.assign({}, r, { a: 0, b: r.value });
      var a = run; run += r.value; return Object.assign({}, r, { a: a, b: run });
    });
    var vals = segs.reduce(function (a, s) { return a.concat([s.a, s.b]); }, [0]);
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
    var VW = narrow ? 78 : 96, top = 6, axisH = 22;
    var LP = lo < 0 ? VW : 4, RP = hi > 0 ? VW : 12, pw = w - LW - LP - RP;
    var x = function (v) { return LW + LP + ((v - lo) / (hi - lo || 1)) * pw; };
    var h = top + segs.length * rowH + axisH, g = "";
    ticks(lo, hi, narrow ? 2 : 4).forEach(function (v) {
      g += line(x(v), top, x(v), h - axisH, v === 0 ? "c-zero" : "c-grid");
      g += t(x(v), h - 6, F.tick(v, o.unit), "c-tick", "middle");
    });
    segs.forEach(function (s, i) {
      var y0 = top + i * rowH + (rowH - barH) / 2, xa = x(Math.min(s.a, s.b)), xb = x(Math.max(s.a, s.b)), ty = y0 + barH / 2 + 4.5;
      var cls = s.kind === "total" ? "c-totalfill" : s.value < 0 ? "c-negfill" : "c-posfill";
      var lab = s.label;
      while (textW(lab, fs) > LW - 10 && lab.length > 2) lab = lab.slice(0, -1);
      if (lab !== s.label) lab = lab.slice(0, -1) + "…";
      g += t(0, ty, lab, s.kind === "total" || s.emph ? "c-label strong" : "c-label");
      g += '<rect x="' + xa.toFixed(1) + '" y="' + y0 + '" width="' + Math.max(1.5, xb - xa).toFixed(1) + '" height="' + barH + '" class="' + cls + (s.soft ? " soft" : "") + '" rx="1"/>';
      var vc = s.kind === "total" ? "c-value strong" : "c-value " + (s.value < 0 ? "neg" : "pos");
      var v = F.value(s.value, o.unit, true, o.dp);
      g += s.value < 0 ? t(xa - 6, ty, v, vc, "end") : t(xb + 6, ty, v, vc);
      if (i < segs.length - 1 && s.kind !== "total") {
        var yn = top + (i + 1) * rowH + (rowH - barH) / 2;
        g += line(x(s.b), y0 + barH, x(s.b), yn, "c-connector");
      }
    });
    el.innerHTML = svg(w, h, g, el.dataset.label);
  }

  // ---- past periods' changes, the middle half shaded, the lines a change must cross to count as unusual, this period marked
  function band(el, o) {
    var w = W(el), h = o.height || 260, L = 48, R = 16, T = 26, B = 30, narrow = w < 520;
    var s = o.points.map(function (p) { return p.change; }), n = s.length;
    var lines = [o.below, o.above].filter(function (v) { return v != null; });
    var lo0 = Math.min.apply(null, s.concat(lines)), hi0 = Math.max.apply(null, s.concat(lines));
    var tk = ticks(lo0, hi0, 5), step = tk[1] - tk[0];
    while (tk[0] > lo0 + 1e-9) tk.unshift(+(tk[0] - step).toFixed(10));
    while (tk[tk.length - 1] < hi0 - 1e-9) tk.push(+(tk[tk.length - 1] + step).toFixed(10));
    var lo = tk[0], hi = tk[tk.length - 1];
    var x = function (i) { return L + (i * (w - L - R - (narrow ? 70 : 110))) / (n - 1); };
    var y = function (v) { return T + ((hi - v) * (h - T - B)) / (hi - lo); };
    var g = "";
    // usual_range is null when there are too few past periods to give a middle half.
    if (o.usual) g += '<rect x="' + L + '" y="' + y(o.usual[1]).toFixed(1) + '" width="' + (w - L - R) + '" height="' + (y(o.usual[0]) - y(o.usual[1])).toFixed(1) + '" class="c-iqr"/>';
    tk.forEach(function (v) {
      g += line(L, y(v), w - R, y(v), v === 0 ? "c-zero" : "c-grid");
      g += t(L - 6, y(v) + 4, F.tick(v, o.unit), "c-tick", "end");
    });
    lines.forEach(function (v) { g += line(L, y(v), w - R, y(v), "c-threshold"); });
    for (var i = 1; i < n - 1; i++) g += line(x(i - 1), y(s[i - 1]), x(i), y(s[i]), "c-line");
    for (i = 0; i < n - 1; i++) g += '<circle cx="' + x(i).toFixed(1) + '" cy="' + y(s[i]).toFixed(1) + '" r="2.4" class="c-dot"/>';
    g += line(x(n - 2), y(s[n - 2]), x(n - 1), y(s[n - 1]), "c-line muted");
    var first = o.points[0].start, lastHist = o.points[n - 2].start;
    g += t(L, h - 8, F.md(first), "c-tick", "start") + t(x(n - 2), h - 8, F.md(lastHist), "c-tick", "end");
    var xl = x(n - 1), yl = y(s[n - 1]), cur = s[n - 1];
    g += '<circle cx="' + xl.toFixed(1) + '" cy="' + yl.toFixed(1) + '" r="5" class="' + (cur < 0 ? "c-negfill" : "c-posfill") + ' c-ring"/>';
    g += t(xl + 9, yl + 4, el.dataset.last, "c-value strong " + (cur < 0 ? "neg" : "pos"));
    g += t(xl + 9, yl + 20, F.value(cur, o.unit, true, o.dp), "c-value " + (cur < 0 ? "neg" : "pos"));
    el.innerHTML = svg(w, h, g, el.dataset.label);
  }

  // ---- two daily lines by position: this period solid, the comparison period dashed
  function daily(el, o) {
    var w = W(el), h = o.height || 220, L = 52, R = 12, T = 30, B = 30, n = o.current.length;
    var a = o.current.map(function (d) { return d.value; }), b = o.base.map(function (d) { return d.value; });
    var lo0 = Math.min.apply(null, a.concat(b)), hi0 = Math.max.apply(null, a.concat(b));
    var tk = ticks(o.zero ? 0 : lo0, hi0, 4), step = tk[1] - tk[0];
    if (!o.zero) while (tk[0] > lo0 + 1e-9) tk.unshift(+(tk[0] - step).toFixed(10));
    while (tk[tk.length - 1] < hi0 - 1e-9) tk.push(+(tk[tk.length - 1] + step).toFixed(10));
    var lo = tk[0], hi = tk[tk.length - 1];
    var x = function (i) { return n === 1 ? (L + w - R) / 2 : L + (i * (w - L - R)) / (n - 1); };
    var y = function (v) { return T + ((hi - v) * (h - T - B)) / (hi - lo || 1); };
    var path = function (s) { return s.map(function (v, i) { return (i ? "L" : "M") + x(i).toFixed(1) + "," + y(v).toFixed(1); }).join(""); };
    var g = "";
    tk.forEach(function (v) { g += line(L, y(v), w - R, y(v), "c-grid"); g += t(L - 6, y(v) + 4, F.tick(v, o.unit), "c-tick", "end"); });
    g += '<path d="' + path(b) + '" class="c-line base" fill="none"/><path d="' + path(a) + '" class="c-line" fill="none"/>';
    a.forEach(function (v, i) { g += '<circle cx="' + x(i).toFixed(1) + '" cy="' + y(v).toFixed(1) + '" r="2.6" class="c-dot"/>'; });
    var every = Math.max(1, Math.ceil(n / (w < 520 ? 4 : 8)));
    o.current.forEach(function (d, i) { if (i % every === 0 || i === n - 1) g += t(x(i), h - 8, n <= 7 ? weekday(d.day) : F.md(d.day), "c-tick", i === 0 ? "start" : i === n - 1 ? "end" : "middle"); });
    g += line(L, 10, L + 18, 10, "c-line") + t(L + 24, 14, el.dataset.cur, "c-note");
    var bx = L + 34 + textW(el.dataset.cur, 12) + 16;
    g += line(bx, 10, bx + 18, 10, "c-line base") + t(bx + 24, 14, el.dataset.base, "c-note");
    el.innerHTML = svg(w, h, g, el.dataset.label);
  }

  // ---- daily gap to the comparison period as bars, with the start date the engine found and the average before / after
  function onset(el, o) {
    var w = W(el), h = o.height || 220, L = 52, R = 12, T = 30, B = 30, n = o.days.length;
    var v = o.days.map(function (d) { return d.gap; });
    var tk = ticks(Math.min.apply(null, v.concat([0])), Math.max.apply(null, v.concat([0])), 4);
    var lo = Math.min(tk[0], Math.min.apply(null, v)), hi = Math.max(tk[tk.length - 1], Math.max.apply(null, v));
    var bw = (w - L - R) / n, x = function (i) { return L + i * bw; };
    var y = function (q) { return T + ((hi - q) * (h - T - B)) / (hi - lo || 1); };
    var g = "", k = o.days.findIndex(function (d) { return d.day === o.start; });
    tk.forEach(function (q) { g += line(L, y(q), w - R, y(q), q === 0 ? "c-zero" : "c-grid"); g += t(L - 6, y(q) + 4, F.tick(q, o.unit), "c-tick", "end"); });
    v.forEach(function (q, i) {
      var y0 = y(Math.max(0, q)), y1 = y(Math.min(0, q));
      g += '<rect x="' + (x(i) + bw * 0.15).toFixed(1) + '" y="' + y0.toFixed(1) + '" width="' + Math.max(1, bw * 0.7).toFixed(1) + '" height="' + Math.max(0.5, y1 - y0).toFixed(1) + '" class="' + (q < 0 ? "c-negfill" : "c-posfill") + (k >= 0 && i < k ? " soft" : "") + '"/>';
    });
    if (k >= 0) {
      g += line(L, y(o.before), x(k), y(o.before), "c-mean") + line(x(k), y(o.after), w - R, y(o.after), "c-mean");
      g += line(x(k), T - 14, x(k), h - B, "c-marker");
      var right = x(k) > w * 0.6;
      g += t(x(k) + (right ? -6 : 6), T - 4, el.dataset.start.replace("{d}", F.md(o.start)), "c-note strong", right ? "end" : "start");
    }
    g += t(L, h - 8, F.md(o.days[0].day), "c-tick", "start") + t(w - R, h - 8, F.md(o.days[n - 1].day), "c-tick", "end");
    el.innerHTML = svg(w, h, g, el.dataset.label);
  }

  var kinds = { spark: spark, waterfall: waterfall, band: band, daily: daily, onset: onset };
  var specs = (window.AIB_SITE || {}).charts || {};
  var live = [];
  // Charts inside hidden panels have no width yet; the panel's script calls draw() again when it is shown.
  function draw(el) {
    var o = specs[el.dataset.chart];
    if (!o) throw new Error("no chart spec for " + el.dataset.chart);
    if (!el.clientWidth) return;
    kinds[o.kind](el, o);
    if (!live.some(function (p) { return p[0] === el; })) live.push([el, o]);
  }
  function drawAll(root) { (root || document).querySelectorAll("[data-chart]").forEach(draw); }
  var rt;
  window.addEventListener("resize", function () {
    clearTimeout(rt);
    rt = setTimeout(function () { live.forEach(function (p) { if (p[0].isConnected && p[0].clientWidth) kinds[p[1].kind](p[0], p[1]); }); }, 120);
  });
  window.AIBCharts = { draw: draw, drawAll: drawAll, kinds: kinds, specs: specs };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { drawAll(); });
  else drawAll();
})();

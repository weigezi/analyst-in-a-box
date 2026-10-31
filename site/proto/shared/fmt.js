// Number formatting and data binding shared by both prototypes. Minus is U+2212; every figure comes from AIB_DATA.
(function () {
  const D = window.AIB_DATA;
  const MINUS = "\u2212";
  const lang = () => ((document.documentElement.lang || "zh").startsWith("zh") ? "zh" : "en");
  const zh = () => lang() === "zh";
  const sign = (x, s) => (x < 0 ? MINUS : x > 0 && s ? "+" : "");
  const num = (x, dp = 0, s = false) =>
    sign(x, s) + Math.abs(x).toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp });
  const pct = (x, dp = 1, s = true) => sign(x, s) + Math.abs(x * 100).toFixed(dp) + "%";
  // Money: "−79,168 元" in Chinese, "−¥79,168" in English.
  const money = (x, s = false, dp = 0) => (zh() ? num(x, dp, s) + " 元" : sign(x, s) + "¥" + num(Math.abs(x), dp));
  // Round to 万 / thousands for headlines: "7.9 万元", "¥79k".
  const wan = (x, s = false) => (zh() ? sign(x, s) + (Math.abs(x) / 1e4).toFixed(1) + " 万元" : sign(x, s) + "¥" + Math.round(Math.abs(x) / 1e3) + "k");
  const range = (r) => (zh() ? r[0] + " 至 " + r[1] : r[0] + "\u2013" + r[1]);
  const T = (o) => (o && typeof o === "object" && "zh" in o ? o[lang()] : o);
  const arrow = (x) => (x < 0 ? "▼" : x > 0 ? "▲" : "");
  const md = (iso) => { const [, m, d] = iso.split("-").map(Number); return zh() ? `${m} 月 ${d} 日` : new Date(iso + "T00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short" }); };

  const get = (path) => path.split(".").reduce((o, k) => (o == null ? o : o[k]), D);

  // Derived in JS only from fields of the run; heavier derivations come from Python (D.derived_py, with D.how notes).
  const P = D.derived_py;
  const cut0 = D.cuts[0];
  const top = cut0.segments[0];
  const fall = D.cuts[1].segments.map((x) => Math.abs(x.delta / x.base));
  D.derived = {
    top, others: P.others, marketplace: P.marketplace,
    region_fall_min: Math.min(...fall), region_fall_max: Math.max(...fall),
    times_usual_wobble: Math.abs(D.qualify.z), times_needed: Math.abs(D.qualify.z_low),
    checks_passed: D.checks.filter((c) => c.pass).length, checks_total: D.checks.length,
    expected_market: D.total.delta - D.qualify.own_part,
    holiday_idx: D.weeks.map((w, i) => (w.holiday.length ? i : -1)).filter((i) => i >= 0),
  };

  function render(el) {
    const v = get(el.dataset.v);
    const f = el.dataset.f || "num";
    let out;
    if (v == null) out = "";
    else if (f === "num") out = num(v, +(el.dataset.dp || 0), "s" in el.dataset);
    else if (f === "money") out = money(v, "s" in el.dataset);
    else if (f === "wan") out = wan(v, "s" in el.dataset);
    else if (f === "pct") out = pct(v, +(el.dataset.dp || 1), !("nos" in el.dataset));
    else if (f === "times") out = Math.abs(v).toFixed(1);
    else if (f === "range") out = range(v);
    else if (f === "md") out = md(v);
    else if (f === "t") out = T(v);
    else out = String(v);
    if ("arrow" in el.dataset && typeof v === "number") out = arrow(v) + " " + out;
    el.textContent = out;
    if ("tone" in el.dataset && typeof v === "number") el.classList.add(v < 0 ? "neg" : "pos");
  }
  const bind = (root = document) => root.querySelectorAll("[data-v]").forEach(render);

  window.AIB = { D, num, pct, money, wan, md, range, T, lang, zh, arrow, bind, MINUS };
})();

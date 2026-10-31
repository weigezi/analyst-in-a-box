// Number formatting for charts drawn in the browser. Same rules as build.py's filters:
// minus is U+2212, every change carries its sign, money is "−79,168 元" in Chinese and "−¥79,168" in English.
(function () {
  "use strict";
  var MINUS = "\u2212";
  var lang = function () { return (document.documentElement.lang || "zh").indexOf("zh") === 0 ? "zh" : "en"; };
  var zh = function () { return lang() === "zh"; };
  var sign = function (x, s) { return x < 0 ? MINUS : x > 0 && s ? "+" : ""; };
  var round = function (x, dp) { var p = Math.pow(10, dp); return Math.round(x * p) / p; };
  function num(x, dp, s) {
    dp = dp || 0;
    var r = round(x, dp);
    return sign(r, s) + Math.abs(r).toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp });
  }
  function pct(x, dp, s) {
    if (dp == null) dp = 1;
    if (s == null) s = true;
    var r = round(x * 100, dp);
    return sign(r, s) + Math.abs(r).toFixed(dp) + "%";
  }
  function money(x, s, dp) {
    dp = dp || 0;
    var r = round(x, dp);
    if (document.documentElement.dataset.currency === "GBP") return sign(r, s) + "£" + num(Math.abs(r), dp);
    return zh() ? num(r, dp, s) + " 元" : sign(r, s) + "¥" + num(Math.abs(r), dp);
  }
  // Value in the unit of the chart: currency, count or ratio.
  // Value in the unit of the chart; dp = decimal places (2 for per-order amounts such as order value).
  function value(x, unit, s, dp) {
    if (unit === "ratio" || unit === "pct") return pct(x, 1, s);
    if (unit === "points") return sign(round(x * 100, 1), s) + Math.abs(round(x * 100, 1)).toFixed(1) + (zh() ? " 个百分点" : " points");
    if (unit === "ratio_gap") return money(x, s, 2);
    if (unit === "count") return num(x, dp || 0, s);
    return money(x, s, dp || 0);
  }
  // Axis ticks: 万 in Chinese ("−4 万"), k in English.
  function tick(v, unit) {
    if (v === 0) return "0";
    if (unit === "ratio" || unit === "pct") return pct(v, Math.abs(v) < 0.1 && v !== 0 && Math.abs(v * 100 % 1) > 1e-9 ? 1 : 0, false);
    if (unit === "points") return sign(v) + +(Math.abs(v) * 100).toFixed(1);
    if (unit === "ratio_gap") return sign(v) + Math.abs(v).toFixed(2);
    if (unit === "currency_small" || Math.abs(v) < 1000) return sign(v) + num(Math.abs(v), Math.abs(v) < 10 ? 1 : 0);
    var s = v < 0 ? MINUS : "";
    if (document.documentElement.dataset.currency === "GBP") return s + "£" + +(Math.abs(v) / 1e3).toFixed(0) + "k";
    return zh() ? s + +(Math.abs(v) / 1e4).toFixed(1) + " 万" : s + +(Math.abs(v) / 1e3).toFixed(0) + "k";
  }
  function md(iso) {
    var p = iso.split("-").map(Number);
    if (zh()) return p[1] + " 月 " + p[2] + " 日";
    return new Date(Date.UTC(p[0], p[1] - 1, p[2])).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
  }
  window.AIBFmt = { MINUS: MINUS, lang: lang, zh: zh, num: num, pct: pct, money: money, value: value, tick: tick, md: md };
})();

/* One case, told step by step. As a step scrolls into view, the graph lights the nodes it uses. */
(function () {
  "use strict";
  var A = window.AIB, stepsEl = document.getElementById("steps"), svg = document.getElementById("story-graph");
  if (!A || !stepsEl || !svg) return;
  var graph = window.AIBGraph.create(svg, { lang: A.lang, name: "story" });
  var observer = null, current = null;

  function pct(v) { return v == null ? "" : (v * 100).toFixed(1) + "%"; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  function bars(step) {
    var max = Math.max.apply(null, step.bars.map(function (b) { return Math.abs(b.value); })) || 1;
    var anyNeg = step.bars.some(function (b) { return b.value < 0; }), anyPos = step.bars.some(function (b) { return b.value > 0; });
    // Mixed signs: zero in the middle. One sign only: zero at the edge, bars use the full width.
    var mode = anyNeg && anyPos ? "mixed" : anyNeg ? "allneg" : "allpos", span = mode === "mixed" ? 50 : 100;
    var out = '<div class="bars">';
    step.bars.forEach(function (b) {
      var wd = Math.abs(b.value) / max * span, neg = b.value < 0;
      var at = mode === "mixed" ? (neg ? "right:50%" : "left:50%") : mode === "allneg" ? "right:0" : "left:0";
      out += '<div class="bar' + (b.top ? " top" : "") + '"><span class="lab">' + esc(b.label) + '</span><span class="track ' + mode + '"><span class="fill' +
        (neg ? " neg" : "") + '" style="' + at + ";width:" + wd.toFixed(2) + '%"></span></span><span class="sh">' + pct(b.share) + "</span></div>";
    });
    out += "</div>";
    var cls = step.drill ? "drill" : "stop";
    return out + '<span class="decision ' + cls + '">' + (step.drill ? A.ui.stop_drill : A.ui.stop_spread) + "</span>";
  }

  function activate(i, steps) {
    var step = steps[i];
    stepsEl.querySelectorAll(".step").forEach(function (e, j) { e.classList.toggle("on", j === i); });
    graph.lit(step.lit);
    if (step.lit.length) graph.pulse(step.lit[step.lit.length - 1]);
  }

  function render(key) {
    if (current === key) return;
    current = key;
    var c = A.cases[key];
    graph.setData({ nodes: c.nodes, links: c.links });
    stepsEl.textContent = "";
    c.steps.forEach(function (st, i) {
      var d = document.createElement("article");
      d.className = "step"; d.dataset.i = i;
      d.innerHTML = '<div class="n">' + String(i + 1).padStart(2, "0") + " · " + A.ui.steps[st.kind] + "</div>" + st.html + (st.bars ? bars(st) : "");
      if (i === c.steps.length - 1) d.innerHTML += '<p class="more"><a href="' + c.report + '">' + A.ui.report + " →</a></p>";
      stepsEl.appendChild(d);
    });
    if (observer) observer.disconnect();
    observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) activate(+e.target.dataset.i, c.steps); });
    }, { rootMargin: "-38% 0px -52% 0px" });
    stepsEl.querySelectorAll(".step").forEach(function (e) { observer.observe(e); });
    activate(0, c.steps);
  }

  document.querySelectorAll(".tabs button").forEach(function (b) {
    b.addEventListener("click", function () {
      document.querySelectorAll(".tabs button").forEach(function (x) { x.classList.toggle("on", x === b); });
      render(b.dataset.case);
      stepsEl.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
  render(Object.keys(A.cases)[0]);
})();

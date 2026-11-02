// Home page behaviour: replay the session, step through the case, copy the install command.
(function () {
  "use strict";
  var F = window.AIBFmt, C = window.AIBCharts;
  var $ = function (q, r) { return (r || document).querySelector(q); };

  var replay = $("#replay");
  if (replay) {
    var items = Array.prototype.slice.call(document.querySelectorAll(".session .reveal, .session .progress li"));
    var reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    replay.addEventListener("click", function () {
      if (reduce || !items.length || !items[0].animate) return;
      items.forEach(function (el, k) {
        el.animate([{ opacity: 0, transform: "translateY(4px)" }, { opacity: 1, transform: "none" }],
                   { duration: 280, delay: 160 + k * 260, easing: "ease", fill: "backwards" });
      });
    });
  }

  var root = $("#stepper");
  if (root) {
    var panels = root.querySelectorAll(".st-panel"), buttons = root.querySelectorAll(".st-list button"), n = panels.length, i = 0;
    var show = function (k) {
      i = Math.max(0, Math.min(n - 1, k));
      panels.forEach(function (p, j) { p.hidden = j !== i; });
      buttons.forEach(function (b, j) {
        b.classList.toggle("on", j === i); b.classList.toggle("done", j < i);
        if (j === i) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
      });
      panels[i].querySelectorAll("[data-chart]").forEach(C.draw);
      $(".st-prev", root).disabled = i === 0;
      $(".st-next", root).hidden = i === n - 1;
      $(".st-skip", root).hidden = i === n - 1;
      $(".st-report", root).hidden = i !== n - 1;
    };
    root.addEventListener("click", function (e) {
      var b = e.target.closest("button");
      if (!b) return;
      if (b.dataset.k) show(+b.dataset.k);
      else if (b.classList.contains("st-prev")) show(i - 1);
      else if (b.classList.contains("st-next")) show(i + 1);
      else if (b.classList.contains("st-skip")) show(n - 1);
    });
  }

  document.querySelectorAll("[data-copy]").forEach(function (b) {
    var label = b.textContent;
    b.addEventListener("click", function () {
      var text = document.getElementById(b.dataset.copy).querySelector(".k").textContent;
      var done = function (ok) {
        b.textContent = ok ? (F.zh() ? "已复制" : "Copied") : (F.zh() ? "请手动选中复制" : "Select to copy");
        setTimeout(function () { b.textContent = label; }, 1800);
      };
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(false); });
      else done(false);
    });
  });
})();

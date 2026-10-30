/* The full graph: two views of the same workspace, and the path each demo question took. */
(function () {
  "use strict";
  var A = window.AIB, svg = document.getElementById("full-graph"), panel = document.getElementById("detail");
  if (!A || !svg) return;
  var graph = window.AIBGraph.create(svg, { lang: A.lang, name: "full" });
  var view = "metrics", sel = document.getElementById("case");

  function show(v) {
    view = v;
    var nodes = A.graph.nodes.filter(function (n) { return n.views.indexOf(v) >= 0; });
    var links = A.graph.links.filter(function (l) { return l.views.indexOf(v) >= 0; });
    graph.setData({ nodes: nodes, links: links });
    document.querySelectorAll(".views button").forEach(function (b) { b.classList.toggle("on", b.dataset.view === v); });
    light();
  }
  function light() { graph.lit(sel.value ? A.lit[sel.value] : []); }
  function esc(s) { return String(s).replace(/[&<>]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]; }); }

  graph.onSelect(function (d, nb) {
    var name = (d.label && (d.label[A.lang] || d.label.en)) || d.id;
    var html = '<div class="k">' + esc(A.ui.legend[d.kind] || d.kind) + (d.status ? " · " + esc(d.status) : "") + "</div><h3>" + esc(name) + "</h3>";
    if (d.short) html += "<p><code>" + esc(d.short) + "</code></p>";
    if (nb.length) html += "<ul>" + nb.map(function (n) { return "<li>" + esc((n.label && (n.label[A.lang] || n.label.en)) || n.id) + "</li>"; }).join("") + "</ul>";
    panel.innerHTML = html; panel.classList.add("open");
  });
  svg.addEventListener("pointerdown", function (e) { if (e.target === svg) panel.classList.remove("open"); });
  document.querySelectorAll(".views button").forEach(function (b) { b.addEventListener("click", function () { show(b.dataset.view); }); });
  sel.addEventListener("change", light);
  show(view);
})();

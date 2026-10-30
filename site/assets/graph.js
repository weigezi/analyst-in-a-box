/* A small force-directed graph with Obsidian-like physics, no dependencies.
   Opening: every node bursts from the centre on the first frame and settles in about 5 s.
   Dragging: neighbours are pulled along by their links; after release it settles in about 4 s.
   Clicking: highlight and a light bounce only; the layout does not move.
   Time-based ticks (one tick per 16.7 ms) keep these durations the same on 60 Hz and 120 Hz screens. */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";
  var ALPHA_MIN = 0.001, DECAY = 1 - Math.pow(ALPHA_MIN, 1 / 300), VELOCITY_KEEP = 0.6, TICK_MS = 1000 / 60;
  var LINK_LEN = { identity: 78, ratio: 66, cut: 96, value: 46, relation: 54, mechanism: 58, event: 58, action: 58 };
  var registry = (window.__aib = window.__aib || { graphs: [] });

  function seeded(seed) { return function () { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; }; }
  function el(tag, attrs) { var e = document.createElementNS(NS, tag); for (var k in attrs) e.setAttribute(k, attrs[k]); return e; }
  function shape(kind, r) {
    if (kind === "metric" || kind === "entity") return el("circle", { r: r });
    var p;
    if (kind === "dimension") p = "M" + -r + "," + -r + "h" + 2 * r + "v" + 2 * r + "h" + -2 * r + "z";
    else if (kind === "mechanism") p = "M0," + -r * 1.3 + "L" + r * 1.3 + ",0L0," + r * 1.3 + "L" + -r * 1.3 + ",0z";
    else if (kind === "event") p = "M0," + -r * 1.3 + "L" + r * 1.2 + "," + r * 0.9 + "L" + -r * 1.2 + "," + r * 0.9 + "z";
    else p = "M" + -r + "," + -r + "h" + 2 * r + "v" + 2 * r + "h" + -2 * r + "z";
    return el("path", { d: p, rx: 2 });
  }
  function radius(n) { return n.kind === "metric" ? (n.ring === 0 ? 13 : 9) : n.kind === "entity" ? 5.5 : 6.5; }
  function text(n, lang) {
    var t = (n.label && (n.label[lang] || n.label.en)) || n.id;
    var max = lang === "zh" ? 12 : 20;
    if (/^(mechanism|event|action)$/.test(n.kind) && t.length > max) t = t.slice(0, max - 1) + "…";
    return t;
  }

  function create(svg, opts) {
    opts = opts || {};
    var lang = opts.lang || "en", rnd = seeded(opts.seed || 7);
    var nodes = [], links = [], byId = {}, keep = {}, alpha = 1, target = 0, running = false, last = 0;
    var w = 800, h = 600, ringR = {}, scale = 1, onSelect = function () {};
    var gLinks = el("g", {}), gRanks = el("g", {}), gNodes = el("g", {});
    svg.appendChild(gLinks); svg.appendChild(gRanks); svg.appendChild(gNodes);
    var state = { startedAt: 0, kickedAt: 0, settledAt: 0, settleMs: null, ticks: 0, id: opts.name || "graph" };
    registry.graphs.push(state);

    function resize() {
      var b = svg.getBoundingClientRect(); w = Math.max(320, b.width); h = Math.max(260, b.height);
      svg.setAttribute("viewBox", [-w / 2, -h / 2, w, h].join(" "));
      var rings = Object.keys(nodes.reduce(function (a, n) { a[n.ring || 0] = 1; return a; }, {})).map(Number).sort();
      var step = (Math.min(w, h) * 0.40) / Math.max(1, rings.length - 1);
      ringR = {}; rings.forEach(function (r, i) { ringR[r] = i * step; });
      state.ringStep = step;
      // Spacing follows the panel, so a small story panel and a full-screen graph both fill their space.
      scale = Math.max(0.8, Math.min(1.8, Math.sqrt(w * h) / 620));
    }

    function setData(data) {
      gLinks.textContent = ""; gRanks.textContent = ""; gNodes.textContent = "";
      byId = {};
      nodes = data.nodes.map(function (d) {
        var old = keep[d.id];
        var n = { id: d.id, kind: d.kind, ring: d.ring || 0, data: d,
                  x: old ? old.x : (rnd() - 0.5) * 2, y: old ? old.y : (rnd() - 0.5) * 2, vx: 0, vy: 0 };
        byId[n.id] = n; return n;
      });
      links = data.links.filter(function (l) { return byId[l.s] && byId[l.t]; })
        .map(function (l) { return { s: byId[l.s], t: byId[l.t], kind: l.kind, data: l }; });
      resize();
      links.forEach(function (l) {
        l.el = el("line", { class: "link " + l.kind }); gLinks.appendChild(l.el);
        if (l.data.rank) { l.rank = el("text", { class: "rank" }); l.rank.textContent = l.data.rank; gRanks.appendChild(l.rank); }
      });
      nodes.forEach(function (n) {
        var g = el("g", { class: "node k-" + n.kind + (n.data.external ? " external" : "") + (n.data.status === "proposed" ? " proposed" : "") });
        g.appendChild(el("circle", { class: "hit", r: radius(n) + 8 }));
        g.appendChild(shape(n.kind, radius(n)));
        var t = el("text", n.kind === "metric" ? { y: radius(n) + 15, "text-anchor": "middle" } : { x: radius(n) + 5, y: 4 });
        t.textContent = text(n.data, lang); g.appendChild(t);
        var tip = el("title", {}); tip.textContent = (n.data.label && (n.data.label[lang] || n.data.label.en)) || n.id; g.appendChild(tip);
        n.el = g; gNodes.appendChild(g); drag(n);
      });
      state.startedAt = performance.now();
      kick(1, 0);
    }

    function kick(a, t) { alpha = Math.max(alpha, a); target = t; state.kickedAt = performance.now(); state.settleMs = null;
      if (!running) { running = true; last = performance.now(); requestAnimationFrame(frame); } }

    function tick() {
      var i, j, n, m, dx, dy, d2, f, l, k;
      for (i = 0; i < nodes.length; i++) {
        n = nodes[i];
        for (j = i + 1; j < nodes.length; j++) {
          m = nodes[j]; dx = m.x - n.x; dy = m.y - n.y; d2 = dx * dx + dy * dy;
          if (d2 < 36) d2 = 36;
          f = ((n.kind === "metric" || m.kind === "metric") ? 260 : 110) * scale * scale * alpha / d2;
          n.vx -= dx * f; n.vy -= dy * f; m.vx += dx * f; m.vy += dy * f;
        }
      }
      for (i = 0; i < links.length; i++) {
        l = links[i]; dx = l.t.x + l.t.vx - l.s.x - l.s.vx; dy = l.t.y + l.t.vy - l.s.y - l.s.vy;
        var d = Math.sqrt(dx * dx + dy * dy) || 1, L = (LINK_LEN[l.kind] || 60) * scale;
        f = (d - L) / d * alpha * 0.35 * 0.5; dx *= f; dy *= f;
        l.t.vx -= dx; l.t.vy -= dy; l.s.vx += dx; l.s.vy += dy;
      }
      var tol = (state.ringStep || 80) * 0.38;
      for (i = 0; i < nodes.length; i++) {
        n = nodes[i]; var R = ringR[n.ring] || 0, r = Math.sqrt(n.x * n.x + n.y * n.y) || 1, off = r - R;
        if (R === 0) { k = alpha * 0.2; n.vx -= n.x * k; n.vy -= n.y * k; }
        else if (Math.abs(off) > tol) { k = (off > 0 ? off - tol : off + tol) / r * alpha * 0.12; n.vx -= n.x * k; n.vy -= n.y * k; }
        if (n.fx != null) { n.x = n.fx; n.y = n.fy; n.vx = n.vy = 0; continue; }
        n.vx *= VELOCITY_KEEP; n.vy *= VELOCITY_KEEP; n.x += n.vx; n.y += n.vy;
        // keep room for the label, which sits to the right of most nodes
        n.x = Math.max(-w / 2 + 24, Math.min(w / 2 - 160, n.x));
        n.y = Math.max(-h / 2 + 22, Math.min(h / 2 - 36, n.y));
      }
      // Keep the drawing centred (as d3-force's centre force does), except while the user holds a node.
      if (!nodes.some(function (q) { return q.fx != null; })) {
        var mx = 0, my = 0;
        for (i = 0; i < nodes.length; i++) { mx += nodes[i].x; my += nodes[i].y; }
        mx = mx / nodes.length * 0.1; my = my / nodes.length * 0.1;
        for (i = 0; i < nodes.length; i++) { nodes[i].x -= mx; nodes[i].y -= my; }
      }
      alpha += (target - alpha) * DECAY;
      state.ticks++;
    }

    function draw() {
      for (var i = 0; i < links.length; i++) {
        var l = links[i];
        l.el.setAttribute("x1", l.s.x); l.el.setAttribute("y1", l.s.y); l.el.setAttribute("x2", l.t.x); l.el.setAttribute("y2", l.t.y);
        if (l.rank) { l.rank.setAttribute("x", (l.s.x * 0.45 + l.t.x * 0.55)); l.rank.setAttribute("y", (l.s.y * 0.45 + l.t.y * 0.55) - 3); }
      }
      for (var j = 0; j < nodes.length; j++) { var n = nodes[j]; n.el.setAttribute("transform", "translate(" + n.x + "," + n.y + ")"); keep[n.id] = n; }
    }

    function frame(now) {
      var steps = Math.min(4, Math.max(1, Math.round((now - last) / TICK_MS))); last = now;
      for (var s = 0; s < steps; s++) tick();
      draw();
      if (alpha < ALPHA_MIN && target === 0) {
        running = false; state.settledAt = performance.now(); state.settleMs = state.settledAt - state.kickedAt; return;
      }
      requestAnimationFrame(frame);
    }

    function point(evt) {
      var p = svg.createSVGPoint(); p.x = evt.clientX; p.y = evt.clientY;
      return p.matrixTransform(svg.getScreenCTM().inverse());
    }
    function drag(n) {
      var start = null, moved = false;
      n.el.addEventListener("pointerdown", function (e) {
        e.preventDefault(); start = { x: e.clientX, y: e.clientY }; moved = false; n.el.setPointerCapture(e.pointerId);
      });
      n.el.addEventListener("pointermove", function (e) {
        if (!start) return;
        if (!moved && Math.hypot(e.clientX - start.x, e.clientY - start.y) < 3) return;
        moved = true; var p = point(e); n.fx = p.x; n.fy = p.y; n.el.style.cursor = "grabbing"; kick(0.3, 0.3);
      });
      n.el.addEventListener("pointerup", function () {
        if (!start) return; start = null; n.el.style.cursor = "";
        if (moved) { n.fx = n.fy = null; target = 0; state.kickedAt = performance.now(); }
        else { pulse(n.id); onSelect(n.data, neighbors(n.id)); }
      });
    }

    function neighbors(id) {
      var out = [];
      links.forEach(function (l) { if (l.s.id === id) out.push(l.t.data); else if (l.t.id === id) out.push(l.s.data); });
      return out;
    }

    function lit(ids) {
      var on = {}; (ids || []).forEach(function (x) { on[x] = 1; });
      var any = (ids || []).some(function (x) { return byId[x]; });
      svg.classList.toggle("dimmed", any);
      nodes.forEach(function (n) { n.el.classList.toggle("lit", !!on[n.id]); });
      links.forEach(function (l) {
        var both = !!(on[l.s.id] && on[l.t.id]);
        l.el.classList.toggle("lit", both);
        if (l.rank) l.rank.classList.toggle("lit", both);
      });
    }
    function pulse(id) {
      var n = byId[id]; if (!n) return;
      n.el.classList.remove("pulse"); void n.el.getBoundingClientRect(); n.el.classList.add("pulse");
      setTimeout(function () { n.el.classList.remove("pulse"); }, 650);
    }

    window.addEventListener("resize", function () { resize(); kick(0.15, 0); });
    return { setData: setData, lit: lit, pulse: pulse, neighbors: neighbors, state: state,
             onSelect: function (fn) { onSelect = fn; }, has: function (id) { return !!byId[id]; } };
  }

  window.AIBGraph = { create: create };
})();

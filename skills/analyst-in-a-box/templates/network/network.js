"use strict";
(() => {
const D = JSON.parse(document.getElementById("aib-data").textContent);
const UI = D.ui;
const $ = (id) => document.getElementById(id);
const svg = $("canvas");
const stage = $("stage");
const panel = $("panel");
const NS = svg.namespaceURI;
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const up8 = (v) => Math.ceil(v / 8) * 8;
const tierName = (t) => UI["tier_" + t];

function make(tag, attrs, parent, text) {
  const n = document.createElementNS(NS, tag);
  for (const k in attrs || {}) n.setAttribute(k, attrs[k]);
  if (text != null) n.textContent = text;
  if (parent) parent.appendChild(n);
  return n;
}
function h(tag, cls, text, parent) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  if (parent) parent.appendChild(n);
  return n;
}
function seeded(seed) {
  return () => {
    seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/* Physics, written from the public parameters of d3-force (ISC licence; documentation at d3js.org/d3-force).
   Its documented defaults: alpha 1, alphaMin 0.001, alphaDecay 1 - alphaMin^(1/300) (about 0.0228),
   alphaTarget 0, velocityDecay 0.4, link distance 30, link strength 1 / min(degree of its two ends),
   many-body strength -30, centre strength 1, positional force strength 0.1. */
/* Our own choices, with what we measured (headless Chrome, 1440x900, both demo workspaces, both views):
   - 160 ticks to alphaMin instead of 300: a tick is 1/60 s, so the layout is still for good after 160/60 = 2.67 s.
     Measured from the first frame to "settled": 2686 to 2696 ms. With 300 ticks it would take about 5 s.
   - the cards are about 100 x 60 px, far bigger than d3's unit-size nodes, so link distances are 144 to 184 px and the
     many-body strength is -900 (reach 700 px) instead of -30.
   - velocity is kept at 0.6 per tick, d3's 1 - velocityDecay (0.4).
   - rectangle collision runs every tick at half strength, then 40 full passes once the layout stops, so no two cards overlap.
   - reduced motion runs the same ticks in a loop before the first paint: 2 to 4 ms measured. */
const STEP_MS = 1000 / 60;
const ALPHA_MIN = 0.001;
const SETTLE_TICKS = 160;
const ALPHA_DECAY = 1 - Math.pow(ALPHA_MIN, 1 / SETTLE_TICKS);
const VELOCITY_KEEP = 0.6;
const DRAG_TARGET = 0.12;
const P = { charge: -900, reach: 700, centre: 0.08, row: 0.22, level: 0.22, cross: 0.2, time: 0.12, pad: 16, speed: 48, spread: 2.6, kMin: 0.7 };
const LINK_DIST = { formula: 144, cut: 184, relation: 152, about: 160 };

/* ---------- text and card size ---------- */
const FONT = getComputedStyle(document.body).fontFamily;
const ctx = document.createElement("canvas").getContext("2d");
const textW = (s, px) => { ctx.font = px + "px " + FONT; return ctx.measureText(s).width; };
const CJK = /[\u2E80-\u9FFF\uF900-\uFAFF\uFF00-\uFFEF]/;
const NO_LINE_START = /^[，。、；：！？）》」』”’,.;:!?)\]%]/;

function tokens(s) {
  const out = [];
  let word = "";
  for (const ch of s) {
    if (CJK.test(ch)) { if (word) out.push(word); word = ""; out.push(ch); }
    else if (ch === " ") { if (word) out.push(word); word = ""; out.push(" "); }
    else word += ch;
  }
  if (word) out.push(word);
  return out;
}
function wrap(s, px, maxW, maxLines) {
  const lines = [];
  let cur = "";
  const toks = tokens(s);
  for (let i = 0; i < toks.length; i++) {
    let t = toks[i];
    if (t === " " && !cur) continue;
    if (textW(cur + t, px) <= maxW || (NO_LINE_START.test(t) && cur)) { cur += t; continue; }
    if (cur.trim()) { lines.push(cur.trim()); cur = ""; if (lines.length === maxLines) break; }
    while (t !== " " && textW(t, px) > maxW) {
      let cut = t.length - 1;
      while (cut > 1 && textW(t.slice(0, cut), px) > maxW) cut--;
      lines.push(t.slice(0, cut)); t = t.slice(cut);
      if (lines.length === maxLines) break;
    }
    if (lines.length === maxLines) break;
    cur = t === " " ? "" : t;
  }
  if (cur.trim() && lines.length < maxLines) lines.push(cur.trim());
  if (lines.length > maxLines) lines.length = maxLines;
  const used = lines.join("").replace(/\s/g, "").length;
  if (used < s.replace(/\s/g, "").length) {
    let last = lines[lines.length - 1];
    while (last.length > 1 && textW(last + "…", px) > maxW) last = last.slice(0, -1);
    lines[lines.length - 1] = last.replace(/[，。、；：,.;:\s]+$/, "") + "…";
  }
  return lines.length ? lines : [""];
}

const RADIUS = { entity: 28, dimension: 28, metric: 8, mechanism: 4, event: 14, action: 8 };
function measure(d) {
  const compact = d.kind === "entity" || d.kind === "dimension";
  const lines = wrap(d.label, 13, compact ? 144 : 200, 2);
  const badge = d.tier === "fact" ? "" : UI["badge_" + d.tier];
  const badgeW = badge ? textW(badge, 10) + 12 : 0;
  const tagW = textW(d.tag, 10) + (badge ? badgeW + 8 : d.tier === "fact" ? 16 : 0);
  const body = Math.max(tagW, ...lines.map((l) => textW(l, 13)));
  return { lines, badge, badgeW, w: Math.max(96, up8(body + 32)), h: lines.length > 1 ? 72 : 56 };
}

function cardDom(n, parent) {
  const d = n.d;
  const g = make("g", {
    "class": `node ${d.tier} k-${d.kind}`, tabindex: 0, role: "button",
    "aria-label": `${d.tag}: ${d.full}. ${tierName(d.tier)}`, "data-id": d.id, "data-tier": d.tier, "data-kind": d.kind,
  }, parent);
  make("title", {}, g, `${d.full} (${tierName(d.tier)})`);
  const r = RADIUS[d.kind] || 8;
  make("rect", { "class": "ring", x: -3, y: -3, width: n.w + 6, height: n.h + 6, rx: r + 3 }, g);
  make("rect", { "class": "card", width: n.w, height: n.h, rx: r }, g);
  if (d.north) make("rect", { "class": "bar", x: 0, y: 12, width: 4, height: n.h - 24, rx: 2 }, g);
  make("text", { "class": "tag", x: 16, y: 20 }, g, d.tag);
  if (n.badge) {
    const bx = n.w - 16 - n.badgeW;
    make("rect", { "class": "badge-bg", x: bx, y: 8, width: n.badgeW, height: 16, rx: 8 }, g);
    make("text", { "class": "badge badge-line", x: bx + n.badgeW / 2, y: 20, "text-anchor": "middle" }, g, n.badge);
  } else if (d.tier === "fact") {
    make("path", { d: `M${n.w - 25} 14 l3 3 l6 -7`, fill: "none", stroke: "#1D3D63", "stroke-width": 1.6, "stroke-linecap": "round", "stroke-linejoin": "round" }, g);
  }
  n.lines.forEach((l, i) => make("text", { x: 16, y: 40 + i * 18 }, g, l));
  return g;
}

/* ---------- one view: nodes, links, world size ---------- */
const defs = make("defs", {}, svg);
const arrow = make("marker", { id: "arr", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 8, markerHeight: 8, orient: "auto" }, defs);
make("path", { d: "M1 1 L9 5 L1 9", fill: "none", stroke: "#8FA2B8", "stroke-width": 1.4 }, arrow);
const vp = make("g", { id: "vp" }, svg);
const views = {};
let cur = null;
const stageBox = () => { const b = stage.getBoundingClientRect(); return { w: b.width, h: b.height }; };

/* ---------- the tree: one level per formula depth, the cut dimensions last ---------- */
/* Levels are columns on a landscape stage and rows on a portrait one. Cards of one level are ordered by the mean
   position of their neighbours in the level before and after (a few barycentre sweeps, which removes most crossings),
   then given an even slot. A level too crowded for the stage is split into staggered sub-rows. */
function treeSize(v, sz) {
  const land = sz.w >= sz.h;
  const kMin = sz.w < 560 ? 0.55 : P.kMin;
  const M = 48, gap = P.pad + 8, gapSub = 24, gapLevel = 88;
  const metrics = v.nodes.filter((n) => n.d.kind !== "dimension");
  const levels = [...new Set(metrics.map((n) => n.d.depth))].sort((a, b) => a - b).map((d) => metrics.filter((n) => n.d.depth === d));
  const nMetric = levels.length;
  const dims = v.nodes.filter((n) => n.d.kind === "dimension");
  if (dims.length) levels.push(dims);
  const rank = new Map();
  const setRank = (lv) => lv.forEach((n, i) => rank.set(n, (i + 0.5) / lv.length));
  levels.forEach(setRank);
  const mean = (n, from) => {
    const r = from.map((m) => rank.get(m));
    return r.length ? r.reduce((a, b) => a + b, 0) / r.length : rank.get(n);
  };
  const parents = (n) => v.links.filter((l) => l.d.kind === "formula" && l.t === n).map((l) => l.s);
  const children = (n) => v.links.filter((l) => l.d.kind === "formula" && l.s === n).map((l) => l.t);
  const sortBy = (lv, f) => { const k = new Map(lv.map((n) => [n, f(n)])); lv.sort((a, b) => k.get(a) - k.get(b)); setRank(lv); };
  for (let pass = 0; pass < 4; pass++) {
    for (let i = 1; i < nMetric; i++) sortBy(levels[i], (n) => mean(n, parents(n)));
    for (let i = nMetric - 2; i >= 0; i--) sortBy(levels[i], (n) => mean(n, children(n)));
  }
  if (dims.length) sortBy(dims, (n) => mean(n, v.links.filter((l) => l.d.kind === "cut" && l.t === n).map((l) => l.s)));

  const cs = (n) => (land ? n.h : n.w), th = (n) => (land ? n.w : n.h);
  /* On a wide stage the cut cards form a row along the bottom edge when the row fits, so their links drop down instead of
     running through every metric column. */
  let band = false;
  const dh = dims.length ? Math.max(...dims.map((n) => n.h)) + 72 : 0;
  if (land && dims.length) {
    const metricLen = 2 * M + (levels.length - 2) * gapLevel + levels.slice(0, -1).reduce((a, lv) => a + Math.max(...lv.map(th)), 0);
    band = dims.length * (Math.max(...dims.map((n) => n.w)) + gap) - gap + 2 * M <= metricLen;
  }
  const avail = (land ? sz.h : sz.w) / kMin - 2 * M - (band ? dh : 0);
  let L = 2 * M + (levels.length - 1 - (band ? 1 : 0)) * gapLevel, C = 0;
  for (const lv of band ? levels.slice(0, -1) : levels) {
    const maxC = Math.max(...lv.map(cs)), maxT = Math.max(...lv.map(th));
    const cap = Math.max(1, Math.floor((avail + gap) / (maxC + gap)));
    lv.sub = Math.ceil(lv.length / cap);
    const per = Math.ceil(lv.length / lv.sub);
    L += lv.sub * maxT + (lv.sub - 1) * gapSub;
    C = Math.max(C, per * maxC + (per - 1) * gap);
  }
  v.tl = { levels, land, M, gapSub, band };
  C += 2 * M + (band ? dh : 0);
  return land ? { W: L, H: C } : { W: C, H: L };
}

function crossCount(v) {
  const o = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  const seg = v.links.map((l) => ({ s: l.s, t: l.t, a: [l.s.gx, l.s.gy], b: [l.t.gx, l.t.gy] }));
  let n = 0;
  for (let i = 0; i < seg.length; i++) {
    for (let j = i + 1; j < seg.length; j++) {
      const p = seg[i], q = seg[j];
      if (p.s === q.s || p.s === q.t || p.t === q.s || p.t === q.t) continue;
      if (o(p.a, p.b, q.a) * o(p.a, p.b, q.b) < 0 && o(q.a, q.b, p.a) * o(q.a, q.b, p.b) < 0) n++;
    }
  }
  return n;
}

function treePlace(v) {
  const { levels: all, land, M, gapSub, band } = v.tl;
  const levels = band ? all.slice(0, -1) : all;
  const bandLv = band ? all[all.length - 1] : null;
  const Lt = land ? v.W : v.H;
  const Ct = (land ? v.H : v.W) - (band ? Math.max(...bandLv.map((n) => n.h)) + 72 : 0);
  const th = levels.map((lv) => Math.max(...lv.map((n) => (land ? n.w : n.h))));
  const used = levels.reduce((a, lv, i) => a + lv.sub * th[i] + (lv.sub - 1) * gapSub, 0);
  const gapLevel = levels.length > 1 ? (Lt - 2 * M - used) / (levels.length - 1) : 0;
  const start = [];
  let pos = M;
  levels.forEach((lv, i) => { start[i] = pos; pos += lv.sub * th[i] + (lv.sub - 1) * gapSub + gapLevel; });
  const put = (n, i, j, lv) => {
    if (lv === bandLv) { n.gx = M + (j + 0.5) * (Lt - 2 * M) / lv.length; n.gy = v.H - M - n.h / 2; return; }
    const r = j % lv.sub, c = Math.floor(j / lv.sub), count = Math.ceil((lv.length - r) / lv.sub);
    const along = start[i] + r * (th[i] + gapSub) + th[i] / 2;
    const across = M + (c + 0.5) * (Ct - 2 * M) / count;
    n.gx = land ? along : across; n.gy = land ? across : along;
  };
  all.forEach((lv, i) => lv.forEach((n, j) => put(n, i, j, lv)));

  /* Order inside each level decides most crossings, above all through the many cut links. Start from the barycentre
     order, then for each level in turn try every order (up to 7 cards; beyond that keep swapping neighbours while it
     helps) and keep the one with fewest crossings. Repeat until a whole round changes nothing. */
  let total = crossCount(v);
  for (let round = 0; round < 4; round++) {
    let improved = false;
    all.forEach((lv, li) => {
      if (lv.length < 2) return;
      const apply = (order) => order.forEach((n, j) => put(n, li, j, lv));
      let best = lv.slice();
      const tryOrder = (order) => { apply(order); const c = crossCount(v); if (c < total) { total = c; best = order.slice(); improved = true; } };
      if (lv.length <= 7) {
        const rec = (rest, acc) => { if (!rest.length) return tryOrder(acc); rest.forEach((n, k) => rec(rest.filter((_, m) => m !== k), [...acc, n])); };
        rec(lv, []);
      } else {
        for (let again = true, guard = 0; again && guard < 20; guard++) {
          again = false;
          for (let k = 0; k + 1 < best.length; k++) {
            const o = best.slice(); [o[k], o[k + 1]] = [o[k + 1], o[k]];
            const before = total; tryOrder(o); if (total < before) again = true;
          }
        }
      }
      lv.splice(0, lv.length, ...best);
      apply(best);
    });
    if (!improved) break;
  }
  for (const l of v.links) l.dist = Math.hypot(l.s.gx - l.t.gx, l.s.gy - l.t.gy);
}

function createView(key) {
  const data = D.views[key];
  const v = { key, data, nodes: [], links: [], byId: new Map(), alpha: 1, target: 0, started: false, settled: false,
              ticks: 0, hover: null, sel: null, moved: false, rnd: seeded(key === "tree" ? 7 : 11) };
  const order = key === "tree" ? [...data.nodes].sort((a, b) => a.depth - b.depth) : data.nodes;
  for (const d of order) {
    const n = { d, id: d.id, x: 0, y: 0, vx: 0, vy: 0, fx: null, fy: null, live: true, nb: new Set(), inc: [], deg: 0, ...measure(d) };
    v.nodes.push(n);
    v.byId.set(d.id, n);
  }
  const pairs = new Map();
  for (const e of data.edges) {
    const s = v.byId.get(e.s), t = v.byId.get(e.t);
    if (!s || !t) continue;
    const l = { d: e, s, t, live: true, bend: 0 };
    const pk = s.id < t.id ? s.id + "|" + t.id : t.id + "|" + s.id;
    const list = pairs.get(pk) || [];
    list.push(l);
    pairs.set(pk, list);
    v.links.push(l);
    s.inc.push(l); t.inc.push(l); s.nb.add(t); t.nb.add(s);
  }
  for (const list of pairs.values()) list.forEach((l, i) => { l.bend = 0.14 + 0.12 * (i - (list.length - 1) / 2) * 2; });

  const sz = stageBox();
  const area = v.nodes.reduce((a, n) => a + (n.w + P.pad) * (n.h + P.pad), 0) * P.spread;
  let W = Math.sqrt(area * sz.w / sz.h), H = area / W;
  if (key === "tree") { const need = treeSize(v, sz); W = need.W; H = need.H; }
  const kMin = sz.w < 560 ? 0.55 : P.kMin;
  v.k = clamp(Math.min(sz.w / W, sz.h / H), kMin, 1.2);
  W = Math.max(W, sz.w / v.k); H = Math.max(H, sz.h / v.k);
  v.W = W; v.H = H;
  v.fitK = Math.min(sz.w / W, sz.h / H);
  v.tx = (sz.w - W * v.k) / 2; v.ty = (sz.h - H * v.k) / 2;

  const mx = 120, ax = data.axis;
  for (const n of v.nodes) {
    n.x = 48 + v.rnd() * (W - 96);
    n.y = 48 + v.rnd() * (H - 96);
    if (key === "tree") {
      continue;
    } else if (n.d.kind === "event") {
      n.ty = H - 128; n.rowK = P.row * 2;
      if (ax && n.d.t != null) { n.tx = ax.max > ax.min ? mx + (n.d.t - ax.min) / (ax.max - ax.min) * (W - 2 * mx) : W / 2; }
    } else if (n.d.kind === "mechanism" || n.d.kind === "action") {
      n.ty = H * 0.16; n.rowK = P.row / 3;
    }
  }

  if (key === "tree") treePlace(v);
  v.g = make("g", { "class": "view", "data-view": key }, vp);
  v.gAxis = make("g", { "class": "axis" }, v.g);
  v.gEdges = make("g", {}, v.g);
  v.gNodes = make("g", {}, v.g);
  if (ax) {
    const y = H - 44;
    make("line", { x1: mx - 48, x2: W - mx + 48, y1: y, y2: y }, v.gAxis);
    for (const n of v.nodes) if (n.tx != null) make("line", { x1: n.tx, x2: n.tx, y1: y - 4, y2: y + 4 }, v.gAxis);
    make("text", { x: mx, y: y + 20 }, v.gAxis, ax.from);
    if (ax.to !== ax.from) make("text", { x: W - mx, y: y + 20 }, v.gAxis, ax.to);
  }
  for (const l of v.links) l.el = linkDom(l, v.gEdges);
  for (const n of v.nodes) n.el = cardDom(n, v.gNodes);
  wireNodes(v);
  return v;
}

/* ---------- links ---------- */
function linkDom(l, parent) {
  const e = l.d;
  const g = make("g", { "class": `edge-g k-${e.kind}`, "data-id": e.id, "data-s": e.s, "data-t": e.t }, parent);
  l.hit = make("path", { "class": "edge-hit" }, g);
  l.path = make("path", { "class": `edge ${e.tier}` }, g);
  if (e.kind === "relation") l.path.setAttribute("marker-end", "url(#arr)");
  make("title", {}, l.hit, `${e.full} (${tierName(e.tier)})`);
  if (e.kind === "formula" || e.kind === "cut") {
    if (e.glyph) {
      l.gbg = make("circle", { "class": "edge-glyph-bg", r: 9 }, g);
      l.gtx = make("text", { "class": "edge-glyph" }, g, e.glyph);
    }
  } else if (e.glyph) {
    l.txt = make("text", { "class": "edge-text" }, g, e.glyph);
  }
  return g;
}

function edgePoint(n, tx, ty) {
  const cx = n.x + n.w / 2, cy = n.y + n.h / 2, dx = tx - cx, dy = ty - cy;
  if (!dx && !dy) return [cx, cy];
  const s = Math.min(dx ? (n.w / 2 + 2) / Math.abs(dx) : Infinity, dy ? (n.h / 2 + 2) / Math.abs(dy) : Infinity);
  return [cx + dx * s, cy + dy * s];
}

function drawLink(l) {
  if (!l.live) return;
  const sc = [l.s.x + l.s.w / 2, l.s.y + l.s.h / 2], tc = [l.t.x + l.t.w / 2, l.t.y + l.t.h / 2];
  const bend = l.bend * Math.hypot(tc[0] - sc[0], tc[1] - sc[1]) * 0.25;
  const mid = [(sc[0] + tc[0]) / 2, (sc[1] + tc[1]) / 2];
  const len = Math.hypot(tc[0] - sc[0], tc[1] - sc[1]) || 1;
  const ctl = [mid[0] - (tc[1] - sc[1]) / len * bend, mid[1] + (tc[0] - sc[0]) / len * bend];
  const a = edgePoint(l.s, ctl[0], ctl[1]), b = edgePoint(l.t, ctl[0], ctl[1]);
  const d = `M${a[0].toFixed(1)} ${a[1].toFixed(1)} Q${ctl[0].toFixed(1)} ${ctl[1].toFixed(1)} ${b[0].toFixed(1)} ${b[1].toFixed(1)}`;
  l.path.setAttribute("d", d); l.hit.setAttribute("d", d);
  const u = l.d.kind === "cut" ? 0.72 : 0.5;
  const m = [(1 - u) * (1 - u) * a[0] + 2 * (1 - u) * u * ctl[0] + u * u * b[0], (1 - u) * (1 - u) * a[1] + 2 * (1 - u) * u * ctl[1] + u * u * b[1]];
  if (l.gbg) { l.gbg.setAttribute("cx", m[0]); l.gbg.setAttribute("cy", m[1]); l.gtx.setAttribute("x", m[0]); l.gtx.setAttribute("y", m[1]); }
  if (l.txt) { l.txt.setAttribute("x", m[0]); l.txt.setAttribute("y", m[1] - 6); }
}

function paint(v) {
  for (const n of v.nodes) if (n.live) n.el.setAttribute("transform", `translate(${n.x.toFixed(1)} ${n.y.toFixed(1)})`);
  for (const l of v.links) drawLink(l);
}

/* ---------- forces ---------- */
const cx = (n) => n.x + n.w / 2;
const cy = (n) => n.y + n.h / 2;

function collide(v, strength) {
  const live = v.nodes.filter((n) => n.live);
  for (let i = 0; i < live.length; i++) {
    for (let j = i + 1; j < live.length; j++) {
      const a = live[i], b = live[j];
      const ox = (a.w + b.w) / 2 + P.pad - Math.abs(cx(a) - cx(b));
      const oy = (a.h + b.h) / 2 + P.pad - Math.abs(cy(a) - cy(b));
      if (ox <= 0 || oy <= 0) continue;
      const wa = a.fx != null ? 0 : 1, wb = b.fx != null ? 0 : 1;
      if (wa + wb === 0) continue;
      const share = strength / (wa + wb);
      if (ox < oy) {
        const dir = cx(a) === cx(b) ? (i % 2 ? 1 : -1) : Math.sign(cx(b) - cx(a));
        a.x -= dir * ox * share * wa; b.x += dir * ox * share * wb;
      } else {
        const dir = cy(a) === cy(b) ? (j % 2 ? 1 : -1) : Math.sign(cy(b) - cy(a));
        a.y -= dir * oy * share * wa; b.y += dir * oy * share * wb;
      }
    }
  }
}

function keepInside(v) {
  for (const n of v.nodes) {
    if (!n.live || n.fx != null) continue;
    n.x = clamp(n.x, 8, v.W - n.w - 8);
    n.y = clamp(n.y, 8, v.H - n.h - (v.data.axis ? 72 : 8));
  }
}

function tick(v) {
  v.alpha += (v.target - v.alpha) * ALPHA_DECAY;
  const a = v.alpha;
  const live = v.nodes.filter((n) => n.live);
  for (const l of v.links) {
    if (!l.live) continue;
    const s = l.s, t = l.t;
    let dx = cx(t) + t.vx - cx(s) - s.vx, dy = cy(t) + t.vy - cy(s) - s.vy;
    const len = Math.hypot(dx, dy) || 1e-6;
    const k = (len - (l.dist || LINK_DIST[l.d.kind])) / len * a / Math.min(s.deg, t.deg) * (l.d.kind === "cut" ? 0.4 : 1);
    dx *= k; dy *= k;
    const bias = s.deg / (s.deg + t.deg);
    t.vx -= dx * bias; t.vy -= dy * bias; s.vx += dx * (1 - bias); s.vy += dy * (1 - bias);
  }
  for (let i = 0; i < live.length; i++) {
    for (let j = i + 1; j < live.length; j++) {
      const p = live[i], q = live[j];
      const dx = cx(q) - cx(p), dy = cy(q) - cy(p);
      const d2 = dx * dx + dy * dy + 1;
      if (d2 > P.reach * P.reach) continue;
      const w = P.charge * a / d2;
      p.vx += dx * w; p.vy += dy * w; q.vx -= dx * w; q.vy -= dy * w;
    }
  }
  for (const n of live) {
    if (n.gx != null) {
      const along = Math.max(a, 0.3) * 4 * P.level, across = a * 4 * P.cross;
      n.vx += (n.gx - cx(n)) * (v.tl.land ? along : across);
      n.vy += (n.gy - cy(n)) * (v.tl.land ? across : along);
      continue;
    }
    n.vx += (v.W / 2 - cx(n)) * P.centre * a;
    n.vy += (v.H / 2 - cy(n)) * P.centre * a;
    if (n.ty != null) n.vy += (n.ty - cy(n)) * n.rowK * a * 4;
    if (n.tx != null) n.vx += (n.tx - cx(n)) * P.time * a * 4;
  }
  for (const n of live) {
    if (n.fx != null) { n.x = n.fx; n.y = n.fy; n.vx = n.vy = 0; continue; }
    n.vx *= VELOCITY_KEEP; n.vy *= VELOCITY_KEEP;
    const sp = Math.hypot(n.vx, n.vy);
    if (sp > P.speed) { n.vx *= P.speed / sp; n.vy *= P.speed / sp; }
    n.x += n.vx; n.y += n.vy;
  }
  collide(v, 0.5);
  keepInside(v);
  v.ticks++;
}

function finish(v) {
  for (let i = 0; i < 40; i++) { collide(v, 1); keepInside(v); }
  v.alpha = 0; v.settled = true;
  paint(v);
  if (v.t0 != null && v.msToSettle == null) v.msToSettle = Math.round(performance.now() - v.t0);
  if (cur === v) document.body.dataset.settled = "1";
  if (cur === v && v.msToSettle != null) document.body.dataset.msToSettle = String(v.msToSettle);
}

let raf = 0, last = 0, acc = 0;
function frame(now) {
  raf = 0;
  const v = cur;
  if (!v) return;
  acc += Math.min(now - last, 100); last = now;
  let steps = 0;
  while (acc >= STEP_MS && steps < 4) { tick(v); acc -= STEP_MS; steps++; }
  paint(v);
  if (v.alpha < ALPHA_MIN && v.target === 0) finish(v); else raf = requestAnimationFrame(frame);
}
function heat(v, a, target) {
  v.alpha = Math.max(v.alpha, a);
  if (target != null) v.target = target;
  v.settled = false;
  delete document.body.dataset.settled;
  if (reduce) { runToEnd(v); return; }
  if (!raf && cur === v) { last = performance.now(); acc = 0; raf = requestAnimationFrame(frame); }
}
function runToEnd(v) {
  v.target = 0;
  for (let i = 0; i < 2000 && v.alpha >= ALPHA_MIN; i++) tick(v);
  finish(v);
}

/* ---------- highlight, drag, pan, zoom ---------- */
function applyTransform(v) { vp.setAttribute("transform", `translate(${v.tx.toFixed(1)} ${v.ty.toFixed(1)}) scale(${v.k.toFixed(4)})`); }

function highlight(v) {
  const focus = v.hover || v.sel;
  v.g.classList.toggle("dim", !!focus);
  const nodes = new Set(), links = new Set();
  if (focus) {
    if (focus.nb) { nodes.add(focus); focus.nb.forEach((m) => nodes.add(m)); focus.inc.forEach((l) => links.add(l)); }
    else { links.add(focus); nodes.add(focus.s); nodes.add(focus.t); }
  }
  for (const n of v.nodes) n.el.classList.toggle("on", nodes.has(n));
  for (const l of v.links) l.el.classList.toggle("on", links.has(l));
}

function toWorld(v, ev) {
  const b = svg.getBoundingClientRect();
  return [(ev.clientX - b.left - v.tx) / v.k, (ev.clientY - b.top - v.ty) / v.k];
}

function wireNodes(v) {
  for (const n of v.nodes) {
    const el = n.el;
    el.addEventListener("pointerenter", (e) => { if (e.pointerType === "mouse" && !drag) { v.hover = n; highlight(v); } });
    el.addEventListener("pointerleave", () => { if (v.hover === n) { v.hover = null; highlight(v); } });
    el.addEventListener("focus", () => { v.hover = n; highlight(v); });
    el.addEventListener("blur", () => { if (v.hover === n) { v.hover = null; highlight(v); } });
    el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(v, n, true); } });
    el.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      e.stopPropagation();
      const [wx, wy] = toWorld(v, e);
      drag = { v, n, ox: wx - n.x, oy: wy - n.y, sx: e.clientX, sy: e.clientY, on: false, id: e.pointerId };
      el.setPointerCapture(e.pointerId);
    });
  }
  for (const l of v.links) {
    l.hit.addEventListener("click", () => select(v, l, false));
    l.hit.addEventListener("pointerenter", () => { if (!drag) { v.hover = l; highlight(v); } });
    l.hit.addEventListener("pointerleave", () => { if (v.hover === l) { v.hover = null; highlight(v); } });
  }
}

let drag = null, pan = null;
const pointers = new Map();
let pinch = null;

svg.addEventListener("pointermove", (e) => {
  const v = cur;
  if (!v) return;
  if (pointers.has(e.pointerId)) pointers.set(e.pointerId, [e.clientX, e.clientY]);
  if (drag && e.pointerId === drag.id) {
    if (!drag.on && Math.hypot(e.clientX - drag.sx, e.clientY - drag.sy) > 4) {
      drag.on = true; drag.n.fx = drag.n.x; drag.n.fy = drag.n.y; v.hover = null; highlight(v);
      heat(v, DRAG_TARGET, DRAG_TARGET);
    }
    if (drag.on) {
      const [wx, wy] = toWorld(v, e);
      drag.n.fx = clamp(wx - drag.ox, 8, v.W - drag.n.w - 8); drag.n.fy = clamp(wy - drag.oy, 8, v.H - drag.n.h - (v.data.axis ? 72 : 8));
      if (reduce) { drag.n.x = drag.n.fx; drag.n.y = drag.n.fy; paint(v); }
    }
  } else if (pinch && pointers.size === 2) {
    const [a, b] = [...pointers.values()];
    const dist = Math.hypot(a[0] - b[0], a[1] - b[1]);
    zoomAt(v, v.k * dist / pinch.dist, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2);
    pinch.dist = dist;
  } else if (pan) {
    v.tx += e.clientX - pan.x; v.ty += e.clientY - pan.y; pan.x = e.clientX; pan.y = e.clientY;
    v.moved = true; applyTransform(v);
  }
});
svg.addEventListener("pointerdown", (e) => {
  if (!cur || (e.target.closest && e.target.closest(".node"))) return;
  pointers.set(e.pointerId, [e.clientX, e.clientY]);
  if (pointers.size === 2) { const [a, b] = [...pointers.values()]; pinch = { dist: Math.hypot(a[0] - b[0], a[1] - b[1]) }; pan = null; return; }
  pan = { x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY };
  svg.classList.add("panning");
});
function endPointer(e) {
  const v = cur;
  pointers.delete(e.pointerId);
  if (pointers.size < 2) pinch = null;
  if (drag && e.pointerId === drag.id) {
    const d = drag; drag = null;
    if (d.on) { d.n.fx = d.n.fy = null; heat(d.v, 0.06, 0); }
    else select(d.v, d.n, false);
  }
  if (pan) {
    const moved = Math.hypot(e.clientX - pan.sx, e.clientY - pan.sy) > 4;
    pan = null; svg.classList.remove("panning");
    if (!moved && v && v.sel && e.type === "pointerup") closePanel(false);
  }
}
svg.addEventListener("pointerup", endPointer);
svg.addEventListener("pointercancel", endPointer);

function zoomAt(v, k, px, py) {
  const b = svg.getBoundingClientRect();
  const nk = clamp(k, Math.min(0.3, v.fitK), 2.4);
  const x = px - b.left, y = py - b.top;
  v.tx = x - (x - v.tx) * nk / v.k; v.ty = y - (y - v.ty) * nk / v.k; v.k = nk; v.moved = true;
  applyTransform(v);
}
function zoomBy(f) { const b = stage.getBoundingClientRect(); if (cur) zoomAt(cur, cur.k * f, b.left + b.width / 2, b.top + b.height / 2); }
svg.addEventListener("wheel", (e) => { if (!cur) return; e.preventDefault(); zoomAt(cur, cur.k * Math.exp(-e.deltaY * 0.0015), e.clientX, e.clientY); }, { passive: false });
$("zin").onclick = () => zoomBy(1.25);
$("zout").onclick = () => zoomBy(0.8);
$("zfit").onclick = () => {
  const v = cur; if (!v) return;
  const sz = stageBox();
  v.k = v.fitK; v.tx = (sz.w - v.W * v.k) / 2; v.ty = (sz.h - v.H * v.k) / 2; v.moved = false; applyTransform(v);
};

/* ---------- detail panel ---------- */
let opener = null;
function section(parent, title) { const s = h("div", "sec", null, parent); h("h3", null, title, s); return s; }

function openPanel(v, item, byKeyboard) {
  const d = item.d;
  const isNode = !!item.nb;
  $("p-tag").textContent = d.tag;
  $("p-title").textContent = d.full;
  const ban = $("p-banner");
  ban.className = "p-banner " + d.tier;
  ban.textContent = UI["banner_" + d.tier];
  const body = $("p-body");
  body.textContent = "";
  if (d.status) {
    const s = section(body, UI.status);
    h("p", null, UI["status_" + d.status] || d.status, s);
  }
  if (d.facts && d.facts.length) {
    const s = h("div", "sec", null, body);
    const dl = h("dl", "kv", null, s);
    for (const [k, val] of d.facts) { h("dt", null, k, dl); h("dd", null, val, dl); }
  }
  const s = section(body, UI.source);
  if (d.sources && d.sources.length) {
    for (const src of d.sources) {
      const box = h("div", "src", null, s);
      h("p", null, [src.kind_text, src.name].filter(Boolean).join(" · ") + (src.date ? ` · ${src.date}` : ""), box);
      if (src.what) h("small", null, src.what, box);
      if (src.quote) h("p", "quote", src.quote, box);
      if (src.note) h("small", null, src.note, box);
    }
  } else if (d.no_source) {
    h("p", null, UI.no_source, s);
  }
  if (d.note) h("p", null, d.note, s);
  if (!s.querySelector("p, small")) s.remove();
  if (d.refuted_by) h("p", null, d.refuted_by, section(body, UI.refuted));
  const links = isNode ? item.inc : [];
  const rel = isNode ? links.map((l) => [l.s === item ? l.t : l.s, l]) : [[item.s, item], [item.t, item]];
  if (rel.length) {
    const box = h("div", "links", null, section(body, UI.connected));
    for (const [other, l] of rel.filter(([o, l]) => o.live && l.live)) {
      const b = h("button", null, other.d.full, box);
      b.type = "button";
      h("small", null, `  ${other.d.tag} · ${tierName(other.d.tier)}`, b);
      b.onclick = () => select(v, other, false);
    }
  }
  panel.hidden = false;
  panel.dataset.tier = d.tier;
  if (byKeyboard) { opener = item.el; $("p-title").tabIndex = -1; $("p-title").focus(); }
}

function select(v, item, byKeyboard) {
  if (v.sel && v.sel.el) v.sel.el.classList.remove("sel");
  v.sel = item;
  if (item.nb) item.el.classList.add("sel"); else item.el.classList.add("sel");
  openPanel(v, item, byKeyboard);
  highlight(v);
  if (item.nb) reveal(v, item);
}
function closePanel(restore) {
  const v = cur;
  panel.hidden = true;
  if (v && v.sel) { v.sel.el.classList.remove("sel"); v.sel = null; highlight(v); }
  if (restore && opener) opener.focus();
  opener = null;
}
$("p-close").onclick = () => closePanel(true);
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) closePanel(true); });

function reveal(v, n) {
  const sz = stageBox();
  const pw = panel.offsetWidth, ph = panel.offsetHeight, phone = sz.w <= 720;
  const free = phone ? { l: 0, t: 0, r: sz.w, b: sz.h - ph - 8 } : { l: 0, t: 0, r: sz.w - pw - 16, b: sz.h };
  const x = (n.x + n.w / 2) * v.k + v.tx, y = (n.y + n.h / 2) * v.k + v.ty;
  const mx = n.w / 2 * v.k + 16, my = n.h / 2 * v.k + 16;
  const dx = x < free.l + mx ? free.l + mx - x : x > free.r - mx ? free.r - mx - x : 0;
  const dy = y < free.t + my ? free.t + my - y : y > free.b - my ? free.b - my - y : 0;
  if (dx || dy) { v.tx += dx; v.ty += dy; v.moved = true; applyTransform(v); }
}

/* ---------- filter, counts, tabs ---------- */
const hideBox = $("hide-inference");
function applyFilter(v) {
  const hide = hideBox.checked;
  for (const n of v.nodes) {
    n.live = !(hide && n.d.tier === "inference");
    n.el.style.display = n.live ? "" : "none";
  }
  for (const l of v.links) {
    l.live = l.s.live && l.t.live && !(hide && l.d.tier === "inference");
    l.el.style.display = l.live ? "" : "none";
  }
  for (const n of v.nodes) n.deg = 0;
  for (const l of v.links) if (l.live) { l.s.deg++; l.t.deg++; }
  for (const n of v.nodes) n.deg = Math.max(n.deg, 1);
  if (v.sel && !(v.sel.nb ? v.sel.live : v.sel.live)) closePanel(false);
}
function counts(v) {
  const c = { fact: 0, confirm: 0, inference: 0, retired: 0, none: 0 };
  for (const n of v.nodes) if (n.live) c[n.d.tier]++;
  const nl = v.links.filter((l) => l.live).length;
  $("counts").textContent = `${v.nodes.filter((n) => n.live).length} ${UI.cards} · ${nl} ${UI.links} · ` +
    ["fact", "confirm", "inference", "retired", "none"].filter((t) => c[t]).map((t) => `${tierName(t)} ${c[t]}`).join(" · ");
}

hideBox.addEventListener("change", () => {
  for (const key in views) applyFilter(views[key]);
  if (cur) { counts(cur); highlight(cur); paint(cur); heat(cur, 0.5); }
});

function setView(key) {
  if (cur) { cur.g.style.display = "none"; if (raf) { cancelAnimationFrame(raf); raf = 0; } }
  document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.view === key)));
  const empty = $("empty");
  if (!D.views[key].nodes.length) {
    cur = null; vp.style.display = "none"; empty.hidden = false; empty.textContent = UI["empty_" + key]; $("counts").textContent = "";
    document.body.dataset.settled = "1";
    return;
  }
  empty.hidden = true; vp.style.display = "";
  const first = !views[key];
  if (first) views[key] = createView(key);
  const v = cur = views[key];
  v.g.style.display = "";
  closePanel(false);
  applyFilter(v);
  counts(v);
  applyTransform(v);
  document.body.dataset.view = key;
  if (first) {
    v.started = true; v.t0 = performance.now();
    paint(v);
    heat(v, 1);
  } else {
    highlight(v); paint(v);
    if (v.alpha >= ALPHA_MIN || v.target) heat(v, v.alpha); else document.body.dataset.settled = "1";
  }
}
document.querySelectorAll(".tabs button").forEach((b) => {
  b.addEventListener("click", () => { setView(b.dataset.view); history.replaceState(null, "", "#" + b.dataset.view); });
  b.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    const tabs = [...document.querySelectorAll(".tabs button")], i = tabs.indexOf(b);
    tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length].focus();
  });
});
let rz = 0;
addEventListener("resize", () => {
  clearTimeout(rz);
  rz = setTimeout(() => {
    const v = cur; if (!v || v.moved) return;
    const sz = stageBox();
    v.tx = (sz.w - v.W * v.k) / 2; v.ty = (sz.h - v.H * v.k) / 2; applyTransform(v);
  }, 150);
});
if (matchMedia("(max-width: 720px)").matches) $("legend").open = false;
setView(location.hash === "#world" ? "world" : "tree");
})();

// Business knowledge graph page: switch views, highlight one question's path, show a node's details.
// Layout and words are computed at build time (site/graphdata.py, site/pages_more.py); this file only toggles classes.
(function () {
  "use strict";
  const D = JSON.parse(document.getElementById("gm-data").textContent);
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const root = $(".gm");
  const views = { tree: $("#view-tree"), world: $("#view-world") };
  const canvas = { tree: $(".gm-tree"), world: $(".gm-world") };
  const tabs = $$(".gm-views [role=tab]");
  const pick = $("#gm-case");
  const panel = $("#gm-detail");
  let view = "tree", kase = "", picked = null, opener = null;

  // ---------- views
  function setView(v, focus) {
    view = v;
    root.dataset.view = v;
    tabs.forEach((t) => {
      const on = t.dataset.view === v;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.tabIndex = on ? 0 : -1;
      if (on && focus) t.focus();
    });
    Object.entries(views).forEach(([k, el]) => (el.hidden = k !== v));
    closeDetail(false);
    save();
  }
  tabs.forEach((t, i) => {
    t.addEventListener("click", () => setView(t.dataset.view));
    t.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
      e.preventDefault();
      setView(tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length].dataset.view, true);
    });
  });

  // ---------- one question's path
  function clearCase() {
    Object.values(canvas).forEach((c) => c.classList.remove("gm-on"));
    $$(".lit").forEach((el) => el.classList.remove("lit"));
    $$(".gm-chip.scope").forEach((el) => el.classList.remove("scope"));
    $$(".gm-chip[title]").forEach((el) => el.removeAttribute("title"));
    $$("[data-val]").forEach((el) => { el.textContent = ""; el.className = "gm-val"; });
    const w = $("#gm-window");
    w.setAttribute("height", "0");
    $("#gm-path").hidden = true;
    $("#gm-steps").replaceChildren();
  }

  function lightEdges(c, lit) {
    $$(".gm-e", c).forEach((e) => {
      if (lit.has(e.dataset.from) && lit.has(e.dataset.to)) e.classList.add("lit");
    });
  }

  function setCase(k) {
    kase = k;
    pick.value = k;
    closeDetail(false);
    clearCase();
    if (k && D.cases[k]) {
      const c = D.cases[k];
      const tl = new Set(c.tree), wl = new Set(c.world);
      canvas.tree.classList.add("gm-on");
      canvas.world.classList.add("gm-on");
      $$(".gm-node", canvas.tree).forEach((n) => tl.has(n.dataset.id) && n.classList.add("lit"));
      $$(".gm-node", canvas.world).forEach((n) => wl.has(n.dataset.id) && n.classList.add("lit"));
      lightEdges(canvas.tree, tl);
      lightEdges(canvas.world, wl);
      $$(".gm-op", canvas.tree).forEach((o) => {
        const kids = $$(`.gm-e[data-from="${o.dataset.from}"]`, canvas.tree);
        if (kids.some((e) => e.classList.contains("lit"))) o.classList.add("lit");
      });
      $$(".gm-evspan", canvas.world).forEach((s) => wl.has(s.dataset.from) && s.classList.add("lit"));
      c.chips.forEach((id) => { const el = $(`[data-chip="${id}"]`); if (el) el.classList.add("lit"); });
      c.scope.forEach((id) => { const el = $(`[data-chip="${id}"]`); if (el) el.classList.add("scope"); });
      Object.entries(c.notes).forEach(([id, t]) => { const el = $(`[data-chip="${id}"]`); if (el) el.title = t; });
      Object.entries(c.values).forEach(([id, v]) => {
        const el = $(`[data-val="${id}"]`);
        if (el) { el.textContent = v.t; el.className = "gm-val " + v.c; }
      });
      const w = $("#gm-window");
      w.setAttribute("y", c.window.y0);
      w.setAttribute("height", Math.max(c.window.y1 - c.window.y0, 3));
      const tpl = document.getElementById("steps-" + k);
      $("#gm-steps").replaceChildren(tpl.content.cloneNode(true));
      $("#gm-path").hidden = false;
    }
    save();
  }
  pick.addEventListener("change", () => setCase(pick.value));
  $("#gm-clear").addEventListener("click", () => { setCase(""); pick.focus(); });

  // ---------- details
  function neighbours(id) {
    const out = new Set([id]);
    D.edges[view].forEach((e) => {
      if (e.from === id) out.add(e.to);
      if (e.to === id) out.add(e.from);
    });
    return out;
  }

  function openDetail(id, btn) {
    const d = D.details[id];
    if (!d) return;
    const c = canvas[view];
    $$(".picked, .near").forEach((el) => el.classList.remove("picked", "near"));
    const near = neighbours(id);
    $$(".gm-node", c).forEach((n) => {
      if (n.dataset.id === id) n.classList.add("picked");
      else if (near.has(n.dataset.id)) n.classList.add("near");
    });
    $$(".gm-e", c).forEach((e) => {
      if (e.dataset.from === id || e.dataset.to === id) e.classList.add("near");
    });
    c.classList.add("gm-sel");
    $("#gm-detail-k").textContent = d.kind;
    $("#gm-detail-h").textContent = d.title;
    const dl = $("#gm-detail-dl");
    dl.replaceChildren();
    d.rows.forEach(([k, v]) => {
      const dt = document.createElement("dt");
      dt.textContent = k;
      const dd = document.createElement("dd");
      dd.textContent = v;
      dl.append(dt, dd);
    });
    // open on the side away from the node, so the panel never covers what was clicked
    const r = (btn || $(`[data-node="${id}"]`)).getBoundingClientRect();
    panel.classList.toggle("left", r.left + r.width / 2 > innerWidth / 2);
    panel.hidden = false;
    picked = id;
    opener = btn || null;
    $("#gm-close").focus({ preventScroll: true });
  }

  function closeDetail(refocus = true) {
    if (panel.hidden) return;
    panel.hidden = true;
    Object.values(canvas).forEach((c) => c.classList.remove("gm-sel"));
    $$(".picked, .near").forEach((el) => el.classList.remove("picked", "near"));
    if (refocus && opener) opener.focus({ preventScroll: true });
    picked = null;
  }
  $$(".gm-hit").forEach((b) => b.addEventListener("click", () => (picked === b.dataset.node ? closeDetail() : openDetail(b.dataset.node, b))));
  $("#gm-close").addEventListener("click", () => closeDetail());
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDetail(); });

  // ---------- state in the address (#view=world&q=east_last_week), so a highlighted path can be linked to
  function save() {
    const p = new URLSearchParams();
    if (view !== "tree") p.set("view", view);
    if (kase) p.set("q", kase);
    const h = p.toString();
    history.replaceState(null, "", h ? "#" + h : location.pathname + location.search);
  }
  const p = new URLSearchParams(location.hash.slice(1));
  setView(views[p.get("view")] ? p.get("view") : "tree");
  setCase(D.cases[p.get("q")] ? p.get("q") : "");
})();

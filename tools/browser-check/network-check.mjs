// Opens knowledge.html pages from file:// in headless Chrome and checks what a visitor would hit.
//   node network-check.mjs [PAGE.html ...]      (default: build both demo workspaces into /tmp/aib-net first)
// Checks: nodes drawn; legend; tier filter; panel on click and Esc; Tab + Enter; no console errors; no horizontal
// scroll at 390 px; settled layout has no overlapping cards and no label wider than its card; reduced motion
// settles at once. Screenshots go to /tmp/aib-net/. Exit code 1 when a check fails.
import { chromium } from "playwright-core";
import { existsSync, mkdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../..");
const OUT = "/tmp/aib-net";
mkdirSync(OUT, { recursive: true });
const CHROME = process.env.CHROME || ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium"].find(existsSync);

let pages = process.argv.slice(2);
if (!pages.length) {
  for (const d of ["store", "intake"]) for (const l of ["en", "zh"]) {
    const out = path.join(OUT, `${d}-${l}.html`);
    execFileSync("uv", ["run", "--frozen", "python", "skills/analyst-in-a-box/scripts/aib_cli.py", "network", "--workspace", `demo/${d}/workspace`, "--lang", l, "--out", out], { cwd: root, stdio: "pipe" });
    pages.push(out);
  }
}

const results = [];
const add = (page, what, pass, detail = "") => { results.push({ page, what, pass, detail }); if (!pass) console.log(`FAIL ${page}: ${what} ${detail}`); };
const browser = await chromium.launch({ executablePath: CHROME, headless: true });

async function open(file, viewport, opts = {}) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: viewport.width < 500 ? 2 : 1, ...opts });
  const page = await ctx.newPage();
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("requestfailed", (r) => errors.push("failed: " + r.url()));
  const t0 = Date.now();
  await page.goto(pathToFileURL(file).href);
  return { ctx, page, errors, t0 };
}
const settle = (page) => page.waitForFunction(() => document.body.dataset.settled === "1", null, { timeout: 15000 });

// Cards that overlap, and labels wider than their card, measured on the settled layout in screen pixels.
const geometry = () => {
  const view = document.querySelector(".view:not([style*='none'])");
  const cards = [...view.querySelectorAll(".node")].filter((n) => n.style.display !== "none").map((n) => ({ id: n.dataset.id, r: n.querySelector(".card").getBoundingClientRect(), n }));
  const overlaps = [];
  for (let i = 0; i < cards.length; i++) for (let j = i + 1; j < cards.length; j++) {
    const a = cards[i].r, b = cards[j].r;
    const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left), oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    if (ox > 0.5 && oy > 0.5) overlaps.push(cards[i].id + " × " + cards[j].id);
  }
  const wide = [];
  for (const c of cards) for (const t of c.n.querySelectorAll("text")) {
    const r = t.getBoundingClientRect();
    if (r.right > c.r.right + 0.5 || r.left < c.r.left - 0.5) wide.push(c.id);
  }
  return { count: cards.length, overlaps, wide };
};

// Pairs of always-visible links that cross, not counting links that share a card (each link sampled as 16 short segments).
const crossings = () => {
  const view = document.querySelector(".view:not([style*='none'])");
  const links = [...view.querySelectorAll(".edge-g")].filter((g) => g.style.display !== "none" && getComputedStyle(g).visibility !== "hidden").map((g) => {
    const path = g.querySelector(".edge"), len = path.getTotalLength(), pts = [];
    for (let i = 0; i <= 16; i++) { const q = path.getPointAtLength(len * i / 16); pts.push([q.x, q.y]); }
    return { s: g.dataset.s, t: g.dataset.t, pts };
  });
  const o = (p, q, r) => (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]);
  const x = (a, b, c, d) => o(a, b, c) * o(a, b, d) < 0 && o(c, d, a) * o(c, d, b) < 0;
  let n = 0;
  for (let i = 0; i < links.length; i++) for (let j = i + 1; j < links.length; j++) {
    const A = links[i], B = links[j];
    if (A.s === B.s || A.s === B.t || A.t === B.s || A.t === B.t) continue;
    let hit = false;
    for (let a = 0; a < 16 && !hit; a++) for (let b = 0; b < 16 && !hit; b++) hit = x(A.pts[a], A.pts[a + 1], B.pts[b], B.pts[b + 1]);
    if (hit) n++;
  }
  return n;
};
// Crossings of the tree view before the hierarchical layout (force layout only), measured on the demo workspaces.
// (all links drawn then, cut links included; since then the cut links show only on hover, so the count is of formula links)
const TREE_BEFORE = { store: { 1440: 21, 390: 14 }, intake: { 1440: 125, 390: 127 } };
// Soft: a count that is not lower than before is reported but does not fail the run.
const soft = (page, width, n) => {
  const before = TREE_BEFORE[page.split("-")[0]]?.[width];
  if (before == null) return;
  const ok = n < before;
  console.log(`${ok ? "ok  " : "WARN"} ${page}: tree link crossings at ${width} px: ${n} (before ${before})`);
  results.push({ page, what: `tree crossings ${width}px`, pass: true, detail: `${n} vs ${before}` });
};

for (const file of pages) {
  const name = path.basename(file, ".html");
  const { ctx, page, errors, t0 } = await open(file, { width: 1440, height: 900 });
  await settle(page);
  const ms = await page.evaluate(() => Number(document.body.dataset.msToSettle));
  add(name, "settles within 3.5 s", ms > 0 && ms <= 3500, `measured ${ms} ms (wall clock ${Date.now() - t0} ms)`);
  add(name, "legend lists five tiers", (await page.locator("#legend li").count()) === 5);
  for (const view of ["tree", "world"]) {
    await page.locator(`#tab-${view}`).click();
    await settle(page);
    const g = await page.evaluate(geometry);
    add(name, `${view}: nodes drawn`, g.count > 0, `${g.count}`);
    if (view === "tree") {
      soft(name, 1440, await page.evaluate(crossings));
      const cutVisible = () => page.evaluate(() => [...document.querySelectorAll(".view:not([style*='none']) .edge-g.k-cut")].filter((g) => getComputedStyle(g).visibility !== "hidden").length);
      const cutTotal = await page.locator(".view:not([style*='none']) .edge-g.k-cut").count();
      add(name, "tree: cut links hidden by default", (await cutVisible()) === 0, `${cutTotal} cut links`);
      const target = page.locator(".view:not([style*='none']) .node[data-kind='metric']", { has: page.locator("xpath=.") }).first();
      const dimNode = page.locator(".view:not([style*='none']) .node[data-kind='dimension']").first();
      await dimNode.hover();
      const shown = await cutVisible();
      add(name, "tree: hovering a dimension shows its cut links", shown > 0 && shown < cutTotal || cutTotal === shown && shown > 0, `${shown} of ${cutTotal}`);
      await page.screenshot({ path: path.join(OUT, `${name}-tree-hover-1440.png`) });
      await page.mouse.move(5, 5);
      await dimNode.focus();
      add(name, "tree: keyboard focus shows cut links", (await cutVisible()) > 0);
      await page.locator("#canvas").evaluate((e) => document.activeElement && document.activeElement.blur());
      void target;
    }
    add(name, `${view}: no overlapping cards`, g.overlaps.length === 0, g.overlaps.slice(0, 4).join("; "));
    add(name, `${view}: label inside its card`, g.wide.length === 0, g.wide.slice(0, 4).join("; "));
    const tiers = await page.evaluate(() => [...new Set([...document.querySelectorAll(".view:not([style*='none']) .node")].map((n) => n.dataset.tier))]);
    await page.screenshot({ path: path.join(OUT, `${name}-${view}-1440.png`) });

    const hideBox = page.locator("#hide-inference");
    const inf = await page.locator(`.view:not([style*='none']) .node[data-tier='inference']`).count();
    if (inf) {
      await hideBox.check();
      const shown = await page.locator(`.view:not([style*='none']) .node[data-tier='inference']:visible`).count();
      add(name, `${view}: filter hides AI inference`, shown === 0, `${inf} → ${shown}`);
      await settle(page);
      await page.screenshot({ path: path.join(OUT, `${name}-${view}-no-inference-1440.png`) });
      await hideBox.uncheck();
      await settle(page);
    }

    const first = page.locator(".view:not([style*='none']) .node").first();
    await first.click();
    const open1 = await page.locator("#panel").isVisible();
    const banner = await page.locator("#p-banner").textContent();
    add(name, `${view}: click opens the panel with a tier banner`, open1 && banner.length > 5, banner);
    if (view === "world") await page.screenshot({ path: path.join(OUT, `${name}-${view}-panel-1440.png`) });
    await page.keyboard.press("Escape");
    add(name, `${view}: Esc closes the panel`, !(await page.locator("#panel").isVisible()));
    await page.locator("#canvas").focus();
    await page.keyboard.press("Tab");
    const focusedNode = await page.evaluate(() => document.activeElement && document.activeElement.classList.contains("node"));
    add(name, `${view}: Tab reaches a node`, focusedNode);
    await page.keyboard.press("Enter");
    add(name, `${view}: Enter opens the panel`, await page.locator("#panel").isVisible());
    await page.keyboard.press("Escape");
    void tiers;
  }
  add(name, "no console errors", errors.length === 0, errors.join(" | "));
  await ctx.close();

  // dragging moves a card, re-heats the layout and it settles again
  {
    const c = await open(file, { width: 1440, height: 900 });
    await settle(c.page);
    const node = c.page.locator(".view:not([style*='none']) .node").nth(2);
    const b0 = await node.locator(".card").boundingBox();
    await c.page.mouse.move(b0.x + b0.width / 2, b0.y + b0.height / 2);
    await c.page.mouse.down();
    await c.page.mouse.move(b0.x + b0.width / 2 + 120, b0.y + b0.height / 2 + 60, { steps: 8 });
    await c.page.waitForTimeout(100);
    const heated = await c.page.evaluate(() => document.body.dataset.settled !== "1");
    const b1 = await node.locator(".card").boundingBox();
    await c.page.mouse.up();
    await settle(c.page);
    add(name, "drag moves the card and re-heats", Math.hypot(b1.x - b0.x, b1.y - b0.y) > 40 && heated, `moved ${Math.round(Math.hypot(b1.x - b0.x, b1.y - b0.y))} px, heated=${heated}`);
    const g = await c.page.evaluate(geometry);
    add(name, "after a drag: no overlapping cards", g.overlaps.length === 0, g.overlaps.slice(0, 3).join("; "));
    await c.ctx.close();
  }

  // phone width
  {
    const c = await open(file, { width: 390, height: 844 }, { hasTouch: true });
    await settle(c.page);
    const sw = await c.page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
    add(name, "390 px: no horizontal scroll", sw.sw <= sw.cw, `${sw.sw} > ${sw.cw}`);
    soft(name, 390, await c.page.evaluate(crossings));
    const tapped = await c.page.evaluateHandle(() => [...document.querySelectorAll(".view:not([style*='none']) .node[data-kind='dimension']")].find((n) => { const r = n.getBoundingClientRect(), s = document.getElementById("stage").getBoundingClientRect(); return r.left > s.left + 8 && r.right < s.right - 8 && r.top > s.top + 8 && r.bottom < s.bottom - 8; }));
    if (tapped.asElement()) {
      await tapped.asElement().tap();
      const vis = await c.page.evaluate(() => [...document.querySelectorAll(".view:not([style*='none']) .edge-g.k-cut")].filter((g) => getComputedStyle(g).visibility !== "hidden").length);
      add(name, "390 px: tapping a dimension shows its cut links", vis > 0, `${vis}`);
      await c.page.screenshot({ path: path.join(OUT, `${name}-tree-tap-390.png`) });
      await c.page.keyboard.press("Escape");
    }
    await c.page.screenshot({ path: path.join(OUT, `${name}-tree-390.png`) });
    await c.page.locator("#tab-world").click();
    await settle(c.page);
    const sw2 = await c.page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
    add(name, "390 px world: no horizontal scroll", sw2);
    await c.page.screenshot({ path: path.join(OUT, `${name}-world-390.png`) });
    const onScreen = await c.page.evaluateHandle(() => [...document.querySelectorAll(".view:not([style*='none']) .node")].find((n) => { const r = n.getBoundingClientRect(), s = document.getElementById("stage").getBoundingClientRect(); return r.left > s.left + 8 && r.right < s.right - 8 && r.top > s.top + 8 && r.bottom < s.bottom - 8; }));
    await onScreen.asElement().tap();
    add(name, "390 px: tap opens the panel", await c.page.locator("#panel").isVisible());
    await c.page.screenshot({ path: path.join(OUT, `${name}-world-panel-390.png`) });
    add(name, "390 px: no console errors", c.errors.length === 0, c.errors.join(" | "));
    await c.ctx.close();
  }

  // reduced motion: the settled layout is there at once
  {
    const c = await open(file, { width: 1440, height: 900 }, { reducedMotion: "reduce" });
    await settle(c.page);
    const ms = await c.page.evaluate(() => Number(document.body.dataset.msToSettle));
    const g = await c.page.evaluate(geometry);
    add(name, "reduced motion: settled in one go, no overlaps", ms < 1500 && g.overlaps.length === 0, `${ms} ms`);
    await c.ctx.close();
  }
}
await browser.close();
const failed = results.filter((r) => !r.pass);
console.log(`${results.length - failed.length}/${results.length} checks passed; screenshots in ${OUT}`);
process.exit(failed.length ? 1 : 0);

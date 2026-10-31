// Open every built page in a headless browser and check what a visitor would hit.
//   cd tools/browser-check && npm install && node check.mjs
// Pages: the ones site/build.py renders itself, plus every page listed in pages-more.json (built by pages_more.py).
// Fails (exit 1) when any check fails. Checks, numbered as in the site's acceptance list:
//   1 at 1440×900 the first screen shows a real conclusion with a number, and the install command (home page)
//   2 at 390 wide no horizontal scroll and no visible text under 12px
//   3 text contrast at least 4.5:1
//   4 no internal terms or raw field names in the visible text
//   5 no console errors, page errors or missing files
//   6 Chinese and English pages have the same sections (same count of h2, same section ids)
//   7 no share above 100%; no "share of" figure with a sign opposite to the change it belongs to
//   8 every case report has a waterfall, a daily chart and a breakdown tree, all drawn
import { chromium } from "playwright-core";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const dist = path.resolve(here, "../../site/dist");
const CHROME = process.env.CHROME || ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium"].find(existsSync);
if (!existsSync(path.join(dist, "index.html"))) { console.error("site/dist is empty: run uv run python site/build.py first"); process.exit(1); }

const CASES = ["revenue_last_week", "east_last_week", "aov_last_week", "june_price_volume", "app_vs_web"];
const MINE = ["index.html", ...CASES.map((c) => `reports/${c}.html`), "reports/public.html"];
const moreFile = path.join(here, "pages-more.json");
// The nav also links the other builder's pages; check them even before pages-more.json lists them.
const NAV_MORE = ["graph.html", "intake.html", "learning.html", "architecture.html"];
const MORE = [...new Set([...(existsSync(moreFile) ? JSON.parse(readFileSync(moreFile, "utf8")).pages.map((p) => p.path) : []), ...NAV_MORE])];
const all = [...MINE, ...MORE];
const missing = all.flatMap((p) => [p, "en/" + p]).filter((p) => !existsSync(path.join(dist, p)));
const pages = all.flatMap((p) => [p, "en/" + p]).filter((p) => existsSync(path.join(dist, p)));

// Words that must not reach a visitor: internal jargon and engine field names (checked on visible text only).
const BANNED = [
  /稳健\s*z/i, /robust\s*z/i, /\bz\s*值/, /\bz-?score/i, /门槛/, /\bpp\b/, /往下钻/, /单点/, /槽位/, /切一刀/, /覆盖率/,
  // "slot" alone is ordinary English (a home-page slot); the engine word shows up as slot_* / slots / slot_label.
  /\bslot(s|_\w+)\b/i, /\bdrill(ed|ing)?\b/i, /\bthreshold\b/i,
  // "dimension=value" written as code, e.g. 渠道=电商平台 or channel=marketplace
  /[\p{L}_]+=[\p{L}_]+/u,
  // engine field names
  /\b(abs_share|base_share|top1_\w+|robust_z|usual_range|unusual_below|unusual_above|current_change|y_delta|label_key|dominant_\w+|explanatory_power|rest_\w+|top_change|mean_before|mean_after|onset|verdict_\w+|within_usual_range|unusual_low|unusual_high|spread_or_noise|single_point\w*|cut_spread|market_explains_little|same_weekdays_364_days|calendar_complete|key_unique|workspace_valid|ev_\w+|act_\w+|mech_\w+)\b/,
];

const results = [];
const add = (page, n, what, pass, detail = "") => results.push({ page, n, what, pass, detail });
for (const p of missing) add(p, 5, "page exists", false, "not built");

const browser = await chromium.launch({ executablePath: CHROME, headless: true });

async function open(ctx, p) {
  const page = await ctx.newPage();
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("requestfailed", (r) => errors.push("failed: " + r.url()));
  await page.goto(pathToFileURL(path.join(dist, p)).href);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(200);
  return { page, errors };
}

// Visible text nodes with their computed size, colour and the colour behind them.
const TEXT_PROBE = () => {
  const parse = (c) => { const m = c.match(/[\d.]+/g); return m ? m.map(Number) : [0, 0, 0, 0]; };
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const blend = (fg, bg) => { const a = fg[3] ?? 1; return [0, 1, 2].map((i) => fg[i] * a + bg[i] * (1 - a)); };
  const bgOf = (el) => {
    const stack = [];
    for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if ((c[3] ?? 1) > 0) stack.push(c); if ((c[3] ?? 1) >= 1) break; }
    let bg = [255, 255, 255];
    for (const c of stack.reverse()) bg = blend(c, bg);
    return bg;
  };
  const out = [];
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    const s = n.textContent.trim();
    if (!s) continue;
    const el = n.parentElement;
    if (el.closest("script, style, noscript, [aria-hidden=true], .skip")) continue;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    if (cs.visibility === "hidden" || cs.display === "none" || r.width === 0 || r.height === 0 || el.closest("[hidden], details:not([open]) > :not(summary)")) continue;
    const isSvg = el instanceof SVGElement;
    const fg = parse(isSvg ? cs.fill : cs.color);
    const bg = bgOf(isSvg ? el.closest("svg").parentElement : el);
    const L1 = lum(blend(fg, bg)), L2 = lum(bg);
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    out.push({ s: s.slice(0, 60), size: parseFloat(cs.fontSize), ratio: +ratio.toFixed(2), opacity: +cs.opacity, top: r.top + scrollY, sel: el.tagName.toLowerCase() + (el.className && typeof el.className === "string" ? "." + el.className.split(" ")[0] : "") });
  }
  return out;
};
const structure = {};
const wide = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const narrow = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });

for (const p of pages) {
  // ---------------- 1440
  const { page, errors } = await open(wide, p);
  const isReport = /^(en\/)?reports\/(?!public)/.test(p);
  if (/(^|\/)index\.html$/.test(p)) {
    const fold = await page.evaluate(() => {
      const vis = (el) => { if (!el) return false; const r = el.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight && r.width > 0; };
      const card = document.querySelector(".session .answer");
      return { title: vis(card && card.querySelector("h2")) && /\d/.test(card.querySelector("h2").textContent),
               big: vis(card && card.querySelector(".big")), cause: vis(card && card.querySelector(".ans-cause")),
               install: vis(document.querySelector("#install")), scrollY };
    });
    const pass = fold.title && fold.big && fold.cause && fold.install;
    add(p, 1, "1440×900 first screen: conclusion with a number, cause and install command", pass, JSON.stringify(fold));
  }
  const texts = await page.evaluate(TEXT_PROBE);
  const low = texts.filter((t) => t.ratio < 4.5 && t.opacity >= 1);
  add(p, 3, "contrast ≥ 4.5:1", low.length === 0, low.slice(0, 5).map((t) => `${t.sel} “${t.s}” ${t.ratio}`).join("; "));
  const body = await page.evaluate(() => {
    document.querySelectorAll("details").forEach((d) => (d.open = true));
    return document.body.innerText + " " + [...document.querySelectorAll("[title],[aria-label]")].map((e) => (e.title || "") + " " + e.getAttribute("aria-label")).join(" ");
  });
  const hits = BANNED.flatMap((re) => { const m = body.match(new RegExp(re.source, re.flags.includes("g") ? re.flags : re.flags + "g")); return m ? m : []; });
  add(p, 4, "no internal terms or field names", hits.length === 0, [...new Set(hits)].slice(0, 8).join(", "));
  const shares = [...body.matchAll(/(?:占[^\d−+\-]{0,8}|share of [a-z ]{0,20})\s*([−+\-]?)(\d+(?:\.\d+)?)%/g)];
  const bad = shares.filter((m) => +m[2] > 100 || m[1]);
  add(p, 7, "shares within 0–100%, unsigned", bad.length === 0, bad.map((m) => m[0]).join("; "));
  if (isReport) {
    const charts = await page.evaluate(() => {
      const drawn = (sel) => [...document.querySelectorAll(sel)].some((el) => el.querySelector("svg"));
      return { waterfall: drawn('[data-chart$=".waterfall"]'), daily: drawn('[data-chart$=".daily"], [data-chart$=".onset"]'),
               tree: !!document.querySelector(".tree-fig .tr-root") && document.querySelectorAll(".tree-fig .tr-node").length > 1 };
    });
    add(p, 8, "waterfall, daily chart and breakdown tree drawn", charts.waterfall && charts.daily && charts.tree, JSON.stringify(charts));
  }
  structure[p] = await page.evaluate(() => ({ h2: document.querySelectorAll("main h2").length,
    ids: [...document.querySelectorAll("main section[id]")].map((s) => s.id), charts: document.querySelectorAll("[data-chart]").length }));
  await page.close();

  // ---------------- 390
  const m = await open(narrow, p);
  const nar = await m.page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
  add(p, 2, "390: no horizontal scroll", nar.sw <= nar.cw, `scrollWidth ${nar.sw}, clientWidth ${nar.cw}`);
  const small = (await m.page.evaluate(TEXT_PROBE)).filter((t) => t.size < 12);
  add(p, 2, "390: no text under 12px", small.length === 0, small.slice(0, 5).map((t) => `${t.sel} “${t.s}” ${t.size}px`).join("; "));
  const all = [...errors, ...m.errors];
  add(p, 5, "no console errors or missing files", all.length === 0, [...new Set(all)].slice(0, 5).join(" | "));
  await m.page.close();
}

// ---------------- 6: language pairs
for (const p of pages.filter((x) => !x.startsWith("en/"))) {
  const a = structure[p], b = structure["en/" + p];
  if (!b) { add(p, 6, "has an English pair", false, "en/" + p + " missing"); continue; }
  const same = a.h2 === b.h2 && a.ids.join() === b.ids.join() && a.charts === b.charts;
  add(p, 6, "Chinese and English sections match", same, `zh ${JSON.stringify(a)} / en ${JSON.stringify(b)}`);
}

// ---------------- links between pages
for (const p of pages) {
  const html = readFileSync(path.join(dist, p), "utf8");
  const broken = [...html.matchAll(/href="([^"#]+?\.html)(#[^"]*)?"/g)].map((m) => m[1]).filter((h) => !/^[a-z]+:/.test(h))
    .filter((h) => !existsSync(path.resolve(path.dirname(path.join(dist, p)), h)));
  add(p, 5, "every internal link points to a built page", broken.length === 0, [...new Set(broken)].join(", "));
}

await browser.close();
const failed = results.filter((r) => !r.pass);
for (const r of results) console.log(`${r.pass ? "✓" : "✗"} [${r.n}] ${r.page}: ${r.what}${r.pass ? "" : " — " + r.detail}`);
console.log(`\n${results.length - failed.length}/${results.length} checks pass on ${pages.length} pages` + (missing.length ? `; ${missing.length} pages not built` : ""));
process.exit(failed.length ? 1 : 0);

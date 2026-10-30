// Open every built page in a headless browser and check what a visitor would hit.
//   cd tools/browser-check && npm install && node check.mjs [--shots DIR]
// Fails (exit 1) on: a script error, a console error, a missing file, a story step that lights nothing,
// or a motion timing outside site/MOTION.md.
import { chromium } from "playwright-core";
import { existsSync, mkdirSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const dist = path.resolve(here, "../../site/dist");
const shotsArg = process.argv.indexOf("--shots");
const shots = shotsArg > 0 ? process.argv[shotsArg + 1] : null;
if (shots) mkdirSync(shots, { recursive: true });
const CHROME = process.env.CHROME || ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium"].find(existsSync);
const OPEN = [3500, 6500], RELEASE = [2500, 5500], CLICK_PX = 1;

const results = [];
const fail = (page, what, detail) => results.push({ page, what, pass: false, detail });
const ok = (page, what, detail) => results.push({ page, what, pass: true, detail });

async function settled(page, name, since) {
  return page.waitForFunction(([n, t]) => {
    const g = (window.__aib?.graphs || []).find(x => x.id === n);
    return g && g.settleMs != null && g.kickedAt >= t ? g.settleMs : false;
  }, [name, since], { timeout: 15000, polling: 100 }).then(h => h.jsonValue());
}

async function positions(page, sel) {
  return page.$$eval(sel + " .node", els => els.map(e => e.getAttribute("transform")));
}

function moved(a, b) {
  let max = 0;
  a.forEach((t, i) => {
    const p = t.match(/-?[\d.]+/g).map(Number), q = (b[i] || t).match(/-?[\d.]+/g).map(Number);
    max = Math.max(max, Math.hypot(p[0] - q[0], p[1] - q[1]));
  });
  return max;
}

async function motion(page, label, svgSel, name) {
  const open = await settled(page, name, 0);
  (open >= OPEN[0] && open <= OPEN[1] ? ok : fail)(label, "opening settles", `${Math.round(open)} ms (target ${OPEN.join("–")})`);
  await page.locator(svgSel).scrollIntoViewIfNeeded();
  const before = await positions(page, svgSel);
  const node = page.locator(svgSel + " .node .hit").first();
  await node.click();
  await page.waitForTimeout(900);
  const shift = moved(before, await positions(page, svgSel));
  (shift <= CLICK_PX ? ok : fail)(label, "click does not move the graph", `${shift.toFixed(2)} px`);
  const box = await node.boundingBox();
  const t0 = await page.evaluate(() => performance.now());
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  for (let i = 1; i <= 10; i++) await page.mouse.move(box.x + box.width / 2 + i * 9, box.y + box.height / 2 + i * 5);
  const during = await positions(page, svgSel);
  await page.mouse.up();
  const rel = await settled(page, name, t0);
  (rel >= RELEASE[0] && rel <= RELEASE[1] ? ok : fail)(label, "after release settles", `${Math.round(rel)} ms (target ${RELEASE.join("–")})`);
  const followers = moved(before, during);
  (followers > 2 ? ok : fail)(label, "neighbours follow a drag", `${followers.toFixed(1)} px`);
}

const browser = await chromium.launch({ executablePath: CHROME, headless: true });
for (const lang of ["zh", "en"]) {
  for (const name of ["index", "graph", "learning", "architecture"]) {
    const file = path.join(dist, lang === "zh" ? "" : "en", name + ".html");
    const label = `${lang}/${name}`;
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const errors = [];
    page.on("pageerror", e => errors.push("pageerror: " + e.message));
    page.on("console", m => { if (m.type() === "error") errors.push("console: " + m.text()); });
    page.on("requestfailed", r => errors.push("missing: " + r.url()));
    await page.goto(pathToFileURL(file).href);
    await page.waitForTimeout(300);
    if (name === "index") {
      const n = await page.locator("#story-graph .node").count();
      (n > 0 ? ok : fail)(label, "story graph draws nodes", `${n} nodes`);
      await motion(page, label, "#story-graph", "story");
      const tabs = await page.locator(".tabs button").count();
      for (let t = 0; t < tabs; t++) {
        await page.locator(".tabs button").nth(t).click();
        await page.waitForTimeout(400);
        const steps = await page.locator(".step").count();
        let dark = 0;
        for (let i = 0; i < steps; i++) {
          await page.locator(".step").nth(i).scrollIntoViewIfNeeded();
          await page.evaluate(i => document.querySelectorAll(".step")[i].scrollIntoView({ block: "center" }), i);
          await page.waitForTimeout(350);
          const on = await page.locator(".step.on").getAttribute("data-i");
          const lit = await page.locator("#story-graph .node.lit").count();
          if (on !== String(i) || lit === 0) dark++;
        }
        (dark === 0 ? ok : fail)(label, `case ${t + 1}: every step activates and lights the graph`, `${steps} steps, ${dark} without light`);
      }
      const stamps = await page.locator(".stamp.ok").count();
      (stamps === tabs ? ok : fail)(label, "answer key: every case matches", `${stamps}/${tabs}`);
    }
    if (name === "graph") {
      await motion(page, label, "#full-graph", "full");
      await page.locator('.views button[data-view="world"]').click();
      await page.waitForTimeout(500);
      const w = await page.locator("#full-graph .node").count();
      (w > 0 ? ok : fail)(label, "world view draws", `${w} nodes`);
      await page.selectOption("#case", { index: 2 });
      const lit = await page.locator("#full-graph .node.lit").count();
      (lit > 0 ? ok : fail)(label, "a question lights its path", `${lit} lit`);
    }
    if (shots) {
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.waitForTimeout(300);
      await page.screenshot({ path: path.join(shots, `${lang}-${name}.png`), fullPage: name !== "graph" });
    }
    (errors.length === 0 ? ok : fail)(label, "no errors, no missing files", errors.slice(0, 5).join(" | ") || "clean");
    await page.close();
  }
}
for (const rep of ["revenue_last_week", "east_last_week", "aov_last_week", "app_vs_web", "public"]) {
  for (const lang of ["zh", "en"]) {
    const page = await browser.newPage();
    const errors = [];
    page.on("requestfailed", r => errors.push(r.url()));
    page.on("pageerror", e => errors.push(e.message));
    await page.goto(pathToFileURL(path.join(dist, "reports", rep, lang + ".html")).href);
    await page.waitForTimeout(200);
    const imgs = await page.$$eval("img", els => els.filter(e => !e.complete || e.naturalWidth === 0).length);
    (errors.length === 0 && imgs === 0 ? ok : fail)(`report/${rep}/${lang}`, "opens with every chart", errors.join(" | ") || `${imgs} broken images`);
    await page.close();
  }
}
await browser.close();
const failed = results.filter(r => !r.pass);
console.log(JSON.stringify({ passed: results.length - failed.length, total: results.length, failed, results }, null, 1));
process.exit(failed.length ? 1 : 0);

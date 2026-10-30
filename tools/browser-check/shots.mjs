// Viewport screenshots of the moments a visitor sees, for a human to look at.
//   node shots.mjs OUT_DIR
import { chromium } from "playwright-core";
import { existsSync, mkdirSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const dist = path.resolve(here, "../../site/dist");
const out = process.argv[2] || "shots";
mkdirSync(out, { recursive: true });
const CHROME = process.env.CHROME || ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome"].find(existsSync);
const browser = await chromium.launch({ executablePath: CHROME, headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });

async function settle(name) {
  await page.waitForFunction(n => (window.__aib?.graphs || []).some(g => g.id === n && g.settleMs != null), name, { timeout: 15000 });
}
const lang = process.argv[3] || "zh";
const base = lang === "zh" ? dist : path.join(dist, "en");
await page.goto(pathToFileURL(path.join(base, "index.html")).href);
await settle("story");
await page.screenshot({ path: path.join(out, `${lang}-1-hero.png`) });
for (const i of [0, 2, 4]) {
  await page.evaluate(i => document.querySelectorAll(".step")[i].scrollIntoView({ block: "center" }), i);
  await page.waitForTimeout(900);
  await page.screenshot({ path: path.join(out, `${lang}-2-step${i + 1}.png`) });
}
await page.locator("#reveal").scrollIntoViewIfNeeded();
await page.evaluate(() => document.getElementById("reveal").scrollIntoView({ block: "start" }));
await page.waitForTimeout(400);
await page.screenshot({ path: path.join(out, `${lang}-3-reveal.png`) });
await page.goto(pathToFileURL(path.join(base, "graph.html")).href);
await settle("full");
await page.screenshot({ path: path.join(out, `${lang}-4-graph-metrics.png`) });
await page.locator('.views button[data-view="world"]').click();
await page.selectOption("#case", { index: 2 });
await page.waitForTimeout(5500);
await page.screenshot({ path: path.join(out, `${lang}-5-graph-world.png`) });
for (const p of ["learning", "architecture"]) {
  await page.goto(pathToFileURL(path.join(base, p + ".html")).href);
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(out, `${lang}-6-${p}.png`) });
}
await page.goto(pathToFileURL(path.join(dist, "reports", "revenue_last_week", lang + ".html")).href);
await page.waitForTimeout(300);
await page.screenshot({ path: path.join(out, `${lang}-7-report.png`) });
await browser.close();

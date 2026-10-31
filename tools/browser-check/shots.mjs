// Screenshots of the built site for a human to look at: first screen and full page at 1440×900 and 390 wide,
// plus every step of the home page's click-through case.
//   node shots.mjs [OUT_DIR]        (default /tmp/aib-site-shots)
import { chromium } from "playwright-core";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const dist = path.resolve(here, "../../site/dist");
const out = process.argv[2] || "/tmp/aib-site-shots";
mkdirSync(out, { recursive: true });
const CHROME = process.env.CHROME || ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome"].find(existsSync);

const mine = ["index.html", "reports/revenue_last_week.html", "reports/east_last_week.html", "reports/aov_last_week.html",
  "reports/june_price_volume.html", "reports/app_vs_web.html", "reports/public.html"];
const more = existsSync(path.join(here, "pages-more.json"))
  ? JSON.parse(readFileSync(path.join(here, "pages-more.json"), "utf8")).pages.map((p) => p.path) : [];
const pages = [...new Set([...mine, ...more, "graph.html", "intake.html", "learning.html", "architecture.html"])].flatMap((p) => [p, "en/" + p]).filter((p) => existsSync(path.join(dist, p)));
const name = (p) => p.replace(/\//g, "_").replace(/\.html$/, "");

const browser = await chromium.launch({ executablePath: CHROME, headless: true });
for (const [vw, vh] of [[1440, 900], [390, 844]]) {
  const page = await browser.newPage({ viewport: { width: vw, height: vh }, deviceScaleFactor: vw < 500 ? 2 : 1 });
  for (const p of pages) {
    await page.goto(pathToFileURL(path.join(dist, p)).href);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(250);
    await page.screenshot({ path: path.join(out, `${name(p)}-${vw}.png`) });
    await page.screenshot({ path: path.join(out, `${name(p)}-${vw}-full.png`), fullPage: true });
    if (p.endsWith("index.html") && vw === 1440) {
      const n = await page.locator("#stepper .st-list button").count();
      for (let i = 0; i < n; i++) {
        await page.locator("#stepper .st-list button").nth(i).click();
        await page.waitForTimeout(150);
        await page.locator("#stepper").screenshot({ path: path.join(out, `${name(p)}-step${i + 1}.png`) });
      }
    }
  }
  await page.close();
}
await browser.close();
console.log(`${pages.length} pages × 2 widths → ${out}`);

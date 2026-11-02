// Design check for the built site: two outside linters that look for the habits of machine-made pages.
//   impeccable 4.8.0 (npm, Apache-2.0): fixed rules, no model. Every finding blocks.
//   hallmark sloplint (vendored, MIT, see vendor/hallmark/SOURCE.md): FAIL and REFLEX block, WARN is only reported.
// A finding can stay only if accepted.json names it and gives a reason a reader could check.
// Usage: node tools/design-check/run.mjs [--verbose]
import { spawnSync } from "node:child_process";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const dist = join(root, "site", "dist");
const verbose = process.argv.includes("--verbose");
const IMPECCABLE = "impeccable@4.8.0";

function htmlFiles(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...htmlFiles(p));
    else if (name.endsWith(".html")) out.push(p);
  }
  return out.sort();
}

function runJson(cmd, args, okCodes) {
  const r = spawnSync(cmd, args, { cwd: dist, encoding: "utf8", maxBuffer: 64 << 20 });
  if (r.error) throw r.error;
  if (!okCodes.includes(r.status)) {
    console.error(r.stderr || r.stdout);
    throw new Error(`${cmd} ${args[0]} exited ${r.status}`);
  }
  return JSON.parse(r.stdout);
}

const accepted = JSON.parse(readFileSync(join(here, "accepted.json"), "utf8"));
for (const a of accepted) {
  if (!a.reason || a.reason.length < 40) throw new Error(`accepted.json: reason too short for ${a.tool} ${a.rule}`);
}
const used = new Set();
function acceptedFor(tool, rule, text, file) {
  const i = accepted.findIndex((a) => a.tool === tool && a.rule === rule
    && (!a.match || text.includes(a.match)) && (!a.file || file.includes(a.file)));
  if (i >= 0) used.add(i);
  return i >= 0;
}

const pages = htmlFiles(dist);
const rel = (p) => relative(dist, p);

// impeccable: exit 0 = clean, 2 = findings.
const imp = runJson("npx", ["-y", IMPECCABLE, "detect", ".", "--json"], [0, 2]).map((x) => ({
  tool: "impeccable", rule: x.antipattern, grade: "block", file: rel(x.file), text: x.snippet,
}));
// hallmark: exit 0 = clean, 1 = findings.
const hm = runJson("node", [join(here, "vendor", "hallmark", "sloplint.mjs"), ...pages, "--json"], [0, 1]).findings.map((x) => ({
  tool: "hallmark", rule: String(x.gate), grade: x.grade === "WARN" ? "report" : "block", file: x.file, text: x.evidence,
}));

const all = [...imp, ...hm];
const blocking = [], kept = [], reported = [];
for (const f of all) {
  if (acceptedFor(f.tool, f.rule, f.text, f.file)) kept.push(f);
  else if (f.grade === "block") blocking.push(f);
  else reported.push(f);
}

function summary(list) {
  const c = new Map();
  for (const f of list) {
    const k = `${f.tool} ${f.rule}`;
    if (!c.has(k)) c.set(k, { n: 0, first: f });
    c.get(k).n++;
  }
  return [...c.entries()].sort((a, b) => b[1].n - a[1].n);
}
function print(title, list, all) {
  console.log(`\n${title}: ${list.length}`);
  for (const [k, { n, first }] of summary(list)) console.log(`  ${String(n).padStart(4)}  ${k.padEnd(28)} ${first.file}: ${first.text}`.slice(0, 200));
  if (all) for (const f of list) console.log(`        ${f.tool} ${f.rule} ${f.file}: ${f.text}`.slice(0, 220));
}

console.log(`design check on ${pages.length} pages (${IMPECCABLE}, hallmark sloplint vendored)`);
print("blocking", blocking, verbose);
print("kept, with a reason in accepted.json", kept, false);
print("reported, not blocking", reported, verbose);
const stale = accepted.filter((_, i) => !used.has(i));
for (const a of stale) console.log(`\naccepted.json entry no longer matches anything, remove it: ${a.tool} ${a.rule} ${a.match || ""}`);
process.exit(blocking.length || stale.length ? 1 : 0);

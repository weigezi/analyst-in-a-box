---
name: analyst-in-a-box
description: Explains why a business number moved (revenue, GMV, orders, average order value, margin, conversion, any KPI) and who should act next, the way a senior business analyst would. Use it whenever someone asks why a metric rose or fell, what drove a change, which channel/region/product is responsible, why one segment grew faster than another, or why growth this period differs from last period; also when they share sales or order data (CSV, Excel, SQLite, DuckDB) and want to understand it, build a metric tree, or set up recurring performance analysis. Works in Chinese too (为什么跌了, 为什么涨了, 异动归因, 贡献度, 拆解, 增速差). Use it even if the user never says "attribution".
license: Apache-2.0 (see LICENSE)
compatibility: Python 3.10+ with pandas, pyyaml and openpyxl (duckdb optional). The scripts run on your machine and make no network calls; your AI tool reads what they print.
metadata:
  version: 0.2.1
---

# analyst-in-a-box

[中文](SKILL.zh.md)

Answer one question well: **why did this number move, and who should do what next.**
The scripts do every calculation. Your job is to frame the question, run the scripts, talk to the user,
and record what they teach you so the next answer is better.

## Ground rules (read these first)

1. **Never do the arithmetic yourself.** Every number you tell the user comes from a script's output.
   Language models get decomposition maths wrong; the scripts check that every breakdown sums to the total.
2. **Never guess what a column or a business term means from its name.** If it is not in the workspace, ask.
   A wrong guess about one column silently corrupts every result after it.
3. **Thresholds belong to the user.** "What counts as a single point", "what counts as unusual": these are
   business judgement. The workspace stores them with their source; never invent one in conversation.
4. **Outside events are hypotheses.** Weather, news, competitors: they only show that timing matches.
   The run decides how they may be worded (three checks: timing, affected slice, size).
5. **Everything the user teaches you goes through `correct`.** That writes it down with their words and makes
   a regression case, so the skill cannot quietly forget it.

## Running the scripts

All commands are run from this skill's folder and print JSON:

```bash
python3 scripts/aib_cli.py <command> --workspace <dir> ...
```

If `import pandas, yaml` fails, install first: `pip install -r scripts/requirements.txt`
(or prefix with `uv run --with-requirements scripts/requirements.txt`).

A **workspace** is one company's knowledge (its metric tree, its world, its corrections). Keep it in the
user's own folder, never inside this skill; ask where if it is not obvious, default `./aib-workspace`.

## 1. First use: from a table to a first answer

Goal: within one conversation the user sees an attribution that is correct and tells them something new.

1. `init <data-file> --workspace <dir> --lang zh|en` reads the table and returns questions. When the user has
   several tables (orders, products, a campaign calendar, a price log, traffic, weather...), give a folder or
   several files. The script finds the main table, the lookups, the links between tables (with coverage), the
   event records and the outside series, and turns each into a multiple-choice question. Show every question
   with its suggested answer and its evidence. Nothing enters the workspace until the user confirms.
   Details: [references/intake.md](references/intake.md).
2. Ask those questions **as multiple choice**, a few at a time, in the user's language. Do not pre-fill
   answers from column names; show the examples the script gives so the user can recognise the column.
3. Put the answers in a JSON file keyed by question `id` and run `confirm --workspace <dir> --answers <file>`.
   It writes the workspace and returns `first_run`.
4. Run it: `run --workspace <dir> --config '<first_run as JSON>'`, then present the report (section 3).
5. Offer, do not force: "Which dimension do you usually look at first?" Their answer is a `set_priority`
   correction (section 4). Business knowledge is asked **when an answer needs it**, never as an upfront survey.
6. If the user gives documents (weekly reports, reviews), **you read them**; the script never does. For every
   event or mechanism that could explain a number, record it with
   `propose --workspace <dir> --doc <file> --file <proposals>`, each with the exact sentence it came from,
   copied as it is. A sentence not in the document is refused. Accepted ones are "from a document, to confirm",
   and they do not count as explained until the user confirms. Never propose a cause the document does not
   state, and never reword the sentence.

## 2. Answering a question

Map the question to a run, then call `run`. Details and edge cases: [references/questions.md](references/questions.md).

| The user asks | Run |
|---|---|
| "Why did revenue fall last week?" | `--metric revenue --current <Mon> <Sun> --base yoy` (or `pop` if they say "vs last week") |
| "Why did the east region fall?" | add `--filter region=east` |
| "Why is Q3 growth lower than Q2?" | second order across time: `--current <Q3> --base yoy --previous` |
| "Why did offline grow faster than online?" | second order across sides: `--compare <id>`; add the comparison to `model.yaml` first if it is missing |
| "Visitors went up but conversion fell" | first order; the formula breakdown in the report answers it |
| "Why did October fall vs September?" (month to date) | `--current <Oct 1> <today> --base pop`: the base is Sep 1 to the same day |
| "Did we sell more, or charge more?" | first order; add a `pvm` entry to `model.yaml` (price-volume-mix) |
| "Is it new customers or lost ones?" | add `"growth_accounting": {"customer_column": "<column the user named>"}` to the config |
| "And inside that, what?" | `followup --from <run_dir> --slot <slot id> [--dimensions d1,d2]` |

If the metric, dimension or comparison does not exist in the workspace, say so and ask; do not approximate
with a different one. Windows of different length are blocked unless the user wants daily averages
(`"per_day": true`); a holiday in one period only is reported with two ways out (`"holiday": "exclude"` or
`"shift_base"`). `followup` keeps the earlier run's filters, periods and path, and records which run it followed.

## 3. Presenting the result

The run writes `report.zh.md`, `report.en.md`, `record.json` and charts. Show the report in the user's
language; it is already ordered conclusion → is it unusual → breakdown → why → who should act.
Keep its numbers exactly; do not round them differently or recompute. Point to the chart files.
How to talk about structure vs rate, shares above 100%, and hypotheses: [references/report.md](references/report.md).

Then handle what the run says it is missing:

- **`gaps`**: the data shows a change nobody has explained. Ask one plain question:
  "New customers' average order fell; do you know why?" Record the answer (section 4) and re-run.
- **`to_confirm`**: entries that are only proposed, including outside events. Ask whether to confirm them.
- **`blocked: true`**: a pre-delivery check failed. Show which one; do not present the conclusions.
- **Data in doubt / data note** (first lines of the conclusion): say this first. "In doubt" stops the report
  (missing days, repeated ids); a "note" is worth checking, but the conclusions still stand. Never explain a
  change the data itself may have made.
- **"Within the usual range"**: say it is normal and do not hunt for a cause, unless the report names one group
  that stands far out from its own swings.
- **A cited record that "cannot explain this change"** (true in both periods): it does not answer the question.
  Ask what changed in this period.

## 4. Learning from the user

When the user corrects you or explains something, record it with `correct --workspace <dir> --json '<correction>'`.
Use their own words in `quote`. Types: `add_mechanism`, `add_event`, `add_action`, `add_alias`,
`set_priority`, `set_param`, `confirm`, `retire`. Formats and examples: [references/learning.md](references/learning.md).

Include `"run"` (the config of the run that prompted it) and `"slot"` (e.g. `customer_type=new`) so the
regression case can replay it. Re-run the question to show the change, then run `regress` to show every
earlier lesson still holds. Report the coverage figure: it is how the user sees the skill learning.

## 5. Outside events and news

When a gap looks external, or the user mentions weather, holidays, policy, competitors or world events:

1. Search the web (your own search tool) within the dates of the change and the region or product affected.
2. Pick at most three relevant items. For each, record an `add_event` correction with `kind: external`,
   `source: {kind: document, ref: <url>}`, `status: proposed` and the entities it would touch.
3. Re-run. The three checks decide the wording: "passed all three checks" or "timing matches, not proven".
   Never present news as the cause on your own judgement.

Calendars and continuous outside data (weather, exchange rates, market benchmarks) are workspace sources;
see [references/workspace.md](references/workspace.md).

## 6. Keeping the workspace healthy

- `check` lists every problem (unknown columns, missing sources, a formula that does not hold on the data).
- `docs` rebuilds readable, linked Markdown pages from the YAML for people who do not read YAML.
- `coverage` shows, run by run, how many explanations could cite a record.
- Edit YAML directly only for structure (a new comparison, a new data source). Business knowledge goes
  through `correct` so it is sourced and regression-tested.

## Reference files

| File | Read when |
|---|---|
| [references/intake.md](references/intake.md) | the user gives several tables or documents; asking intake questions, recording `propose` |
| [references/workspace.md](references/workspace.md) | writing or reading any workspace file |
| [references/questions.md](references/questions.md) | turning an unusual question into a run |
| [references/operators.md](references/operators.md) | the user asks how a number was computed, or which method is used |
| [references/report.md](references/report.md) | presenting a report, explaining structure vs rate, hypotheses |
| [references/learning.md](references/learning.md) | recording a correction |
| [references/network.md](references/network.md) | the user wants to see the workspace as a page: `network` writes `knowledge.html` |

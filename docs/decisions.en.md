# Decision log

[中文](decisions.zh.md)

This file records the direction agreed before work on analyst-in-a-box began. Each entry states what was decided and why.
When an entry is later overturned, the original text stays; a note below it says "Overturned", what replaced it, and why.

Decision date: 2026-10-30. Decided by: the project maintainer.

## 1. The question this project answers

**"Why did this number move, and who should do what next?"**

Business performance analysis only. Experiment analysis (A/B tests) is solved very differently and is kept out.

Users range from large companies to sole traders: anyone with data who runs a business meets this question.

## 2. Where the value is

In performance analysis, the arithmetic can be handed to a program. Two things are hard:

1. **Business context**: which slice is naturally different, what counts as a normal swing, which dimension to look at first, when to stop.
2. **Self-improvement**: once the user corrects it, it does not make the same mistake again.

The point of this project is to turn those two into a structure other people can pick up and use, and that grows as it is used.

## 3. Form

- The core is a skill folder (Agent Skills format). Drop it into your own AI tool; scripts run locally and data never leaves your machine.
- A demo page lets people see what it can do before they invest effort. It tells one case first, then opens the full graph.
  - **Overturned (2026-11-01): it now leads with how you get there and what you get.** Why: after reading the case-first home page the maintainer said the page should show how a user can generate this in one go, and that the case it led with was thin, fictional and not very interesting. The demo shop is invented and its causes were planted along the skill's own way of breaking numbers down, so leading with it proves little. The home page now leads with the route (drop in a few tables, answer multiple-choice questions, get a metric tree and a first report) and the real output behind each capability; the case is one entry among several.
- The skill and each company's knowledge live apart: the skill is generic; a company's metric tree, world description and corrections live in the user's own workspace. Upgrading the skill never overwrites the user's knowledge.

## 4. Data access

Every company keeps data somewhere different: Excel, databases, online spreadsheets, exports from various systems.
Data access is a replaceable entry point; changing the source does not change the skill. Version 1 supports CSV, Excel, SQLite and DuckDB.

## 5. First use

1. The user loads a dataset.
2. The skill reads the columns and drafts a metric tree and dimensions.
3. Multiple-choice questions confirm what each column means. **Field meaning is never guessed from the column name**; this step cannot be skipped.
4. It immediately runs a first-order attribution and tells the user one thing they did not know.

Business knowledge is **not asked up front**. When an answer gets stuck, it asks one question at that point, records the answer, and never asks again; user corrections are recorded too.
If documents exist, it reads them first and answers what it can; anything extracted is marked "to confirm".

## 6. Method layer: four layers

| Layer | Contents |
|---|---|
| Layer 0 | Metric breakdown: from the north-star metric down, by identities. E.g. gross profit = revenue × margin; revenue = orders × average order value |
| Layer 1 | Dimensions and priority: which cut to try first for each metric. Priority is only "try this first"; the system suggests, the user confirms, and it is **never adjusted automatically** |
| Layer 2 | Order: the order equals how many comparisons are made (see section 7) |
| Layer 3 | Methods, stop conditions and known traps. Stop conditions are a decision table, one rule per row, with a fallback row |

Built-in industry starters **contain formulas only** (e.g. the identities of e-commerce or subscription businesses), never priorities or thresholds, and are all marked "draft, to confirm".
Formulas are mathematics, not guesses; priorities and thresholds are business judgement and can only come from the user.
## 7. Order equals the number of comparisons

| Order | Comparisons | Example |
|---|---|---|
| First | One metric compared once, usually this period vs a base period | Revenue fell 7% year on year last week. What caused it? |
| Second | Two first-order results compared again. The second comparison can be across two time windows or across the two sides of a dimension | Time windows: why was Q3 growth lower than Q2? Two sides: why did offline grow faster than online? |
| Third | A second-order result compared once more | Why is the online–offline growth gap wider this quarter than last? |

Version 1 goes up to second order; third order is left configurable.

A divergence between two terms of the same formula, such as "visitors up, conversion down", is **not second order**: one breakdown by the formula answers it, so it belongs to layer 0.

The mathematics of second order comes from public methods: Kitagawa decomposition (demography, 1955) and shift-share analysis (regional economics).
Both show that comparing two points in time and comparing two groups use exactly the same algorithm.

## 8. The layer that describes the world

It describes **only the part of the world that explains the numbers**, and it only reads data, never writes it. Five kinds:

| Kind | Contents | Example |
|---|---|---|
| Entity | Shops, products, suppliers, channels, stores, upstream factories; also outside parties such as platforms, competitors, weather | "East region store no. 3" |
| Relation | Belongs to, supplies, goes through | A store belongs to a region; a factory supplies a distributor |
| Mechanism | Why a slice's numbers are naturally different | Offline sales pay commission, so offline margin is lower |
| Event | What happened, when, and who did it, with start and end dates | On 12 October a channel partnership changed |
| Action and owner | Who can do what once a problem is found | The channel owner negotiates to restore traffic |

How it joins the metric tree: every dimension value is an entity; relations decide where a breakdown can go; mechanisms and events explain a contribution; actions and owners close the report.

When a slice needs explaining, it cites an entry if one exists. If none does, it writes "the data shows this change; the reason is waiting for your confirmation" and records a gap.

### Its scope

It is complete for one question only, "why did this number move, and who should act next": every entity is a dimension value on the metric tree, every explanation carries a source, a status and a refutation condition, and it is cheap to build. It does not do general concept reasoning, does not write back to business systems, and does not handle permissions or large-scale data governance. That is how it is described in public too.

Structurally it keeps to these rules: one canonical name per thing, other names kept as aliases; "business reasons" kept apart from "this run's hypotheses", each hypothesis stating what data would refute it; every entry carries a source and a status.

### Where it comes from: not only by asking people

| Source | What it gives | Reliability |
|---|---|---|
| The data itself | Hierarchies and relations (a store only ever appears under one region → it belongs to that region); a sudden jump on some day → something may have happened | The structure is fact, but field meaning needs a person; a jump cannot say what happened |
| Business system records | Price changes, campaign calendars, listings, stock-outs | High; just connect them |
| The user's documents | Weekly reports, post-mortems, org charts, supplier lists | Medium; extracted entries are marked "to confirm" |
| General industry knowledge | Supply chains, sales-season rhythms | Low; drafts only |
| Asking a person | Mechanisms, and the "why" behind events | Highest; asked only when stuck |

## 8b. External signals

Moves often come from outside the company: travel watches holidays and world events, a florist watches the weather, a factory watches demand, industry output and exchange rates.
None of this is in the user's data, the data is not the user's, and it can only show that timing matches, not that one caused the other. Three kinds:

| Kind | Examples | How it is used |
|---|---|---|
| Calendar | Autumn break, Lunar New Year, sale days | Mainly to **align the base period**: when this year's and last year's holidays fall in different weeks, year-on-year figures rise or fall artificially; remove that first, then attribute |
| Continuous external data | Weather, exchange rates, industry output, raw-material prices, industry benchmarks | Treated as external metrics; a mechanism states how it affects internal numbers and with what lag |
| News events | Wars, policy, competitor sales | **Hypotheses only**, never conclusions |

Two rules:

1. **Compare with the market first, then look for causes.** Shift-share analysis already splits a change into "moved with the market" and "your own". If the whole industry fell 10% and you fell 10%, the main cause is outside; if the industry held and you fell, break down internally.
2. **An external factor enters the conclusion only after three checks**: timing matches (the event precedes the change); the affected slice matches (a war should hit orders to that place, not everything); the size is plausible. Otherwise write "timing matches, not proven" and state what data would refute it.

Version 1: calendars and continuous data are replaceable sources, like data access, starting with file import.
News is looked up by the user's AI tool with its own web search, within the days of the change, and comes back with links as hypotheses. Nothing to configure; the demo store runs offline.

## 9. Self-improvement

Each correction is written to a file and turned into a regression case; the next similar question reads it.
Every analysis leaves a run record: which definitions version was used, which rules fired, which hypotheses were produced.
A coverage figure is tracked: of the places in a conclusion that need a business explanation, how many can cite an entry. Its rise with use is the evidence that it "learns".

## 10. Arithmetic belongs to programs

Every decomposition is computed by a script; the model never does mental arithmetic. Every algorithm is tested so that its terms sum to the total change.
Thresholds are never hard-coded; they come from the user's or the example's configuration.

## 11. How to prove it is generic

A person who was not involved follows only the getting-started flow, in two stages:

1. **First time**: after loading data and confirming the metric tree, they get an attribution that is arithmetically correct and tells them one thing they did not know.
2. **After a while, and some corrections from them**: the same kind of mistake does not recur, and they judge it close to their own analysts.

Public datasets have no answer key, so they only prove "it loads and it runs". The demo therefore carries two datasets:

- a fictional shop whose data is generated with known causes planted, the demo ending with "what it found" beside "what was planted";
- one public real dataset whose licence has been checked.

## 12. Writing rules

- Every document exists in Chinese and English, section for section.
- No jargon such as "ontology" in user-facing text; plain words instead.
- Every number has a source; facts, estimates and guesses are written apart.
- Ideas are borrowed from an earlier internal project; code and text are written from scratch, and no business content is carried over.

## 13. Not in version 1

- Multi-person collaboration (who approves, who gets mentioned in a group chat): needs a team and a collaboration tool; version 1 is for one person.
- Automatic adjustment of dimension priority: priority is guidance, not a rule.
- Model fine-tuning: all knowledge lives in files.
- Publishing to the public internet or a public repository: needs the maintainer's approval.

## 13b. Waiting for the maintainer

- **The licence.** Not chosen yet; the README says "to be decided".

  Decided 2026-10-30 by the maintainer: Apache-2.0, chosen over MIT for its explicit patent grant. The
  public dataset keeps its own CC BY 4.0 licence.
- **When to publish to the public internet or a public repository.** Before that, confirm that the design
  ideas borrowed from the earlier internal project may be shared; that is a question of company policy, not
  of technology.

## 14. Next things to research

- **How to bring news in properly** (raised by the maintainer, 2026-10-30): version 1 relies on the web search built into the user's AI tool. Next, research dedicated news sources: which exist, their licence terms, how to filter by time window and region, and how to judge that a news item relates to a particular change.

## 15. Version 0.2 (2026-10-31)

Version 0.1 answered the planted demo questions correctly but did not behave like a careful analyst on dirty
data. An audit showed it attributing a fall to an event when two days of data were simply missing, and drilling
into pure noise. These are the decisions taken to fix that. Earlier sections stay as written. Where 0.2
replaces a 0.1 rule, the rule is named here.

### Check the data before explaining it

A data-quality step runs before any breakdown: whole days missing (closing days excluded), repeated order ids,
days with far more or fewer rows than usual, a day's total several times the usual, the two periods' row
counts, a single row carrying the change, and a value that vanished while another appeared. The thresholds are
params in `rules.yaml`, each with its source.

The old check "identities hold on the data" was a tautology: a ratio is defined as one factor divided by the
other, so the product always matches. It is renamed `identities_computable` and says it only proves that every
factor can be computed. A real reconciliation (`segments_add_up_to_total`) replaces it in the list of checks.

### Tell noise from a cause

A cut names a single point only when the top group carries clearly more of the movement than its share of the
base, and when its own change is far from its own past swings. The two-group bias is gone: with 0.1's
"top share ≥ 50%" rule, the top group of a two-value dimension always qualified. When the whole number is
within its usual range, the run reports and does not drill, unless one group stands far out (see the decisions
below).

A three-day event inside a week is diluted by four ordinary days. Each group's evidence is therefore the
stronger of two calibrated tests: the week as a whole, and the strongest run of 2 to 4 days, each judged
against the same statistic on past periods (Naus 1965; Kulldorff 1997). This was found on unseen seeds, not by
lowering a threshold.

### Choose the dimension; report one cause once

Every layer scores the candidate dimensions by explanatory power × surprise (Adtributor, Bhagwan et al. 2014).
A confirmed priority still decides the first cut. A drill path counts as one cause, and the run checks it from
the other side.

### A record must be able to explain the change

Every cited mechanism or event says whether it can explain the change: did it differ between the two periods,
and does it act on mix or on each group's level? Something true in both periods cannot explain a change.
0.1's demo correction ("new customers buy a smaller first order") was such a record, and coverage still rose
from 50% to 100%; that rise was false. The demo correction is now the October offer that changed the mix.

### The market comparison is an estimate

"Following the market" now means the market's growth plus this business's usual gap to it (median over the same
past periods), in the spirit of shift-share analysis taking the lasting difference out first
(Esteban-Marquillas 1972). Both numbers are kept; the report uses the adjusted one and calls it an estimate.

### Periods that line up

Calendar months compare with calendar months; a single day compares with the same weekday a week earlier.
Unequal lengths compare daily averages, automatically when the rule chose them and on request otherwise.
History follows the same rule as the question. A past period whose two sides held different holidays is left
out of the history and named.

### Decided by the maintainer (2026-10-31)

- **Whole number within its usual range, one group stands far out: drill into it.**

  Waiting for the maintainer (raised at the 0.2 checkpoint): the average-order-value question needs this
  default, but in pure noise it fires on groups with a robust z of 4 to 7 about once in 30 weeks.

  Decided: keep it. Params `drill_quiet_total_when_group_stands_out` (true) and `group_stands_out_z` (3.5),
  source "maintainer decided 2026-10-31".
- **What happens when a data check fails.**

  Waiting for the maintainer: the checkpoint version stopped the report on any failed check.

  Decided: two levels, a param per check (`quality_check_levels`). Checks that would make the numbers wrong
  stop the report: repeated order ids, whole days missing outside closing days, a period with almost no rows
  to compare. The others are named at the top of the report and the conclusions are given: a sudden jump in a
  day's row count, a value that looks renamed, one order carrying a large share. The skill placed
  `daily_value_steady` (a day's total several times the usual, as after a unit change) with "stop", because it
  changes every amount after it. That placement is the skill's, not the maintainer's, and one param changes it.
- **Saturdays in the public dataset.**

  Waiting for the maintainer: all 53 Saturdays in the data have no invoice, and UCI does not say which days the
  retailer traded.

  Decided: treat Saturdays as closed, and say this is an assumption drawn from the data. The workspace records
  it with source "inferred from data" and status "to confirm", and the report says so.

### The run-of-days test pays for being a second test (2026-10-31)

**Decided.** The weekly test stays the main evidence, unchanged. The "strongest run of 2 to 4 days" test replaces
a group's z only when it is still stronger after a two-test Bonferroni correction: its p-value is doubled, turned
back into a z, and then compared with the weekly one.

**Why.** Running two tests per group and keeping the stronger gives noise two chances, so false alarms rise. The
correction takes the extra chance back. Sources: C. E. Bonferroni (1936); O. J. Dunn (1961), "Multiple
comparisons among means", *JASA* 56(293).

**Measured.** Ten pure-noise shops × 30 weeks = 300 weeks. Revenue drilled into 17 weeks without the
correction and 15 with it. `tests/test_search.py` now runs these ten seeds × 30 weeks and allows at most 15.
The demo questions on unseen seeds: 30/30 found.

**Why the weekly test is not corrected too.** Correcting both gave 10/300, but lost a real cause: one channel
in one region losing 80% of its orders, whose weekly z went from −2.19 to −1.90, below the 2.0 bar. The weekly
test is the one that is done anyway; only the extra test should pay for being extra.

## 16. Intake: from several tables to a workspace (2026-10-31)

The maintainer: "What makes this skill strong is not only how it presents; it should do the gathering too."
Before this, `init` read one table and the demo shop's world was written by hand, so nothing showed the
workspace being formed.

### Inferred from shape only; every inference asked

`init` takes a folder or several files. The main table, the lookup tables, the links between tables, event
records, calendars and daily series are inferred from the shape of the data, never from column names
(section 5). Every inference is a multiple-choice question with its suggested answer and the evidence: row
counts, which column is never after which, a link's coverage. Nothing enters the workspace before `confirm`,
and a link not answered "yes" is not made.

### Links by coverage

A column whose values are found in another column is a candidate link. Coverage is the share of rows that
match. Below 50% the pair is not asked about; from 50% to 95% the suggested answer is "no"; from 95% "yes".
Links are many-to-one lookups only (one row per key on the right), so a main-table row stays one row. The
thresholds are constants in `intake.py`: rules of intake, not business thresholds.

### Each row of an event table is an event to confirm

Each row of a campaign calendar or a price log becomes a world event: source "system record", status "to
confirm". The user confirms what the table is, but nobody has vouched for each row yet.

### Documents are read by the AI tool; the script checks the sentence

The script does not read prose: pulling causes out of sentences by rule is guessing too. So the user's AI
tool reads the document and proposes mechanisms or events. `propose` checks one thing: the quoted sentence is
in the document, word for word. Whitespace and Markdown emphasis are ignored; every other character must match,
and a quote under 8 characters is refused. A quote that does not match is refused. Accepted entries keep the
document path and the sentence, with status "to confirm".

### A record to confirm is not counted as explained (changes a 0.2 rule)

In 0.2 as first written, an internal record that fitted the change counted as explained whatever its status.
Now an internal record must be confirmed. One still to confirm makes the slot a hypothesis, and the report says
"possible cause, from a document (or a system record), to confirm", with the sentence. Outside events are
unchanged: they are still judged by the three checks against outside data. Every internal record the demo shop
cites is confirmed, so the four demo answers did not change.

### The demo: the same shop, both ways

`demo/intake/` splits the demo shop's data into nine tables plus one weekly report, runs the whole intake, and
writes a formation report that compares the result with the hand-written workspace, part by part.
`demo/store/` is not changed. What cannot be formed is listed as such: readable names for codes, mechanisms
such as the marketplace commission, actions and owners, comparisons, a confirmed cut order, price-volume-mix.

## 17. A readable name for every column (added 2026-10-31)

Intake and reports used to show column names as they are (`order_id`, `channel`), which a business reader cannot use.
Now:

- after reading the columns, the getting-started flow gives each column a readable name in both languages, from the
  words in the column name (`order_id` → 订单编号 / Order ID), and writes it into `draft.json`, `project.yaml` and the
  labels and dimension names of `model.yaml`;
- **these are names, not meanings**: what a column means is still asked as a multiple-choice question and never taken
  from its name;
- the person answering can override any name with `name:<column>`; words it does not know are kept as they are;
- the raw column name stays in the data and in a hover tooltip, and is not shown as text on a page.

## 18. Outside design checks; the font becomes IBM Plex (2026-11-02)

Why: our own browser check passed all 177 items, but it checks whether pages are correct (contrast, overflow,
internal words), not whether they look machine-made. The maintainer pointed at four design skills; two of them ship
checkers with fixed rules and no model. On our 22 pages impeccable found 128 findings, hallmark 271 floor
findings and 175 habitual defaults.

What was decided:

- After a build, run `node tools/design-check/run.mjs`: impeccable pinned at 4.8.0; hallmark's checker copied
  unchanged into the repository with its MIT licence and source commit (`4f6a46c`).
- Every impeccable finding and hallmark's floor and reflex tiers block; hallmark's finish tier is only reported.
- A finding may stay only if `accepted.json` names it with a reason others can check. There is one: hallmark's
  rule 20 asks for the stamp its own workflow writes; this site was not made with that workflow, so the stamp
  would be a false claim.
- Font: Geist is on impeccable's overused list; replaced with IBM Plex Sans / Mono (OFL, self-hosted Latin
  subsets, about 70 KB). Chinese still uses system fonts.
- Removed the small labels above headings, the arrows after link text and strings joined with middle dots; every
  colour comes from a named variable in `:root`; pure white became a slight tint of the report navy; spacing sits
  on a 4px grid.

Not done: the 46 finish-tier notes from hallmark (pages over 450 words, straight quotes in English, long labels)
were left alone. They do not block, but they say the pages still carry a lot of text.

## 19. Public names, confidence tiers, the knowledge-network page, the person's role, the promo film (2026-11-02)

This section puts together what was settled on the day; later pages and documents follow it.

**1. Public names.** The layer that describes the business is called the "business knowledge graph". It has two parts: the "metric tree" (the north star broken down by formula, each metric listing the dimensions it can be cut by and in what order) and the "business world description" (entities, relations, mechanisms, events, and actions with owners). The word ontology is not used in public, and "world description" alone is retired. The order in which dimensions are cut is itself a business fact, so it carries a source and a status like the metric tree does.

**2. The value comes from the whole design, not from one page.** Before making any piece (site, film, copy), check it against these seven things: north-star breakdown; horizontal (by formula factors) plus vertical (by dimension) breakdown; contributions computed by scripts, with the parts adding up to the total change; the two parts of the business knowledge graph; their visualisation; intake from several raw tables to a workspace; a correction remembered after one sentence.

**3. Facts and AI inference are kept apart by confidence.** What is collected falls into two layers: facts (what the user said, records from business systems, what the data itself shows) and AI inference (read from documents, general industry knowledge, guesses). AI inference is not treated as knowledge until a person confirms it. Where things stand: every record already carries a source kind and a status and is refused without them; a cause read from a document must quote its sentence word for word and is marked "to confirm"; an outside event must pass three checks. What is not done is the display: the graph only has one marker, "to confirm", so it does not show where an entry came from. It should tell apart, at a glance, what a person said, what the data showed, and what the AI read in a document.

**4. The skill generates the knowledge-network page.** Today the skill only writes linked Markdown pages; it has no page of its own, and the graph page exists only on the showcase site, with positions computed at build time. It will change: the skill generates, for the user's workspace, a moving knowledge-network page (nodes spread out on opening, can be dragged, settle after a few seconds; clicking a node shows its source, its status and what data would overturn it), with two views, the metric tree and the business world description, and nodes that differ by confidence. This replaces the earlier approach of computing the showcase site's layout at build time without live force layout (that choice was recorded only in internal working notes); what was rejected before was the old site's whole look, not force layout itself. The physics constants follow the open-source d3-force defaults and our own measurements, and the look is our own light style. The showcase site shows the demo shop's copy.

**5. The person's role.** Publicly the three parties are "you", "the scripts" and "the AI", with "you" explained once at the start. You only judge: whether its understanding of your business (the tables, columns and joins it recognised, the causes it read) is right, correcting a few spots; the analysis itself runs in one go. The scripts recognise tables, columns and joins. Do not say "fully automatic" or "no human needed", and do not quote counts that change with every dataset, such as the number of questions asked.

**6. The promo film.** It talks about value and strengths and says what the product solves; it does not narrate the steps. Limits belong in documents and reports, not in the film. Only measured numbers are used; anything not measured (speed against a human analyst, "verified in real business", an unqualified "zero false alarms") is not said. One thing per shot, little and large text; show who is acting before the result; each mechanism gets one plain rule and one picture. It carries three messages: an analyst-grade explanation (contribution algorithms plus horizontal and vertical breakdown, never a result taken as a cause), orders, products, traffic and campaign tables turned into a business knowledge graph by itself, and learning more about your business the more it is used, with the measured results at the end. Length 70 to 80 seconds.

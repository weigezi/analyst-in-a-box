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

### How it differs from other systems

| | What it answers | How it is built |
|---|---|---|
| A concept-logic system | What a concept is, and the logic between concepts | Written by experts in specialised tools |
| A data-integration platform | What a company has and what you can do to it (actions write back to systems) | Built on top of an integrated data warehouse |
| This project | Why this number moved, and who should do what next | Drafted by the machine from data and documents, confirmed and filled in by a person |

**This project is not more complete than either.** It is far weaker in expressiveness, reasoning, write-back, permissions and data scale. It is complete for one question only, "why did this number move": every entity is a dimension value on the metric tree, every explanation carries a source, a status and a refutation condition, and it is cheap to build. That is how it is described in public too.

It borrows only their structure: one canonical name per thing, other names kept as aliases; "business reasons" kept apart from "this run's hypotheses", each hypothesis stating what data would refute it; every entry carries a source and a status.

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
- **When to publish to the public internet or a public repository.** Before that, confirm that the design
  ideas borrowed from the earlier internal project may be shared; that is a question of company policy, not
  of technology.

## 14. Next things to research

- **How to bring news in properly** (raised by the maintainer, 2026-10-30): version 1 relies on the web search built into the user's AI tool. Next, research dedicated news sources: which exist, their licence terms, how to filter by time window and region, and how to judge that a news item relates to a particular change.

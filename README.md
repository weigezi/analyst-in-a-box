# analyst-in-a-box

[中文](README.zh.md)

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![ci](https://github.com/weigezi/analyst-in-a-box/actions/workflows/ci.yml/badge.svg)](https://github.com/weigezi/analyst-in-a-box/actions/workflows/ci.yml)

**Why did this number move, and who should act next?**

A skill for AI tools that explains a moving business number the way a senior analyst would. The breakdown is
computed by scripts and adds up to the total, and a cause is never a result in disguise: it is a dated, sourced
record that has to pass checks.

<p align="center">
  <a href="docs/assets/demo.mp4">
    <img src="docs/assets/demo.gif" width="800" alt="Revenue fell 43,159. Split by formula and split by channel, both add up to exactly 43,159.">
  </a>
</p>
<p align="center"><sub>Demo shop, generated data: last week's revenue against the same week a year ago, split two ways, both adding up to the total. On-screen text is in Chinese. <a href="docs/assets/demo.mp4">Watch the full 76-second film</a>.</sub></p>

```bash
npx skills add weigezi/analyst-in-a-box
```

## Who does what

Three parties are named throughout this page.

- **You** judge whether its understanding of your business is right (the tables, columns and joins it recognised,
  the causes it read from your documents) and correct a few spots.
- **The scripts** recognise tables, columns and joins, compute every number and run every check.
- **The AI** understands the question, writes the explanation in plain words and proposes candidate causes from
  your documents.

You check that it understood. The analysis then runs in one go.

## An explanation that adds up

In the demo shop, last week's revenue was down 9.6% year on year, 4.5 times the usual swing across 22 comparable
weeks. Only then does it break the change down, in two ways:

- **By formula.** Conversion rate −35,366, order value −17,084, visits +9,291.
- **By dimension.** Marketplace −79,168, web +34,816, app +1,193.

Both add up to the total change, −43,159. The scripts use methods published elsewhere: BEA contributions to
percent change for sums, LMDI-I for products (Shapley when a factor is zero or negative), Kitagawa for ratios. There
are 12 methods in all, each with its citation in [`operators.md`](skills/analyst-in-a-box/references/operators.md).
A report that fails any of its 12 pre-delivery checks is not delivered.

**Where the money went and why are two separate layers.** The breakdown says the marketplace lost 79,168. It does
not say why. A cause has to be a record with a date and a source, and the scripts check that it can explain this
change: it must differ between the two periods, it must start on the same day the change did, and without it the
other channels must look normal (they grew 10.8% against a usual 7.7%). In the demo the record reads: from 12 October
the marketplace changed its fee terms and our listing lost its placement (source: partner contract log, confirmed).
In that hand-written workspace the record also names an owner, the channel lead, and an action.

If the data itself is in doubt, it says so first. Two missing days, or an order file loaded twice, stop the report
with the reason instead of producing a cause.

## Tangled tables become a business knowledge graph

Give it several raw exports and a document. The scripts work out which table is the main one, which are lookups, how
the tables join (with the coverage of each join) and which hold events, and every guess comes back to you as a
multiple-choice question. What they build is the **business knowledge graph**, in two parts:

- **Metric tree.** The north-star metric broken down by formula. Each metric lists the dimensions it can be cut by,
  and in what order.
- **Business world description.** Entities, relations, mechanisms, dated events, and actions with owners. Each
  record carries its source, its status, and what data would overturn it.

In the demo, nine exported tables (226,814 orders) and a weekly report became a workspace that answers questions and
writes its first report in about 3 seconds of script time, once the shop owner's answers were in. A cause read from
the weekly report is kept with the exact sentence it came from and marked "to confirm" until you confirm it. Owners
and actions are added by you.

## It learns your business

Tell it once: "From 1 October, new customers get a greeting card with a fruit basket." It records your sentence as a
dated record with your words as the source, uses it the next time that question comes up, and writes a regression
check. In the demo, the share of the order-value change it could explain went from 0 to 100%. Delete the record and
the check fails (1/1 becomes 0/1). The check guards the corrected question only.

What it keeps is sorted by confidence. **Facts** are what you said, records from business systems, and what the data
itself shows. **AI inference** is what was read from documents, general industry knowledge, and guesses. AI inference
is not treated as knowledge until a person confirms it. Every record must carry a source and a status or it is
refused, and a cause read from a document must quote its sentence word for word.

## What was measured

All of this was measured on generated data or one public dataset, not on a real business.

- **30 of 30** planted causes found, on 6 generated shops (5 questions each) whose seeds it was never tuned on.
- **15 trap cases** built to provoke false alarms and misses: 0 false alarms among the 12 with nothing planted,
  0 misses among the 3 with a cause planted.
- In 300 weeks of pure noise it still drilled into a single point in 15 weeks for revenue and 7 for order value
  (5.0% and 2.3%).
- Every breakdown sums to the total change: 178 tests pass, and the same check runs before each report.
- The scripts take a median of 0.31 seconds per question on an Apple Silicon Mac. This leaves out the time the
  AI tool spends reading and writing.

## Try it

Install the skill with the command at the top, then ask your AI tool something like:

> Here is our order table (path). Why did revenue fall last week?

It asks what each column is instead of guessing from names, then gives a first report in the same conversation.

- Several tables: give it a folder of exports, and a weekly report if you have one.
- From a terminal: `python3 skills/analyst-in-a-box/scripts/aib_cli.py init your_data.csv --workspace ./aib-workspace`
- See the runs behind this page: the demo site is built from real runs with `uv run python site/build.py`. A hosted
  demo site will be linked here once it is published.
- Run the tests: `uv run --frozen pytest`

## Documentation

- [Trial guide](docs/trial.en.md): trying it on your own business, and what to send back.
- [Decisions](docs/decisions.en.md): why it is built this way, including the public names and rules.
- [Several tables to a workspace](demo/intake/README.md) and [the public dataset](demo/public/README.md).
- [Contributing](CONTRIBUTING.md) and [security](SECURITY.md).

The skill itself is in `skills/analyst-in-a-box/`. The fictional shop and its answer key are in `demo/store/`.

## Status

First public release. It has been tested on a generated demo shop, six more generated shops, the trap cases, and
one public dataset (UCI Online Retail, CC BY 4.0). That dataset shows real data loads and yields a checked report; it
has no answer key, so it does not show the answers are right. Nobody outside the project has tried it on their own
business yet, and the [trial guide](docs/trial.en.md) is how that changes. Not done yet: third-order questions, and
news sources other than your own web search.

Found a bug, or tried it on your data? Open an issue; there are templates for both. Licence: [Apache-2.0](LICENSE).
The data in `demo/public` keeps its own licence.

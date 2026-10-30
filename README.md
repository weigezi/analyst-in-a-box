# analyst-in-a-box

[中文](README.zh.md)

**Why did this number move, and who should act next?**

A skill for AI tools that explains a moving business number the way a senior analyst would. It breaks the
change down with published methods, decides when to stop, explains each point with the part of the world that
causes it, and names who can act. When you correct it, it writes your words down and turns them into a
regression case, so it does not make the same mistake twice.

## What it does

- **Breaks a change down exactly.** Formulas (revenue = orders × average order value), cuts by dimension, ratios
  split into structure and rate, and second-order questions ("why is growth slower than last month", "why did
  offline grow faster than online"). Every breakdown is computed by a script and checked to sum to the total.
- **Qualifies before it attributes.** Is this period unusual against its own history? Did the market move the
  same way? Do the two periods hold the same holidays?
- **Explains with the world, not just the data.** Entities, relations, mechanisms, events, and actions with
  owners, each with a source and a status. Outside events (weather, news) stay hypotheses until they pass three
  checks: timing, affected slice, size.
- **Learns from one person.** Business knowledge is asked when an answer needs it, not in an upfront survey.
  Each correction becomes a regression case; coverage of explained points rises with use.
- **Starts from a table.** Point it at a CSV, Excel, SQLite or DuckDB table; it asks what each column is
  (it never guesses from names) and gives a first attribution in the same conversation.

## Try it

| You want to | Do |
|---|---|
| see it work | build the demo site: `uv run python site/build.py`, then open `site/dist/index.html` |
| use it | copy `skills/analyst-in-a-box/` into your AI tool's skills folder and ask "why did revenue fall last week?" |
| use it from a terminal | `python3 skills/analyst-in-a-box/scripts/aib_cli.py init your_data.csv --workspace ./aib-workspace` |
| try it on your own business | follow the [trial guide](docs/trial.en.md) |

## The demo

The demo shop, Bloom & Basket, is fictional. Its data is generated with known causes planted in it: a marketplace
that changed its terms, three days of heavy rain in one region, a promotion that shifted the mix, a home-page
change that hit one category on one channel. The skill never reads the answer key; `tests/test_demo_store.py`
checks that it finds every cause. A real public dataset (UCI Online Retail, CC BY 4.0) shows that real
data loads and runs; see [demo/public](demo/public/README.md).

## How it differs from other systems

It is not more complete than either. One kind of system describes concepts and their logic; another describes what a company
has and what can be done to it, and writes back to systems. This project only reads data, and is complete for
one question: why did this number move. Details: [docs/decisions.en.md](docs/decisions.en.md).

## Layout

| Path | Contents |
|---|---|
| `skills/analyst-in-a-box/` | the skill: `SKILL.md`, `references/`, `scripts/aib/`, formula starters |
| `demo/store/` | the fictional shop: generator, answer key, workspace |
| `demo/public/` | the public dataset: preparation script, attribution |
| `site/` | the demo site builder and its assets |
| `tests/` | operators, decision tables, demo causes, learning, first use |
| `tools/` | browser check, clean-room check, bilingual check |
| `docs/` | decisions, trial guide |

## Checks

```bash
uv run pytest                                   # every method sums exactly; every planted cause is found
uv run python site/build.py                     # build the demo site from real runs
cd tools/browser-check && npm install && node check.mjs   # no errors, motion timings (site/MOTION.md)
uv run python tools/bilingual_check.py          # every document has both languages, section for section
```

## Status

Version 0.1. Not yet tried by someone outside the project. Licence: [Apache-2.0](LICENSE). The data in
`demo/public` keeps its own licence (CC BY 4.0, see [demo/public](demo/public/README.md)).

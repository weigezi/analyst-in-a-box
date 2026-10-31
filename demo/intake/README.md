# Intake demo: the shop's raw tables become a workspace

[中文](README.zh.md)

The demo shop's hand-written workspace (`../store/workspace/`) shows what the skill can do once someone has
described the shop. This folder shows how much of that description the skill forms by itself: from the
tables a shop's systems export, plus one weekly report.

## What is here

| Path | What it is |
|---|---|
| `build_tables.py` | splits the demo shop's data into nine system-shaped tables in `tables/` (orders carry only a product code and a city; the category and the region are in lookup tables) |
| `tables/` | orders, products, cities, traffic, the campaign calendar, the price-change log, the holiday calendar, weather, the market index |
| `docs/weekly_report.zh.md` | a fictional weekly report, written the way a shop writes one (`weekly_report.md` is a translation) |
| `answers.yaml` | how the owner answers the intake questions |
| `proposals.yaml` | what an AI tool proposes after reading the report, each with its sentence |
| `run_intake.py` | runs the whole intake and writes `workspace/`, `runs/`, `formation.json` and the formation report |
| `formation.md` | the formation report: what was formed, from where, and where it differs from the hand-written workspace |

```bash
uv run python demo/intake/run_intake.py
```

`demo/store/` is only read.

## What it shows

- The skill finds the main table, the two lookup tables and seven links between tables, all at 100% coverage. It
  also finds the two event tables, the holiday calendar and the three daily series, and turns each into a
  question. The owner changes the suggestion twice, both for the market index: it is a market, not just a
  series, and it is compared with revenue.
- The campaign calendar and the price log become three events, "from a system record, to confirm". The weekly
  report gives two events and one mechanism, each kept with its sentence, "from a document, to confirm".
- The formed workspace answers the revenue question: the main cause is the marketplace, and the possible cause
  is the fee change, shown as "from a document, to confirm" and not counted as explained. The east question is
  explained, because the rainstorm passes the three checks against the weather data (outside events are judged
  by that test, not by who confirmed them).
- What it cannot form is listed as such: readable names for codes, mechanisms such as the marketplace
  commission, actions and owners, the app-vs-web comparison, a confirmed cut order, and price-volume-mix.

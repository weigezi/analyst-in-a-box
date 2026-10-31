# Presenting a report

[中文](report.zh.md)

## 1. Order

The report is already in the order a reader needs; keep it:

1. **Conclusion**: the change, the main source, and one thing the user may not know.
2. **Is it unusual**: against its own history, against the market, holiday alignment.
3. **Breakdown**: formula first, then each cut, with the decision that ended it.
4. **Why**: for every single point, what explains it, with source and status.
5. **Who should act**: owners and actions recorded for those points.
6. **Waiting for you**: gaps and entries to confirm. Turn these into questions.

In conversation, lead with the conclusion in two or three sentences, then offer the rest.

## 2. Wording that is easy to get wrong

- **Shares.** The report never shows a share above 100% or one whose sign is opposite to the change. Tables
  show each group's share of all movement (0 to 100%), and the sign is in the amount. The conclusion speaks in
  amounts: the main group's change, its own growth, and "without it, the rest changed X; it usually changes Y".
  Do not compute a share yourself.
- **Estimates.** "Following the market" uses this business's usual gap to its market; the report says it is an
  estimate and also gives the plain number. Repeat both, and say which is which.
- **When it started.** If the report names a start date, compare it with the events it lists. Starting the
  same day as an event is strong evidence; starting before it argues against it.
- **Structure-led vs rate-led** (ratios). Structure-led: the mix of groups moved (more cheap orders);
  rate-led: groups' own levels moved (every group got cheaper). Say which, and in which dimension it was measured.
- **Mix vs performance** (two sides). Mix: the sides sell different things. Performance: the same thing grew
  differently on each side.
- **Spread, no single point.** The change is distributed; the analysis stopped on purpose. Do not pick a
  "biggest" segment to sound decisive.
- **Hypotheses.** An outside event that passed all three checks is "a hypothesis supported by timing, slice
  and size", never "the cause". One that did not is "timing matches, not proven". Read out the refutation condition.
- **Within the usual range.** Say so plainly; the breakdown is still useful, but it is not an anomaly.

## 3. Numbers

Use the numbers in the report as they are. Do not round differently, convert units, or add your own
percentages. If the user wants a number the report does not have, run again with a different config.

## 4. Gaps

A gap is the most valuable line in the report: it is where the skill can learn. Ask about it in plain words,
one gap at a time, and record the answer with `correct`.

## 5. Data for drawing

`record.json` holds everything the charts are drawn from, so a page can draw them again:

| Field | What it holds |
|---|---|
| `charts.waterfall` | `base`, `steps` (`label_key`, `dimension`, `value`; one `others` step), `current`, `unit`, `dimension`, `filters`, `base_window`, `current_window`; base + steps = current |
| `charts.daily` | `current` and `base`, each `[{day, value}]` aligned by position, `unit`, `excluded_days` |
| `charts.range` | `current_change`, `usual_range` (middle half of past changes), `unusual_below` / `unusual_above` (threshold lines, not the usual range), `history` (`window`, `base`, `change` per past period) |
| `narrative` | `main`, `secondary`, `offsets`, `ruled_out`, `rest` (rest of the scope against its usual change), `onset` (start date, `daily` gaps, matched `events`), `recent_weeks`, `market` (estimate) |
| `quality` | `status`, `suspect`, `failed` (block level), `warned`, `checks` (each with `status` and `level`) |
| `tree`, `pvm`, `growth_accounting` | the other breakdowns, when they ran |

Colours: decrease vermillion `#D55E00`, increase blue `#0072B2`, totals grey (Okabe & Ito 2008); every number
in a chart carries its sign, with a true minus sign.

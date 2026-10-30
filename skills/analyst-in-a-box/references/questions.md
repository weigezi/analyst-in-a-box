# Turning a question into a run

[中文](questions.zh.md)

## 1. Time words

| The user says | Window |
|---|---|
| last week | Monday to Sunday of the last complete week in the data |
| last month, last quarter | the calendar month or quarter |
| recently, these days | ambiguous: ask as a choice (last 7 days / last 4 weeks / this month so far) |
| a date range | use it as given |

## 2. What to compare with

| The user says | `--base` |
|---|---|
| year on year, 同比, nothing specific | `yoy`: the same weekdays 364 days earlier, so the weekday mix matches |
| vs last week, 环比, period on period | `pop`: the window right before, same length |
| an explicit base range | `--base START END` |

The two windows must have the same number of days; the run blocks otherwise, because an 8-day window
against a 7-day one shows about +14% from nothing. Holidays that fall differently in the two windows are
flagged by the calendar check; mention that note when it appears.

## 3. Which order

| Signal in the question | Order | Run |
|---|---|---|
| one metric changed: "why did X fall / rise" | first | default |
| the change itself changed: "growth slowed", "worse than last month", "turned negative", "keeps falling" | second, across time | `--previous` |
| two sides differ: "why did A grow faster than B", new vs returning, online vs offline | second, across sides | `--compare <id>` |
| two terms of one formula diverge: "visitors up, conversion down" | first | default; read the formula breakdown |

If the question has two parts ("why did it fall, and why is it worse than last month"), run both and present
the first-order answer first.

## 4. When something is missing

- **Metric not in the workspace**: list the metrics that exist as choices; do not substitute a similar one.
- **The user names a value differently** ("the platform" for `marketplace`): ask to confirm, then record an
  `add_alias` correction so the next question resolves directly.
- **A comparison not in `model.yaml`**: confirm the dimension and the two sides with the user, add it under
  `comparisons`, run `check`, then run.
- **The data does not reach back for `yoy`**: say so and offer `pop`.

## 5. Narrowing the scope

`--filter dim=value` (repeatable) restricts the whole run. `--dimensions a,b` overrides the cut order for
this run only; to change it for good, record a `set_priority` correction instead.

# Workspace format

[中文](workspace.zh.md)

A workspace is a folder holding one company's knowledge. The skill reads these files; it writes them only
through `confirm` (first use) and `correct` (learning). A complete example lives in the demo shop.

Contents: 1 Files · 2 project.yaml · 3 model.yaml · 4 rules.yaml · 5 world.yaml · 6 Sources and statuses

## 1. Files

| File | Holds | Written by |
|---|---|---|
| `project.yaml` | name, language, data sources, outside sources | `confirm`, or by hand |
| `model.yaml` | method layer: measures, metrics, formulas, dimensions, cut order, comparisons | `confirm`, `correct`, structure by hand |
| `rules.yaml` | named thresholds with sources, decision tables | `confirm`, `correct` |
| `world.yaml` | entities, relations, mechanisms, events, actions and owners | `confirm`, `correct` |
| `corrections.jsonl` | every correction, with the user's words | `correct` |
| `regressions/*.yaml` | one replayable case per correction | `correct` |
| `runs/<id>/` | `record.json`, `report.zh.md`, `report.en.md`, `charts/` | `run` |
| `docs/` | readable linked pages generated from the YAML | `docs` |

## 2. project.yaml

```yaml
name: My shop
language: zh                     # default report language
sources:                         # one entry per table; types: csv, excel, sqlite, duckdb
  orders: {type: csv, path: data/orders.csv, date_columns: [order_date]}
  traffic: {type: sqlite, path: shop.db, table: daily_visits, date_columns: [date]}
external:                        # outside data, same loaders; "role" says how it is used
  calendar: {type: csv, path: external/calendar.csv, role: calendar}         # name, start, end[, label_zh, label_en]
  market: {type: csv, path: external/market.csv, role: market, value: market_sales, date: date,
           date_columns: [date], compares_with: revenue}                    # "did the market move us?"
  weather: {type: csv, path: external/weather.csv, role: series, value: rainfall_mm, date: date,
            date_columns: [date], unit: mm}                                  # evidence for outside events
```

A new kind of source (an online spreadsheet, a warehouse) is one loader in `scripts/aib/sources.py`.

Since 0.2 a source may declare `key: order_id` (or a list such as `[date, channel]`): one row per value,
which the data-quality step checks. `confirm` writes it only when the user named the column as the id and the
data has one row per value. Closing days are a `quality` block. Missing rows on those days are not missing data:

```yaml
quality:
  closed_weekdays: [5]                 # 0 = Monday
  closed_dates: [2026-12-25]
  source: {kind: data, note: "no rows on 53 of 53 Saturdays"}   # inferred from data ...
  status: proposed                                               # ... so: to confirm, not a fact
```

## 3. model.yaml

```yaml
north_star: gross_profit
measures:            # aggregations of one column of one source
  revenue_m: {source: orders, agg: sum, column: revenue, date: order_date, dimensions: [channel, region]}
  orders_m: {source: orders, agg: count_distinct, column: order_id, date: order_date,
             dimensions: [channel, region], additive_over: [channel, region]}
metrics:
  revenue: {label: {en: Revenue, zh: 营收}, measure: revenue_m, unit: currency}
  orders: {label: {en: Orders, zh: 订单数}, measure: orders_m, unit: count}
  aov: {label: {en: Average order value, zh: 客单价}, kind: ratio, numerator: revenue, denominator: orders, unit: currency}
identities:          # layer 0: formulas; checked against the data on every run
  - {id: revenue_by_orders, left: revenue, factors: [orders, aov], operator: multiply, source: {kind: formula}, status: confirmed}
dimensions:
  channel: {label: {en: Channel, zh: 渠道}, column: channel}
priorities:          # layer 1: which cut to try first; "drill" follows the top segment, "each" cuts every dimension
  revenue: {order: [channel, region], mode: drill, source: {kind: user, date: 2026-10-30}, status: confirmed}
comparisons:         # second order across sides
  - {id: app_vs_web, dimension: channel, sides: [app, web], segment_by: category}
```

- `unit`: `currency`, `count` or `ratio`. Ratio deltas are reported in percentage points.
- `count_distinct` is not summable in general. List in `additive_over` only the dimensions on which each id
  has a single value; `confirm` checks this against the data.
- A table whose rows are visits (a sessions table) is counted, not summed: `agg: count_distinct` over its key (or
  `agg: count` when no column identifies a row), on that table's own `source` and `date`. An identifier column is never
  `agg: sum`. A ratio that prints as 0.00% in both periods while its top and bottom are above zero stops the run
  (param `ratio_shows_zero_below`): the bottom is a sum of ids.
- A measure can be cut only by its own `dimensions`; a ratio only by dimensions both its parts have.
- `priorities.<metric>.mode` (0.2): `drill` (default) scores the candidates at every layer, and a confirmed
  `order` fixes the first cut. `each` cuts every dimension from the top and merges slots that are one cause.
  `fixed` cuts `order` as given, without scoring. A `proposed` order is only a candidate list. `confirm` writes the
  dimensions the person chose, in the order they chose them, as a `proposed` order for each metric. When the
  whole number is within its usual range (the same `overall_quiet` signal the stop decision uses), the scores
  say nothing, because nothing moved. The person's own interest then decides what to show first: the first
  dimension of the `proposed` or `confirmed` order is cut first, and the scores stay in the record. When the
  number did move, the highest score wins; with no order, the scores decide (ties go alphabetical). The run
  records which rule picked the first cut in `notes` (`first_cut`: `quiet_user_order`, `highest_score`,
  `stated_order` or `fixed_order`).
- `pvm` (0.2): `[{metric: revenue, quantity: orders, dimension: category}]` adds a price-volume-mix breakdown
  to every first-order question on that metric.
- Identities are expanded to the leaves (`revenue` → `orders × aov`, `orders` → `visits × cr`). Expansion stops
  where a factor cannot be filtered the way the question is filtered.

## 4. rules.yaml

```yaml
params:              # every threshold is named and sourced; tables refer to them as "param:<name>"
  single_point_min_share: {value: 0.5, source: {kind: user, date: 2026-10-30}, status: confirmed}
tables:              # layer 3: one rule per row, first match wins, last row is the fallback
  - id: stop.cut
    inputs: {top1_abs_share: result.top1_abs_share}     # <operator>.<output field>; "result" = the cut just made
    hit_policy: FIRST
    rows:
      - when: {top1_abs_share: {gte: "param:single_point_min_share"}}
        then: {action: drill, reason: single_point}
      - when: {}
        then: {action: stop, reason: spread}
```

Tables the skill reads: `qualify.unusual`, `qualify.market`, `stop.cut`. Optional params for outside events:
`external_slice_min_share`, `external_size_min_share` (without them those checks report "not judged").

Since 0.2, `confirm` writes the whole default set from `scripts/aib/defaults.py`, each param with its source.
A param missing from an older workspace falls back to that default. The 0.2 `stop.cut` reads the noise gate
(`cut.overall_quiet`, `cut.top1_beats_quiet`, `cut.context_unusual`, `cut.top1_excess`, `cut.top1_abs_z`,
`cut.top1_n`, `cut.has_history`, `cut.order`). A 0.1 table that reads only `result.top1_abs_share` still runs,
but it has no noise gate; copy the table from `defaults.py`. Params by group:

| Group | Params |
|---|---|
| noise gate | `single_point_min_excess`, `segment_z_min`, `segment_z_min_when_unusual`, `segment_min_n`, `drill_when_usual`, `drill_quiet_total_when_group_stands_out`, `group_stands_out_z` |
| search | `search_max_depth`, `search_top_k`, `same_cause_min_share`, `shrink_ratio_segments` |
| data quality | `quality_check_levels` (each check `block` or `warn`), `quality_jump_high` / `_low`, `quality_value_jump`, `quality_row_ratio_max` / `_block`, `quality_single_row_max_share` / `_fail_share`, `quality_extreme_row_times`, `quality_new_value_min_share` |
| history | `history_skip_misaligned_holidays`, `onset_lookback_weeks`, `onset_min_shift_sd` |
Operators: `gte gt lte lt eq ne in not_null`, combinable with `all` / `any`. `check` rejects a table whose
last row is not the fallback, whose rows can never fire, or whose inputs or params do not exist.

## 5. world.yaml

Only the part of the world that explains the numbers. Every entry has `source` and `status`.

```yaml
entities:      # a dimension value is an entity; outside parties too
  - {id: ch_marketplace, type: channel, dimension: channel, key: marketplace, label: {en: Marketplace, zh: 电商平台},
     aliases: [platform], source: {kind: data}, status: confirmed}
relations:     # belongs_to, supplies, goes_through, ...
  - {id: rel_1, subject: city_shanghai, predicate: belongs_to, object: region_east, source: {kind: data}, status: confirmed}
mechanisms:    # why a slice is naturally different
  - {id: mech_commission, entities: [ch_marketplace], metrics: [margin_rate], direction: lower,
     claim: {en: "...", zh: "..."}, refuted_by: {en: "...", zh: "..."},
     source: {kind: user, date: 2026-10-30, quote: "..."}, status: confirmed}
events:        # what happened, when; end is optional (missing = still going)
  - {id: ev_rain, kind: external, start: 2026-10-21, end: 2026-10-23, entities: [region_east, deliv_same_day],
     what: {en: "...", zh: "..."}, evidence: {source: weather, filters: {region: east}},
     refuted_by: {en: "...", zh: "..."}, source: {kind: document, ref: "https://...", label: {en: "...", zh: "..."}}, status: proposed}
actions:       # who can do what
  - {id: act_1, entities: [ch_marketplace], action: {en: "...", zh: "..."}, owner: {en: Channel manager, zh: 渠道负责人},
     source: {kind: user}, status: confirmed}
```

`refuted_by` says, in plain words, what data would show the entry is wrong. It is printed under every citation so
the reader knows what to check; the engine's own checks (the fit of a reason to the change, the three checks for
outside events) run regardless. `source.label` is the readable name of a source in each language.

A dimension value that is empty or the word `NULL` is shown in reports as `(blank)` (`(空)` in Chinese): the rows
have no recorded value, they are not a group called NULL. Only the shown name changes; the group keeps its key and
every number. Give that entity a `label` of your own (for example an agent code that really is `NULL`) and the
report shows your name instead.

An entry is cited for a slice only if **all** its entities are in that slice's context (filters, drill path,
the slice itself, compared sides). Mechanisms also need a matching metric; events must overlap the window.

## 6. Sources and statuses

| `source.kind` | Meaning |
|---|---|
| `user` | the user said it (keep `quote` and `date`) |
| `document` | from a document or web page (keep `ref`) |
| `data` | inferred from the data itself |
| `system_record` | from a business system log (price changes, campaign calendar) |
| `general_knowledge` | general industry knowledge; a draft only |
| `formula` | arithmetic |
| `demo_setting` | a setting of the fictional demo shop |

`status`: `confirmed`, `proposed` (to confirm), `retired` (kept for history, never cited).

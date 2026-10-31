# Recording a correction

[中文](learning.zh.md)

`correct --workspace <dir> --json '<correction>'` changes one workspace file, appends the correction to
`corrections.jsonl` with the user's words, and writes `regressions/<date>_<target>.yaml`.
`regress` replays every case; a failure means something the user taught has been lost.

## 1. Common fields

| Field | Meaning |
|---|---|
| `type` | one of the types below |
| `quote` | the user's own words, unedited |
| `run` | the config of the run that prompted it (lets the regression case replay it) |
| `slot` | the slice it explains, as in the run's `slots[].id`, e.g. `customer_type=new` or `channel=marketplace/region=east` |

## 2. Types

```json
{"type": "add_mechanism", "slot": "customer_type=new", "quote": "New customers buy a small first order",
 "entry": {"entities": ["cust_new"], "metrics": ["aov"], "direction": "lower",
           "claim": {"en": "New customers buy a smaller first order", "zh": "新客第一单买小份"}}, "run": {...}}

{"type": "add_event", "slot": "region=east", "quote": "There was a storm that week",
 "entry": {"kind": "external", "start": "2026-10-21", "end": "2026-10-23", "entities": ["region_east"],
           "what": {"en": "Storm in the east", "zh": "华东暴雨"},
           "source": {"kind": "document", "ref": "https://..."}, "status": "proposed"}, "run": {...}}

{"type": "add_action", "quote": "...", "entry": {"entities": ["ch_marketplace"],
 "action": {"en": "...", "zh": "..."}, "owner": {"en": "Channel manager", "zh": "渠道负责人"}}, "run": {...}}

{"type": "add_alias", "entity": "ch_marketplace", "alias": "platform", "quote": "we call it the platform"}
{"type": "set_priority", "metric": "revenue", "order": ["region", "channel"], "quote": "...", "run": {...}}
{"type": "set_param", "name": "single_point_min_share", "value": 0.6, "quote": "..."}
{"type": "confirm", "bucket": "events", "id": "ev_east_rainstorm", "quote": "yes, it rained"}
{"type": "retire", "bucket": "mechanisms", "id": "mech_x", "reason": "no longer true", "slot": "...", "run": {...}}
```

Entries the user states are stored as `source: {kind: user, date, quote}` and `status: confirmed`.
Entries found elsewhere (a news link) keep the `source` you give and default to `status: proposed`.

## 3. What the regression case checks

| Type | Must stay true |
|---|---|
| `add_mechanism`, `add_event` with a `slot` | that slot cites the new entry |
| `add_action` | the run lists the action |
| `add_alias` | the alias resolves to the entity |
| `set_priority` | the first cut is the first dimension in the new order |
| `set_param` | the param has the new value |
| `confirm`, `retire` | the entry has the new status; a retired entry is not cited for `slot` |

After recording, re-run the question to show the difference, then run `regress` and report how many cases pass.

## 4. Can this entry explain this change? (0.2)

Two optional fields say whether an entry can explain a change. Ask the user rather than guess:

- `start` / `end` (events; also allowed on mechanisms), or `period: both` for something true all the time.
  Something true in both periods cannot explain a change between them. Every citation carries `explains`:
  `change`, `why_mix_matters` (it says why a shift in mix moves the number, not why the mix shifted),
  `cannot_explain_change` or `term_mismatch`. Only `change` makes a slot explained.
- `acts_on: structure | rate`: does it change the mix of groups, or each group's own level? An entry that acts
  on the other term from the one that moved is `term_mismatch`.

So when the user offers a reason, also ask "since when?". "New customers always buy smaller first orders" is
true, but it does not answer why the average fell this year. Record it with `period: both`, and ask what changed.

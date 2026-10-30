# 记一条纠正

[English](learning.md)

`correct --workspace <目录> --json '<纠正>'` 会改一个工作目录文件，把这条纠正连同用户原话追加进 `corrections.jsonl`，
并写出 `regressions/<日期>_<对象>.yaml`。`regress` 会重放所有回归题；有一道没过，就说明用户教过的某样东西丢了。

## 1. 通用字段

| 字段 | 意思 |
|---|---|
| `type` | 下面的类型之一 |
| `quote` | 用户原话，不改写 |
| `run` | 引出这条纠正的那次运行的配置（回归题靠它重放） |
| `slot` | 它解释的那一块，就是运行结果里 `slots[].id`，例如 `customer_type=new` 或 `channel=marketplace/region=east` |

## 2. 类型

```json
{"type": "add_mechanism", "slot": "customer_type=new", "quote": "新客第一单一般买小份",
 "entry": {"entities": ["cust_new"], "metrics": ["aov"], "direction": "lower",
           "claim": {"en": "New customers buy a smaller first order", "zh": "新客第一单买小份"}}, "run": {...}}

{"type": "add_event", "slot": "region=east", "quote": "那周下了暴雨",
 "entry": {"kind": "external", "start": "2026-10-21", "end": "2026-10-23", "entities": ["region_east"],
           "what": {"en": "Storm in the east", "zh": "华东暴雨"},
           "source": {"kind": "document", "ref": "https://..."}, "status": "proposed"}, "run": {...}}

{"type": "add_action", "quote": "...", "entry": {"entities": ["ch_marketplace"],
 "action": {"en": "...", "zh": "..."}, "owner": {"en": "Channel manager", "zh": "渠道负责人"}}, "run": {...}}

{"type": "add_alias", "entity": "ch_marketplace", "alias": "平台", "quote": "我们管它叫平台"}
{"type": "set_priority", "metric": "revenue", "order": ["region", "channel"], "quote": "...", "run": {...}}
{"type": "set_param", "name": "single_point_min_share", "value": 0.6, "quote": "..."}
{"type": "confirm", "bucket": "events", "id": "ev_east_rainstorm", "quote": "对，那几天确实在下雨"}
{"type": "retire", "bucket": "mechanisms", "id": "mech_x", "reason": "已经不成立了", "slot": "...", "run": {...}}
```

用户自己说的条目存成 `source: {kind: user, date, quote}`、`status: confirmed`。
从别处找到的（比如一条新闻链接）保留你给的 `source`，默认 `status: proposed`。

## 3. 回归题检查什么

| 类型 | 从此必须一直成立 |
|---|---|
| 带 `slot` 的 `add_mechanism`、`add_event` | 那一块引用了这条新记录 |
| `add_action` | 运行结果里列出了这个动作 |
| `add_alias` | 这个别名能认到那个实体 |
| `set_priority` | 第一刀切的是新顺序里的第一个维度 |
| `set_param` | 这个门槛是新的值 |
| `confirm`、`retire` | 这条记录是新的状态；作废的记录在 `slot` 上不再被引用 |

记完之后，再跑一次这个问题，让用户看到变化；然后跑 `regress`，告诉用户通过了几道。

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

## 4. 这条记录能不能解释这次的变化（0.2）

两个可选字段说明一条记录能不能解释变化。不确定就问用户，不要猜：

- `start` / `end`（事件用；机制也可以用），或者 `period: both`，表示一直成立。两期都成立的事，解释不了两期之间的变化。
  每条引用都带 `explains`：`change`、`why_mix_matters`（说明了占比变化为什么会拉动这个数，没说明占比为什么变）、
  `cannot_explain_change` 或 `term_mismatch`。只有 `change` 才能让一处算已解释。
- `acts_on: structure | rate`：它改变的是各组的占比，还是各组自己的水平？说的那一项和实际变的那一项对不上，就是 `term_mismatch`。

所以用户给出一个原因时，再问一句「从什么时候开始的？」。「新客第一单总是买得小」是真的，但回答不了今年客单价为什么降了。
把它记成 `period: both`，再问这段时间发生了什么。

# 工作目录格式

[English](workspace.md)

工作目录是一个文件夹，存一家公司自己的知识。skill 读这些文件；只通过 `confirm`（第一次使用）和 `correct`（学习）去写。
演示店里有一份完整的例子。

目录：1 文件 · 2 project.yaml · 3 model.yaml · 4 rules.yaml · 5 world.yaml · 6 出处和状态

## 1. 文件

| 文件 | 装什么 | 谁写 |
|---|---|---|
| `project.yaml` | 名称、语言、数据来源、外部来源 | `confirm`，或手写 |
| `model.yaml` | 方法层：度量、指标、公式、维度、切分顺序、对比 | `confirm`、`correct`，结构可手改 |
| `rules.yaml` | 带出处的命名阈值、决策表 | `confirm`、`correct` |
| `world.yaml` | 实体、关系、机制、事件、动作和负责人 | `confirm`、`correct` |
| `corrections.jsonl` | 每一条纠正，带用户原话 | `correct` |
| `regressions/*.yaml` | 每条纠正一道可重放的回归题 | `correct` |
| `runs/<id>/` | `record.json`、`report.zh.md`、`report.en.md`、`charts/` | `run` |
| `docs/` | 从 YAML 生成的、带链接的可读页面 | `docs` |

## 2. project.yaml

```yaml
name: 我的店
language: zh                     # 报告默认语言
sources:                         # 一张表一条；类型：csv、excel、sqlite、duckdb
  orders: {type: csv, path: data/orders.csv, date_columns: [order_date]}
  traffic: {type: sqlite, path: shop.db, table: daily_visits, date_columns: [date]}
external:                        # 外部数据，同样的读取方式；role 说明怎么用
  calendar: {type: csv, path: external/calendar.csv, role: calendar}         # name, start, end[, label_zh, label_en]
  market: {type: csv, path: external/market.csv, role: market, value: market_sales, date: date,
           date_columns: [date], compares_with: revenue}                    # 「是不是大盘带着走」
  weather: {type: csv, path: external/weather.csv, role: series, value: rainfall_mm, date: date,
            date_columns: [date], unit: mm}                                  # 外部事件的证据
```

要加一种新来源（在线表格、数仓），只需在 `scripts/aib/sources.py` 里加一个读取函数。

0.2 起，来源可以声明 `key: order_id`（或者一组列，比如 `[date, channel]`），表示每个值只对应一行，数据检查会核它。
只有用户指认这一列是编号、而且数据里确实一行一个值时，`confirm` 才会写上。不营业日写在 `quality` 一段里，这几天没有数据不算缺数据：

```yaml
quality:
  closed_weekdays: [5]                 # 0 = 周一
  closed_dates: [2026-12-25]
  source: {kind: data, note: "53 个周六全都没有记录"}   # 从数据推断……
  status: proposed                                      # ……所以是待确认，不是事实
```

## 3. model.yaml

```yaml
north_star: gross_profit
measures:            # 对某个来源某一列的聚合
  revenue_m: {source: orders, agg: sum, column: revenue, date: order_date, dimensions: [channel, region]}
  orders_m: {source: orders, agg: count_distinct, column: order_id, date: order_date,
             dimensions: [channel, region], additive_over: [channel, region]}
metrics:
  revenue: {label: {en: Revenue, zh: 营收}, measure: revenue_m, unit: currency}
  orders: {label: {en: Orders, zh: 订单数}, measure: orders_m, unit: count}
  aov: {label: {en: Average order value, zh: 客单价}, kind: ratio, numerator: revenue, denominator: orders, unit: currency}
identities:          # 第零层：公式；每次运行都在数据上核一遍
  - {id: revenue_by_orders, left: revenue, factors: [orders, aov], operator: multiply, source: {kind: formula}, status: confirmed}
dimensions:
  channel: {label: {en: Channel, zh: 渠道}, column: channel}
priorities:          # 第一层：先切哪刀；drill 沿第一名往下钻，each 每个维度都切一遍
  revenue: {order: [channel, region], mode: drill, source: {kind: user, date: 2026-10-30}, status: confirmed}
comparisons:         # 二阶，比维度两侧
  - {id: app_vs_web, dimension: channel, sides: [app, web], segment_by: category}
```

- `unit`：`currency`、`count` 或 `ratio`。比率的变化用百分点报告。
- `count_distinct` 一般不能直接相加。`additive_over` 里只列「每个编号在这个维度上只有一个值」的维度；`confirm` 会拿数据核。
- 一个度量只能按它自己的 `dimensions` 切；比率只能按分子分母都有的维度切。
- `priorities.<指标>.mode`（0.2）：`drill`（默认）每层都给候选维度打分，确认过的 `order` 决定第一刀；
  `each` 每个维度都从头切一遍，再把是同一个原因的槽位合并；`fixed` 照 `order` 原样切，不打分。`proposed` 状态的顺序只当候选清单。`confirm` 会把用户选的维度，按他选的顺序，给每个指标写成一条 `proposed` 顺序；两个候选得分相同时，先切这个顺序里靠前的，得分高的永远优先。没有 proposed 顺序时，得分相同按维度名的字母顺序。
- `pvm`（0.2）：`[{metric: revenue, quantity: orders, dimension: category}]`，给这个指标的每道一阶题加一份量、结构、价格的拆解。
- 公式会一直展开到叶子（`revenue` → `orders × aov`，`orders` → `visits × cr`）。某个因子没法按题目的过滤条件切时，就停在那一层。

## 4. rules.yaml

```yaml
params:              # 每个阈值都有名字和出处；决策表里写成 "param:<名字>"
  single_point_min_share: {value: 0.5, source: {kind: user, date: 2026-10-30}, status: confirmed}
tables:              # 第三层：一行一条规则，从上往下第一条命中的生效，最后一行是兜底
  - id: stop.cut
    inputs: {top1_abs_share: result.top1_abs_share}     # <算子>.<输出字段>；result = 刚切完的那一刀
    hit_policy: FIRST
    rows:
      - when: {top1_abs_share: {gte: "param:single_point_min_share"}}
        then: {action: drill, reason: single_point}
      - when: {}
        then: {action: stop, reason: spread}
```

skill 会读的表：`qualify.unusual`、`qualify.market`、`stop.cut`。外部事件可选的门槛：
`external_slice_min_share`、`external_size_min_share`（没有就报「未判断」）。

0.2 起，`confirm` 会把 `scripts/aib/defaults.py` 里的全套默认参数写进来，每个都带出处；老工作目录缺的参数按默认值算。
0.2 的 `stop.cut` 读噪音门的输入（`cut.overall_quiet`、`cut.top1_beats_quiet`、`cut.context_unusual`、`cut.top1_excess`、
`cut.top1_abs_z`、`cut.top1_n`、`cut.has_history`、`cut.order`）。0.1 只读 `result.top1_abs_share` 的表照样能跑，但没有噪音门；
从 `defaults.py` 抄一份新表过来。参数分组如下：

| 组 | 参数 |
|---|---|
| 噪音门 | `single_point_min_excess`、`segment_z_min`、`segment_z_min_when_unusual`、`segment_min_n`、`drill_when_usual`、`drill_quiet_total_when_group_stands_out`、`group_stands_out_z` |
| 选维度 | `search_max_depth`、`search_top_k`、`same_cause_min_share`、`shrink_ratio_segments` |
| 数据检查 | `quality_check_levels`（每项 `block` 或 `warn`）、`quality_jump_high` / `_low`、`quality_value_jump`、`quality_row_ratio_max` / `_block`、`quality_single_row_max_share` / `_fail_share`、`quality_extreme_row_times`、`quality_new_value_min_share` |
| 历史 | `history_skip_misaligned_holidays`、`onset_lookback_weeks`、`onset_min_shift_sd` |
比较符：`gte gt lte lt eq ne in not_null`，可用 `all` / `any` 组合。最后一行不是兜底、有永远命中不了的行、
引用了不存在的输入或门槛，`check` 都会报出来。

## 5. world.yaml

只描述能解释数字的那部分世界。每一条都有 `source` 和 `status`。

```yaml
entities:      # 维度值就是实体；公司外面的也算
  - {id: ch_marketplace, type: channel, dimension: channel, key: marketplace, label: {en: Marketplace, zh: 电商平台},
     aliases: [platform], source: {kind: data}, status: confirmed}
relations:     # belongs_to（属于）、supplies（供货）、goes_through（经由）……
  - {id: rel_1, subject: city_shanghai, predicate: belongs_to, object: region_east, source: {kind: data}, status: confirmed}
mechanisms:    # 为什么这一块的数天生不一样
  - {id: mech_commission, entities: [ch_marketplace], metrics: [margin_rate], direction: lower,
     claim: {en: "...", zh: "..."}, refuted_by: {en: "...", zh: "..."},
     source: {kind: user, date: 2026-10-30, quote: "..."}, status: confirmed}
events:        # 什么时候发生了什么；end 可省略（省略 = 还在持续）
  - {id: ev_rain, kind: external, start: 2026-10-21, end: 2026-10-23, entities: [region_east, deliv_same_day],
     what: {en: "...", zh: "..."}, evidence: {source: weather, filters: {region: east}},
     refuted_by: {en: "...", zh: "..."}, source: {kind: document, ref: "https://...", label: {en: "...", zh: "..."}}, status: proposed}
actions:       # 谁能做什么
  - {id: act_1, entities: [ch_marketplace], action: {en: "...", zh: "..."}, owner: {en: Channel manager, zh: 渠道负责人},
     source: {kind: user}, status: confirmed}
```

`refuted_by` 用大白话写清：什么数据出现，就说明这条记录是错的。每次引用都会把它印在下面，让读的人知道该去核对什么；
引擎自己的检查（原因和这次变化对不对得上、外部事件的三道检查）照常进行，不依赖它。`source.label` 是出处在两种语言里的可读名字。

维度值为空、或就是 `NULL` 这个词时，报告里显示为 `(空)`（英文版是 `(blank)`）：这些行没有记录下这个值，并不是一个叫 NULL 的组。只改显示的名字，分组仍用原来的值，所有数字不变。给这个实体自己写一个 `label`（比如某个代理编码真的就叫 `NULL`），报告就显示你起的名字。

一条记录只有在它的**全部**实体都落在这一块的上下文里（筛选条件、下钻路径、这一块本身、对比的两侧）时才会被引用。
机制还要指标对得上；事件还要和时间窗有重叠。

## 6. 出处和状态

| `source.kind` | 意思 |
|---|---|
| `user` | 用户说的（保留 `quote` 和 `date`） |
| `document` | 来自文档或网页（保留 `ref`） |
| `data` | 从数据本身推出来的 |
| `system_record` | 来自业务系统的记录（调价、活动日历） |
| `general_knowledge` | 行业常识；只当草稿 |
| `formula` | 算术 |
| `demo_setting` | 虚构演示店的设定 |

`status`：`confirmed`（已确认）、`proposed`（待确认）、`retired`（已作废，保留历史，不再引用）。

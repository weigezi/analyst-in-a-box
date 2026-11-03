# 形成报告：从几张原始表到一个能答题的工作区

[English](formation.md)

演示店「花果篮」的同一批数据，拆成真实系统常见的 9 张表（`tables/`），外加一份周报（`docs/weekly_report.zh.md`）。skill 自己读表、出选择题，店主回答（`answers.yaml`），AI 工具读周报提出候选（`proposals.yaml`），然后直接答题。下面把自动形成的工作区（`workspace/`）和手写的演示工作区（`../store/workspace/`）逐项对照。本报告由 `run_intake.py` 生成，数字都是从两个工作区读出来的。

## 一、四类来源各有多少

| 类 | 数量 |
|---|---|
| 机器从数据推出（再经选择题确认） | 45 |
| 选择题（问了 / 答了） | 46 / 37 |
| 从文档抽出、待确认（收下 / 拒收） | 3 / 0 |
| 只有人能补、目前空着 | 6 |

## 二、机器自己从数据推出来的

| 类 | 数量 | 内容 |
|---|---|---|
| 维度 | 6 | channel, category, region, city, delivery, customer_type |
| 维度值（实体） | 24 |  |
| 「属于」关系 | 8 | city→region |
| 查找表并进主表 | 2 | products, cities |
| 公式算出的指标 | 3 | per_id, margin, conversion |
| 恒等式 | 3 | revenue_by_per_id, gross_profit_by_margin, id_count_by_conversion |
| 外部数据 | 3 | holidays (calendar), market (market), weather (series) |
| 事件表里的事件（系统记录，待确认） | 3 | 供应商涨价，礼盒售价上调 15% 2026-06-01~2026-06-30; 情人节花束主推 2026-02-07~2026-02-14; 新客买果篮送贺卡 2026-10-01~2026-10-31 |

## 三、用户在选择题里确认的

| 问题 | 建议的答案 | 用户的回答 |
|---|---|---|
| `main_table` | orders | orders |
| `kind:cities` | lookup | lookup |
| `kind:holidays` | calendar | calendar |
| `kind:market` | series | market (改了建议) |
| `kind:price_changes` | events | events |
| `kind:products` | lookup | lookup |
| `kind:promotions` | events | events |
| `kind:traffic` | business | business |
| `kind:weather` | series | series |
| `link:orders.sku>products.sku` | yes | yes |
| `link:orders.city>cities.city` | yes | yes |
| `link:price_changes.category>products.category` | yes | yes |
| `link:promotions.category>products.category` | yes | yes |
| `link:promotions.customer_type>orders.customer_type` | yes | yes |
| `link:traffic.channel>orders.channel` | yes | yes |
| `link:weather.region>cities.region` | yes | yes |
| `event_text:holidays` | name | name |
| `role:market.market_sales` | — | skip |
| `market_compares:market` | none | revenue (改了建议) |
| `event_text:price_changes` | reason | reason |
| `event_kind:price_changes` | internal | internal |
| `event_text:promotions` | campaign | campaign |
| `event_kind:promotions` | internal | internal |
| `role:traffic.visits` | — | visits |
| `role:weather.rainfall_mm` | — | skip |
| `market_compares:weather` | none | none |
| `date_column` | order_date | order_date |
| `role:revenue` | — | amount |
| `role:gross_profit` | — | profit |
| `order_id` | — | order_id |
| `template` | — | orders |
| `north_star` | — | gross_profit |
| `dimensions` | — | channel, category, region, city, delivery, customer_type |
| `belongs:sku>category` | — | no |
| `belongs:city>region` | — | yes |
| `belongs:name>category` | — | no |
| `single_point_share` | — | 0.5 |
| `reversal_column` | none | — |
| `reversal_values:sku` | — | — |
| `reversal_values:channel` | — | — |
| `reversal_values:city` | — | — |
| `reversal_values:delivery` | — | — |
| `reversal_values:customer_type` | — | — |
| `reversal_values:category` | — | — |
| `reversal_values:name` | — | — |
| `reversal_values:region` | — | — |

靠用户指认含义才有的指标（金额、毛利、访问量、订单数）：revenue, gross_profit, visits, id_count

## 四、从文档抽出来、待确认的

| 类型 | 原句 | 记成 |
|---|---|---|
| event | 「电商平台从 10 月 12 日起执行新的费用条款，我们没有接受新的抽成档位，店铺随后掉出了首页推荐位，搜索流量明显变少。」 | `ev_marketplace_fee_terms` |
| event | 「华东 21 日到 23 日连着三天大暴雨，上海、杭州两地的当日达几乎停摆」 | `ev_east_rainstorm` |
| mechanism | 「当日达要靠骑手上路，雨一大就送不出去，这在雨季是老问题。」 | `mech_same_day_needs_riders` |

## 五、只有人能补的

| 要补的 | 为什么只有人能补 |
|---|---|
| 机制 | 某一组的数为什么天生不一样（抽佣金、品类便宜）；目前 1 条，都来自周报、待确认，已确认 0 条 |
| 动作和负责人 | 谁去做、能做什么 |
| 切分顺序 | 先看哪个维度；定之前每一层按打分选 |
| 对比组 | 哪两边值得比（App 对比网页） |
| 量-结构-价格 | 哪个数是「量」、价格按哪个维度拆 |
| 可读名字 | 代码对应的名字（marketplace → 电商平台）；数据里只有代码 |

## 六、和手写工作区逐项对照

| 项目 | 手写工作区 | 自动形成 | 对得上吗 |
|---|---|---|---|
| 维度 | category, channel, city, customer_type, delivery, region | category, channel, city, customer_type, delivery, region | 对上 |
| 指标 | aov, cr, gross_profit, margin_rate, orders, revenue, visits | conversion, gross_profit, id_count, margin, per_id, revenue, visits | 对上 |
| 恒等式 | 3 | 3 | 对上 |
| 维度值 | 24 | 24 | 对上 |
| 有可读名字的维度值 | 24 | 0 | 没对上 |
| 「属于」关系 | 9 | 8 | 部分对上 |
| 事件 | ev_app_homepage_change, ev_east_rainstorm, ev_marketplace_fee_change | ev_east_rainstorm, ev_marketplace_fee_terms, ev_price_changes_1, ev_promotions_1, ev_promotions_2 | 部分对上 |
| 机制 | 3 | 1 | 没对上 |
| 动作和负责人 | 3 | 0 | 没对上 |
| 对比组 | 1 | 0 | 没对上 |
| 确认过的切分顺序 | aov, gross_profit, margin_rate, revenue | — | 没对上 |
| 量-结构-价格拆解 | 1 | 0 | 没对上 |
| 外部数据 | calendar, market, series | calendar, market, series | 对上 |

## 七、拿形成的工作区答题

| 问题 | 主因 | 引用 | 状态 |
|---|---|---|---|
| revenue_last_week | `channel=marketplace` | `ev_marketplace_fee_terms` (文档，待确认) | 推测 / 待确认 |
| east_last_week | `delivery=same_day` | `ev_east_rainstorm` (文档，待确认，对着天气数据过了三道检查) | 已解释 |
| aov_last_week | `category=fruit_basket/customer_type=new` | `ev_promotions_2` (系统记录，待确认) | 推测 / 待确认 |
| june_revenue | `category=gift_box` | `ev_price_changes_1` (系统记录，待确认) | 推测 / 待确认 |
| first_run | `channel=marketplace` | `ev_marketplace_fee_terms` (文档，待确认) | 推测 / 待确认 |

暴雨虽然来自周报，却算已解释：外部事件看的是对着外部数据（这里是降雨量）的三道检查，不看谁确认过。这是 0.1 起对外部事件的规则，没有改。

## 八、没对上的地方

- 维度值没有可读名字：自动形成的是 marketplace、fruit_basket 这样的代码，手写版是「电商平台」「果篮」。数据里没有中文名，只有人能补。
- 事件不完全一样：「App 首页撤掉绿植推荐位」在手写版里来自 App 发版记录，这次没给这份记录，所以没形成。反过来，活动日历和调价记录里的三件事（情人节主推、10 月新客果篮送贺卡、6 月礼盒涨价）是自动形成独有的；手写版里贺卡活动是靠用户纠正补上的。
- 机制只形成了 1 条（从周报抽出的「当日达靠骑手」）；手写版的 3 条里，「平台抽佣金所以毛利低」「果篮最便宜」数据和周报里都没有，只有人能说。
- 「属于」关系少一类：手写版有「电商平台经由平台方」这种连到外部实体的关系，数据里推不出来。
- 没有对比组：「App 对比网页」这道二阶题，要人说哪两边值得比，所以形成的工作区答不了那一题。
- 切分顺序都是「待确认」：手写版是维护者定的顺序；形成的工作区每层按打分选，第一刀不一定是渠道。
- 没有量-结构-价格拆解：要人说哪个数是「量」、按哪个维度拆，6 月那道题因此只拆到品类，没有拆量和价。

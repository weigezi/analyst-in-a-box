# Formation report: from a few raw tables to a workspace that answers questions

[中文](formation.zh.md)

The same data as the demo shop "Bloom & Basket", split into 9 tables shaped like real system exports (`tables/`), plus a weekly report (`docs/weekly_report.zh.md`). The skill reads the tables and asks multiple-choice questions; the owner answers (`answers.yaml`); an AI tool reads the report and proposes candidates (`proposals.yaml`); then it answers questions. Below, the formed workspace (`workspace/`) is set against the hand-written demo workspace (`../store/workspace/`) part by part. `run_intake.py` writes this report; every number is read from the two workspaces.

## 1. How much came from each source

| Kind | Count |
|---|---|
| inferred from the data (then confirmed in a question) | 45 |
| questions (asked / answered) | 38 / 38 |
| from a document, to confirm (accepted / refused) | 3 / 0 |
| only a person can add; empty so far | 6 |

## 2. What the machine inferred from the data

| Kind | Count | What |
|---|---|---|
| dimensions | 6 | channel, category, region, city, delivery, customer_type |
| dimension values (entities) | 24 |  |
| "belongs to" relations | 8 | city→region |
| lookup tables joined to the main table | 2 | products, cities |
| metrics from formulas | 3 | per_id, margin, conversion |
| identities | 3 | revenue_by_per_id, gross_profit_by_margin, id_count_by_conversion |
| outside data | 3 | holidays (calendar), market (market), weather (series) |
| events from event tables (system records, to confirm) | 3 | 供应商涨价，礼盒售价上调 15% 2026-06-01~2026-06-30; 情人节花束主推 2026-02-07~2026-02-14; 新客买果篮送贺卡 2026-10-01~2026-10-31 |

## 3. What the user confirmed in the questions

| Question | Suggested | Answered |
|---|---|---|
| `main_table` | orders | orders |
| `kind:cities` | lookup | lookup |
| `kind:holidays` | calendar | calendar |
| `kind:market` | series | market (changed the suggestion) |
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
| `market_compares:market` | none | revenue (changed the suggestion) |
| `event_text:price_changes` | reason | reason |
| `event_kind:price_changes` | internal | internal |
| `event_text:promotions` | campaign | campaign |
| `event_kind:promotions` | internal | internal |
| `role:traffic.visits` | — | visits |
| `role:weather.rainfall_mm` | — | skip |
| `market_compares:weather` | none | none |
| `date_column` | — | order_date |
| `role:revenue` | — | amount |
| `role:gross_profit` | — | profit |
| `role:list_price` | — | skip |
| `order_id` | — | order_id |
| `template` | — | orders |
| `north_star` | — | gross_profit |
| `dimensions` | — | channel, category, region, city, delivery, customer_type |
| `belongs:sku>category` | — | no |
| `belongs:city>region` | — | yes |
| `belongs:name>category` | — | no |
| `single_point_share` | — | 0.5 |

Metrics that exist because the user named a column's meaning (amount, profit, visits, orders): revenue, gross_profit, visits, id_count

## 4. What was taken from a document, to confirm

| Type | Sentence | Recorded as |
|---|---|---|
| event | "电商平台从 10 月 12 日起执行新的费用条款，我们没有接受新的抽成档位，店铺随后掉出了首页推荐位，搜索流量明显变少。" | `ev_marketplace_fee_terms` |
| event | "华东 21 日到 23 日连着三天大暴雨，上海、杭州两地的当日达几乎停摆" | `ev_east_rainstorm` |
| mechanism | "当日达要靠骑手上路，雨一大就送不出去，这在雨季是老问题。" | `mech_same_day_needs_riders` |

## 5. What only a person can add

| To add | Why only a person can |
|---|---|
| mechanisms | why a group's number is naturally different (a commission, a cheaper category); 1 so far, all from the report and waiting for confirmation, 0 confirmed |
| actions and owners | who acts, and what they can do |
| cut order | which dimension to look at first; until then every layer is chosen by score |
| comparisons | which two sides are worth comparing (app vs web) |
| price-volume-mix | which number is the quantity and which dimension to split prices by |
| readable names | names for codes (marketplace → 电商平台); the data holds only codes |

## 6. Against the hand-written workspace

| Part | Hand-written | Formed | Match |
|---|---|---|---|
| dimensions | category, channel, city, customer_type, delivery, region | category, channel, city, customer_type, delivery, region | match |
| metrics | aov, cr, gross_profit, margin_rate, orders, revenue, visits | conversion, gross_profit, id_count, margin, per_id, revenue, visits | match |
| identities | 3 | 3 | match |
| entities | 24 | 24 | match |
| dimension values with a readable name | 24 | 0 | differs |
| relations | 9 | 8 | partly |
| events | ev_app_homepage_change, ev_east_rainstorm, ev_marketplace_fee_change | ev_east_rainstorm, ev_marketplace_fee_terms, ev_price_changes_1, ev_promotions_1, ev_promotions_2 | partly |
| mechanisms | 3 | 1 | differs |
| actions | 3 | 0 | differs |
| comparisons | 1 | 0 | differs |
| confirmed priorities | aov, gross_profit, margin_rate, revenue | — | differs |
| price-volume-mix | 1 | 0 | differs |
| outside data | calendar, market, series | calendar, market, series | match |

## 7. Asking the formed workspace

| Question | Main cause | Cites | Status |
|---|---|---|---|
| revenue_last_week | `channel=marketplace` | `ev_marketplace_fee_terms` (document, to confirm) | hypothesis / to confirm |
| east_last_week | `delivery=same_day` | `ev_east_rainstorm` (document, to confirm, passed the three checks against the weather data) | explained |
| aov_last_week | `category=fruit_basket/customer_type=new` | `ev_promotions_2` (system record, to confirm) | hypothesis / to confirm |
| june_revenue | `category=gift_box` | `ev_price_changes_1` (system record, to confirm) | hypothesis / to confirm |
| first_run | `channel=marketplace` | `ev_marketplace_fee_terms` (document, to confirm) | hypothesis / to confirm |

The rainstorm counts as explained although it came from the report: an outside event is judged by the three checks against outside data (here the rainfall), not by who confirmed it. That is the 0.1 rule for outside events, kept.

## 8. Where it does not match

- Dimension values have no readable names: the formed workspace has codes like marketplace and fruit_basket, the hand-written one has 电商平台 and 果篮. The data has no display names; only a person can add them.
- The events are not the same set. "The app home page dropped its plants slot" comes from the app's release notes in the hand-written workspace; no such record was given, so it was not formed. The other way round, three entries from the campaign calendar and the price-change log (the Valentine's push, the October card offer, the June gift-box price rise) exist only in the formed one; in the hand-written workspace the card offer was added by a user correction.
- One mechanism was formed (from the report: same-day needs riders). Of the hand-written three, "the marketplace takes a commission, so margin is lower" and "fruit baskets are the cheapest" are in neither the data nor the report; only a person can say them.
- One kind of relation is missing: the hand-written workspace links the marketplace to an outside entity (the marketplace operator); the data cannot show that.
- No comparison: the second-order question "app vs web" needs a person to say which two sides are worth comparing, so the formed workspace cannot answer it.
- Every cut order is "to confirm": the hand-written one is the maintainer's order; the formed one chooses every layer by score, so the first cut is not always the channel.
- No price-volume-mix: a person has to say which number is the quantity and which dimension to split by, so the June question stops at the category and does not split volume and price.

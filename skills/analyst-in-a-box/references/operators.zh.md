# 方法

[English](operators.md)

每种方法都是公开发表过的方法，由脚本计算，并且都有测试保证各项之和正好等于总变化（`tests/test_ops.py`，含随机用例）。
代码在 `scripts/aib/ops/` 和 `scripts/aib/qualify.py`。

## 1. 拆之前先判断

| 问题 | 方法 | 出处 |
|---|---|---|
| 这一期对这个指标来说算不算异常？ | 这一期的变化和过去 N 期的变化比，算稳健 z 值（中位数和中位数绝对偏差，系数 1.4826），加上百分位 | Iglewicz & Hoaglin (1993)，*How to Detect and Handle Outliers* |
| 是不是大盘带着走？ | 预期变化 = 基期 ×（大盘增速 + 我们相对大盘的常态差距，取过去同样各期的中位数）；剩下的是「自己的」。这是估计；只按大盘算的那个数也保留 | 偏离-份额分析，Dunn (1960)；先扣掉长期差异见 Esteban-Marquillas (1972) |
| 两段的节假日对得上吗？ | 一个节日一个节日地数，各落在两个时间窗里几天；对不上的过去各期不算进上面的历史 | 算术 |
| 数据本身靠得住吗？ | 日历、声明的主键、每天条数和金额对比最近同一星期几的中位数、两期行数比、逐条去掉看影响、疑似改名；每项标「停发」或「提醒」 | `scripts/aib/quality.py`；门槛在 `rules.yaml` |
| 历史平坦（中位数绝对偏差为 0） | 改用平均绝对偏差 × 1.253314；这个也为 0 就说历史平坦 | Iglewicz & Hoaglin (1993) |
| 从哪天开始的？ | 主因那一组每天和对应基期日的差；用最小二乘找一个均值变化点，变化量 ≥ 2 个标准差才点名 | Hinkley (1970)，*Biometrika* 57(1) |

## 2. 一阶：比一次

| 指标形态 | 方法 | 输出 |
|---|---|---|
| 能相加的（营收、订单数）按维度切 | 加法：每组自己的变化；占比合计 100% | `top1_key`、`top1_abs_share`、`same_direction_share`，每组的 `delta`、`share` |
| 几个因子相乘（营收 = 订单数 × 客单价） | LMDI-I，因子都为正时精确；有因子为零或负时用 Shapley | 每个因子的 `contribution`、`share`、`dominant_factor` |
| 比率（客单价、转化率、毛利率）按维度切 | Kitagawa 三项：结构（占比变了）、指标（各组自己的水平变了）、交叉 | `structure_total`、`rate_total`、`interaction_total`、`larger_effect` |

出处：美国经济分析局（BEA）的「对百分比变化的贡献」（加法）；B. W. Ang (2004, 2005)，*Energy Policy*，LMDI；
L. S. Shapley (1953) 与 J. W. Sun (1998)，*Energy Economics*；E. M. Kitagawa (1955)，*Journal of the American Statistical Association* 50(272)；
对称的两项形式见 P. Das Gupta (1978)。

只在一期出现的组，整个算作结构（它的占比出现了或消失了）；这样比率拆解仍然精确。

## 3. 二阶：比两次

| 问题 | 方法 | 输出 |
|---|---|---|
| 这一段的增速为什么和上一段不一样？ | 每组在两段里各自对增速的贡献，相减（比率指标：两段各做三项拆解，逐项相减） | `growth_w1`、`growth_w2`、`growth_change`，每组的 `change` |
| A 侧为什么比 B 侧涨得快？ | 增速差拆成结构差异（两侧卖的组合不一样）和表现差异（同一组在两侧长得不一样），再加只在一侧有的组 | `gap`、`mix_total`、`performance_total`、`unmatched_total`、`larger_effect` |

出处：BEA 的「对百分比变化的贡献」；Kitagawa (1955) 对称形式；偏离-份额分析里结构与竞争力的拆分（Dunn, 1960）。
三阶（在二阶结果上再比一次）第一版不计算。

## 4. 什么时候停

每切一刀，决策表 `stop.cut` 决定：往第一名下钻，还是因为变化分散而停下。
它的门槛是 `rules.yaml` 里有名字、有出处的参数，不是代码里的常数。它读的是噪音门（`scripts/aib/search.py`）：

- **集中度。** 第一名比其余各组同步变化多变的那部分，占全部变动的多少。金额类指标看这一组比其余各组合起来的增速多变了多少（留一法）。
  比率类指标拿这一组占变动的份额和它在基期的权重比。不管哪种，各组同比例变化时都是 0，二值维度也不会天然偏向单点。
- **和它自己的历史比。** 用过去同样各期，算这一部分的稳健 z 值。一周里只有三天出事的情况，另外算最强的连续 2～4 天，
  拿过去同一个统计量来比（Naus 1965，*JASA* 60(310)；Kulldorff 1997，*Communications in Statistics* 26(6)），取两者中更强的。
- **小组。** 比率指标的各组按经验贝叶斯收缩后的值排名次（Efron & Morris 1975），只有 3 单的组排不到第一。精确拆解本身不变。
- **选哪个维度。** 每一层给候选维度打分，分数 = 解释力 × Jensen-Shannon 意外度（Bhagwan 等 2014，Adtributor，USENIX NSDI）。
  用户确认过的优先级决定第一刀。最多 3 层。一条下钻路径从另一边反过来验证一次，算一个原因。

## 5. 其他拆法

| 问题 | 方法 | 输出 | 出处 |
|---|---|---|---|
| 多层指标树（毛利 = 营收 × 毛利率；营收 = 订单数 × 客单价） | 展开到叶子；对叶子做一次 LMDI（逐层和一次做结果一致，叶子加起来等于顶层）；比率叶子再按 Kitagawa 拆 | `tree.leaves`、`tree.ratio_splits` | Ang (2004) |
| 是卖得多、卖的组合变了，还是卖得贵？ | 量 = 总件数变化 × 基期结构 × 基期单价；结构 = 本期总件数 × 份额变化 × 基期单价；价格 = 本期件数 × 单价变化；只在一期有的算「新上」「下架」 | `pvm.volume_total`、`mix_total`、`price_total`、`new_total`、`gone_total` | 销量差异、结构差异、价格差异，Horngren、Datar 与 Rajan，《成本会计》 |
| 是新客多了，还是老客流失了？ | 按客户分：新客、回流、留下、多买、少买、流失；加起来等于总变化 | `growth_accounting.buckets`、`quick_ratio`、`gross_retention` | Hsu，Tribe Capital (2019)，[A Quantitative Approach to Product Market Fit](https://tribecap.co/essays/a-quantitative-approach-to-product-market-fit) |

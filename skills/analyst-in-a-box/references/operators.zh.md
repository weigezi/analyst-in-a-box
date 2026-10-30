# 方法

[English](operators.md)

每种方法都是公开发表过的方法，由脚本计算，并且都有测试保证各项之和正好等于总变化（`tests/test_ops.py`，含随机用例）。
代码在 `scripts/aib/ops/` 和 `scripts/aib/qualify.py`。

## 1. 拆之前先判断

| 问题 | 方法 | 出处 |
|---|---|---|
| 这一期对这个指标来说算不算异常？ | 这一期的变化和过去 N 期的变化比，算稳健 z 值（中位数和中位数绝对偏差，系数 1.4826），加上百分位 | Iglewicz & Hoaglin (1993)，*How to Detect and Handle Outliers* |
| 是不是大盘带着走？ | 把我们的变化拆成「基期 × 大盘增速」（跟着大盘走的）和剩下的（自己的） | 偏离-份额分析，Dunn (1960) |
| 两段的节假日对得上吗？ | 一个节日一个节日地数，各落在两个时间窗里几天 | 算术 |

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
它的门槛是 `rules.yaml` 里一个有名字、有出处的参数，不是代码里的常数。

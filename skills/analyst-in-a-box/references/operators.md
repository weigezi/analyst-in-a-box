# Methods

[中文](operators.zh.md)

Every method is a published one, computed by a script, and tested so that its terms sum exactly to the
total change (`tests/test_ops.py`, including random cases). Code: `scripts/aib/ops/`, `scripts/aib/qualify.py`.

## 1. Before breaking anything down

| Question | Method | Source |
|---|---|---|
| Is this period unusual for this metric? | robust z-score of this period's change against the last N periods' changes (median and MAD, scale 1.4826), plus percentile rank | Iglewicz & Hoaglin (1993), *How to Detect and Handle Outliers* |
| Did the market move us? | split our change into base × market growth ("moved with the market") and the rest ("our own") | shift-share analysis, Dunn (1960) |
| Do the two periods hold the same holidays? | count holiday days inside each window, holiday by holiday | arithmetic |

## 2. First order: one comparison

| Metric shape | Method | Output |
|---|---|---|
| summable (revenue, orders) cut by a dimension | additive: each segment's own change; shares sum to 100% | `top1_key`, `top1_abs_share`, `same_direction_share`, per-segment `delta`, `share` |
| a product of factors (revenue = orders × AOV) | LMDI-I, exact for positive factors; Shapley when a factor is zero or negative | per-factor `contribution`, `share`, `dominant_factor` |
| a ratio (AOV, conversion, margin) cut by a dimension | Kitagawa three-term: structure (mix moved), rate (each segment's own level moved), interaction | `structure_total`, `rate_total`, `interaction_total`, `larger_effect` |

Sources: U.S. Bureau of Economic Analysis, contributions to percent change (additive);
B. W. Ang (2004, 2005), *Energy Policy*, LMDI; L. S. Shapley (1953) and J. W. Sun (1998), *Energy Economics*;
E. M. Kitagawa (1955), *Journal of the American Statistical Association* 50(272); P. Das Gupta (1978) for the
symmetric two-term form.

A segment present in only one period counts entirely as structure (its weight appeared or vanished); this keeps
the ratio decomposition exact.

## 3. Second order: two comparisons

| Question | Method | Output |
|---|---|---|
| Why is this window's growth different from the previous window's? | each segment's contribution to growth in each window, subtracted (for ratios: three-term in each window, subtracted term by term) | `growth_w1`, `growth_w2`, `growth_change`, per-segment `change` |
| Why did side A grow faster than side B? | growth gap split into mix (the sides sell a different mix) and performance (the same segment grew differently), plus segments on one side only | `gap`, `mix_total`, `performance_total`, `unmatched_total`, `larger_effect` |

Sources: BEA contributions to percent change; Kitagawa (1955) symmetric form; the mix / competitive split of
shift-share analysis (Dunn, 1960). Third order (a second-order result compared again) is not computed in
version 1.

## 4. Stopping

After every cut the decision table `stop.cut` decides: drill into the top segment, or stop because the change
is spread out. Its threshold is a named param with a source in `rules.yaml`, never a constant in code.

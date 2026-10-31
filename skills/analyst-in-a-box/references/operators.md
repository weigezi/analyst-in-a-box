# Methods

[中文](operators.zh.md)

Every method is a published one, computed by a script, and tested so that its terms sum exactly to the
total change (`tests/test_ops.py`, including random cases). Code: `scripts/aib/ops/`, `scripts/aib/qualify.py`.

## 1. Before breaking anything down

| Question | Method | Source |
|---|---|---|
| Is this period unusual for this metric? | robust z-score of this period's change against the last N periods' changes (median and MAD, scale 1.4826), plus percentile rank | Iglewicz & Hoaglin (1993), *How to Detect and Handle Outliers* |
| Did the market move us? | expected change = base × (market growth + our usual gap to the market, median over the same past periods); the rest is "our own". An estimate; the plain split (base × market growth) is kept too | shift-share analysis, Dunn (1960); Esteban-Marquillas (1972) for taking the lasting difference out first |
| Do the two periods hold the same holidays? | count holiday days inside each window, holiday by holiday; past periods that do not line up are left out of the history above | arithmetic |
| Is the data itself sound? | calendar, declared key, daily row and value jumps against the same weekday's recent median, row ratio, leave-one-out single rows, renamed values; each check `block` or `warn` | `scripts/aib/quality.py`; thresholds in `rules.yaml` |
| A flat history (MAD = 0) | fall back on the mean absolute deviation × 1.253314; if that is zero too, say the history is flat | Iglewicz & Hoaglin (1993) |
| When did it start? | the main group's day-by-day gap to the paired base day; the single mean-shift change point by least squares, named only when the shift is ≥ 2 sd | Hinkley (1970), *Biometrika* 57(1) |

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
is spread out. Its thresholds are named params with a source in `rules.yaml`, never constants in code.
It reads the noise gate (`scripts/aib/search.py`):

- **Concentration.** The top group's share of all movement beyond moving in step with the others. Amounts use
  each group's change beyond the growth of all the other groups together (leave-one-out). Ratios compare the
  group's share of the movement with its base weight. Either way a uniform change scores 0, and a two-value
  dimension is not biased toward a single point.
- **Its own history.** A robust z of that residual against the same past periods. A three-day event inside a
  week is also scored as the strongest run of 2 to 4 days, judged against the same statistic in the past
  (Naus 1965, *JASA* 60(310); Kulldorff 1997, *Communications in Statistics* 26(6)). The stronger test counts.
- **Small groups.** Ratio groups are ranked by empirically-Bayes-shrunk rates (Efron & Morris 1975), so a
  group of three orders does not come first. The exact decomposition is unchanged.
- **Which dimension.** Each layer scores candidates by explanatory power × Jensen-Shannon surprise (Bhagwan et
  al. 2014, Adtributor, USENIX NSDI). A confirmed priority fixes the first cut. Depth is at most 3. A drill path
  is checked from the other side and counts as one cause.

## 5. Other breakdowns

| Question | Method | Output | Source |
|---|---|---|---|
| A metric tree several levels deep (profit = revenue × margin; revenue = orders × AOV) | expand to the leaves; LMDI over the leaves (consistent in aggregation, so leaves add up to the top); ratio leaves split by Kitagawa | `tree.leaves`, `tree.ratio_splits` | Ang (2004) |
| Did we sell more, a different mix, or charge more? | volume = ΔQ × base mix × base price; mix = Q₁ × Δshare × base price; price = q₁ × Δprice; items in one period only are "new" / "gone" | `pvm.volume_total`, `mix_total`, `price_total`, `new_total`, `gone_total` | sales-volume / sales-mix / price variances, Horngren, Datar & Rajan, *Cost Accounting* |
| New customers, or lost ones? | per customer: new, came back, kept, bought more, bought less, lost; they add up to the change | `growth_accounting.buckets`, `quick_ratio`, `gross_retention` | Hsu, Tribe Capital (2019), [A Quantitative Approach to Product Market Fit](https://tribecap.co/essays/a-quantitative-approach-to-product-market-fit) |

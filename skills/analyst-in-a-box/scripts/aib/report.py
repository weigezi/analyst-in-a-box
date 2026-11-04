"""Write the analysis for a person: conclusion first, then the breakdown, then why, then who acts.

Every number comes from the run state; nothing here does arithmetic beyond formatting.
Charts use the Okabe-Ito colour-blind-safe palette (M. Okabe & K. Ito, 2008, "Color Universal Design").
"""

from __future__ import annotations

import math
from pathlib import Path

from .defaults import param
from . import quality
from .explain import World, entry_text
from .workspace import label

T = {
    "zh": {
        "conclusion": "结论", "unusual": "算不算异常", "breakdown": "拆解", "why": "为什么", "who": "谁该做什么",
        "confirm": "待你确认", "appendix": "附：这次用了什么", "segment": "分组", "base": "基期", "cur": "本期",
        "delta": "变化", "share": "占变化", "structure": "结构", "rate": "指标", "interaction": "交叉",
        "mix": "结构差异", "performance": "表现差异", "unmatched": "只在一边有", "factor": "因子",
        "contribution": "贡献", "vs": "对比", "main_from": "主要来自", "of_change": "占变化的",
        "larger_structure": "结构主导：变化主要来自各组占比变了，而不是各组自己的水平变了。",
        "larger_rate": "指标主导：变化主要来自各组自己的水平变了，而不是占比变了。",
        "larger_mix": "结构差异主导：两边卖的组合不一样。", "larger_performance": "表现差异主导：同一组在两边长得不一样。",
        "spread": "这一刀切下去变化分散在各组，没有单点，停在这一层。", "drill": "单点集中，往下钻：", "single": "单点集中：",
        "qualify_scope": "这一节看的是整体{m}，不是两边的差。",
        "unusual_low": "和自己过去 {n} 期比，这一期明显偏低（稳健 z 值 {z}，低于门槛 {t}）。",
        "unusual_high": "和自己过去 {n} 期比，这一期明显偏高（稳健 z 值 {z}，高于门槛 {t}）。",
        "within": "和自己过去 {n} 期比，这一期在通常范围内（稳健 z 值 {z}）。",
        "no_history": "历史太短，判断不了这一期算不算异常。",
        "market_own": "同期大盘 {mg}，按大盘应变化 {mp}，实际变化 {d}；自己的部分 {op}，占 {os}。下滑是自己的问题，往内部拆。",
        "market_market": "同期大盘 {mg}，按大盘应变化 {mp}，实际变化 {d}；大部分是跟着大盘走的（占 {ms}）。",
        "calendar": "注意：两期的节假日对不齐（{items}），同比会被日历放大或压低。",
        "mechanism": "机制", "event": "事件", "hypothesis": "推测", "supported": "推测，已过三道检查",
        "timing_only": "推测，只有时间对得上，未证实", "not_supported": "推测，时间都对不上",
        "timing": "时间", "slice": "影响的那一块", "size": "量级", "evidence": "证据",
        "overlap": "重叠 {n} 天", "slice_text": "占变化 {v}（门槛 {t}）", "size_text": "事件那几天占这一块变化的 {v}（门槛 {t}）",
        "refute": "推翻条件：剔除事件那几天后这一块仍然同样下滑，这个推测就不成立。",
        "gap": "数据上看到「{seg}」的变化，原因待你确认。直接告诉我原因，我会记下来，下次不再问。",
        "status_confirmed": "已确认", "status_proposed": "待确认", "source": "出处", "refuted_by": "什么数据出现就推翻它", "owner": "负责人",
        "no_action": "还没有登记可做的动作。",
        "no_owner": "变动落在这里：{items}。这些地方还没有登记负责人，也没有登记动作。直接告诉我谁负责，我会记下来，下次不再问。", "coverage": "需要业务解释的地方：{e}/{n} 处有记录可引（覆盖率 {p}）。",
        "definitions": "口径版本", "decisions": "命中的规则", "checks": "交付前自检", "pass": "通过", "fail": "未通过",
        "blocked": "⚠️ 交付前自检没通过。下面没有一个数可以当作发现，请先处理这些问题：", "you_may_not_know": "你可能还不知道",
        "blocked_head": "**还不是发现。** 下面的数是按现有数据算出来的，没通过的自检处理好之前不下结论。",
        "blocked_computed": "这些数是按现有数据算出来的，在没通过的自检处理好之前，不算发现。",
        "blocked_why": "不点名原因：交付前自检没通过，这里的内容还不是发现。",
        "blocked_who": "不点名负责人：交付前自检没通过，这里的内容还不是发现。",
        "no_breakdown": "这次没有算出拆解{reason}。", "no_breakdown_why": "没有算出拆解，所以没有点名原因。",
        "no_breakdown_dims": "：这个指标在这个工作区里没有可以切的维度", "flat_head": "**{m}**{p}在这个精度下看不出变化（基期 {b}，本期 {c}）。",
        "gap_a_b": "{a} 同比 {ga}，{b} 同比 {gb}，差 {gap}。", "horizontal": "按公式拆",
        "rate_change": "从 {b} 到 {c}（{d}）。", "amount_change": "比基期 {g}（{b} → {c}）。",
        "main_share": "主要来自 **{seg}**：{v}，占全部变化的 {p}。",
        "main_over": "主要来自 **{seg}**：{v}，单它一项就比总变化（{total}）还大，其他各组合计 {rest}，抵掉了一部分。",
        "main_abs": "主要来自 **{seg}**：{v}，占全部变动幅度的 {p}。",
        "market_own2": "同期大盘 {mg}，照大盘走本该 {mp}；实际 {d}。差出来的 {op} 是自己的，往内部拆。",
        "market_market2": "同期大盘 {mg}，照大盘走本该 {mp}；实际 {d}，大部分是跟着大盘走的。",
        "size_text2": "事件那几天的变化 {e}，是这一块全部变化 {all} 的 {v}（门槛 {t}）",
        "size_note": "超过 100% 说明其余几天这一块在涨。",
        "confirm_external": "「{what}」目前是推测（{st}）。你确认后我会把它标成已确认。",
        "confirm_proposed": "「{what}」还没确认。",
        "suspect": "**数据存疑**：{items}。数据核实之前，不把任何原因当成已解释。",
        "note_blank_amounts": "{column} 有空白：本期 {blank:,} / {rows:,} 行（{share}）为空，基期 {base_blank:,} / {base_rows:,} 行（{base_share}）为空，空白的行没有计入金额",
        "note_zero_amounts": "{column} 为 0 的行：本期 {zero:,} / {rows:,} 行（{share}）；这些行仍算作一单，会拉低按单计的数",
        "note_looks_like_rate": "{column} 的所有值都在 0 到 1 之间（{min} 到 {max}，{n:,} 行），像是比率而不是金额；比率加总没有意义，请确认它真的是可以相加的量",
        "note_repeats_per_entity": "{column} 对同一个 {entity} 在不同日期上几乎总是同一个值（{entities:,} 个里有 {pct} 如此），像是存量或价目而不是每次发生的金额；加总会把它每期重复算一次，请确认",
        "data_note": "**数据说明**：{items}。以上不阻止出报告，但会影响怎么读这些数。",
        "quality_warn": "**数据提醒**：{items}。这些不影响下面的数怎么算，结论照常给出，但值得核一下。",
        "quality_warn_blocked": "**数据提醒**：{items}。这一项单独不会拦住报告，要和上面没通过的自检一起看。",
        "data_note_blocked": "**数据说明**：{items}。这些单独不会拦住报告；没通过的自检处理好之后，它们会影响怎么读这些数。",
        "closed_inferred": "{days}按不营业处理，这是从数据推出来的假设，还没人确认（{note}）。这几天没有数据不算缺数据。",
        "closed_evidence": "数据里 {e}/{w} 个{d}没有任何记录", "closed_no_evidence": "依据见工作区记录",
        "q_calendar_complete": "有些该有数据的日子一条记录都没有（{v}）",
        "q_key_unique": "订单编号有重复（{v}）",
        "q_row_ratio": "一期的记录比另一期少得多，两期没法比（{v}）",
        "q_monthly": "{src} 的数据按月记（每条记录的日期都是当月 1 号），而这次的时间窗不是整月，所以窗里没有记录；请改用整月的窗口",
        "q_daily_volume_steady": "有几天的记录条数和平常差太多，像是重复导入或只导了一部分（{v}）",
        "q_daily_value_steady": "有几天的金额是平常的好几倍或几分之一，像是单位或口径变了（{v}）",
        "q_no_single_row_dominates": "一条记录就占了变化的一大块（{v}）",
        "q_dimension_values_stable": "有一个值消失、同时冒出一个差不多大的新值，像是改了名（{v}）",
        "fit_change": "这条记录在两期的情况不同，能解释这次的变化。",
        "fit_why_mix_matters": "这条记录两期都成立：它说明了占比变化为什么会拉动这个数，但解释不了占比为什么变了。",
        "fit_cannot_explain_change": "这条记录两期都成立，解释不了这次的变化。",
        "fit_term_mismatch": "这条记录说它影响的是{acts}，但这一块主要是{term}在变，对不上。",
        "term_structure": "占比", "term_rate": "各组自己的水平",
        "gap_mix": "数据上看到「{seg}」的变化主要是占比变了，已有记录解释不了占比为什么变。你知道这段时间发生了什么吗？",
        "data_suspect_slot": "数据存疑，先不下结论。",
        "possible_cause": "可能的原因", "from_document": "来自文档，待确认：{ref}", "from_system_record": "来自系统记录，待确认：{ref}",
        "quote_line": "原文：「{q}」", "pending_line": "这条还没人确认，所以不算已解释。你确认后我会把它标成已确认。",
        "drill_quiet": "整体在通常范围内，但这一组的变化远超它自己过去的波动，往下看：",
        "stop_quiet": "整体在通常范围内，各组也没有明显超出自己的波动，停在这一层。",
        "stop_small": "第一名这一组样本太少，不点名（{n} 个 {unit}，门槛 {min}）。",
        "no_owner_quiet": "{lead}变动最大的是：{items}。这些地方还没有登记负责人，也没有登记动作。直接告诉我谁负责，我会记下来，下次不再问。",
        "stop_first_quiet": "整体在通常范围内，所以只切了第一刀（{dim}）就停了。", "stop_first_other": "只切了第一刀（{dim}），没有往任何一组下钻。",
        "dom_big_quiet": "「{seg}」占全部变动的 {share}，超过你设的单点门槛 {need}；不往下钻：整体在通常范围内{swing}。",
        "dom_big_small": "「{seg}」占全部变动的 {share}，超过你设的单点门槛 {need}，但样本太少，不点名，不往下钻。",
        "dom_big_other": "「{seg}」占全部变动的 {share}，超过你设的单点门槛 {need}，但不往下钻：{why}。",
        "swing_within": "，这一组也没有超出它自己过去的波动（z 值 {z}，要到 {zmin}）",
        "swing_no_history": "，这一组没有历史，没法和它自己的波动比",
        "why_no_history": "它没有历史，没法和它自己的波动比", "why_other": "它没有通过单点的全部检验",
        "why_in_step": "它基本是跟着其余各组一起动的（超出其余各组的部分占全部变动的 {ex}，要到 {need}）",
        "why_within_swing": "它的变化在它自己过去的波动之内（z 值 {z}，要到 {zmin}）",
        "stop_not_single": "不是单点：最大的一组没有通过单点的全部检验（占比、超出其余各组的部分、相对自己波动的大小），分析停在这一层。",
        "ro_cut_big": "{dim}这一刀（不往下钻：最大的一组占全部变动的 {share}，但没有通过单点的全部检验）",
        "cross_check": "反过来验证：", "cross_ok": "从另一边切也指向同一组，两层说的是同一个原因。",
        "cross_no": "从另一边切指向的不是同一组，两层可能是两件事。",
        "head_amount": "**{m}**{p}比基期{dir} {a}（{g}，{b} → {c}）。",
        "head_rate": "**{m}**{p}从 {b} {dir}到 {c}（{d}）。",
        "up": "多了", "down": "少了", "rise": "升", "fall": "降",
        "main_amount": "主因是 **{seg}**：{v}，它自己比基期 {g}。",
        "main_rate": "主因是 **{seg}**：拉动 {v}。",
        "rest_line": "去掉这一块，其余部分 {r}，平时是 {u}，{judge}。",
        "rest_same": "和平时差不多", "rest_better": "比平时好", "rest_worse": "比平时差",
        "onset_line": "从 {d} 开始（逐日对比找到的变化起点）。",
        "onset_event": "和「{e}」的开始日期{gap}。", "same_day": "是同一天", "days_after": "差 {n} 天",
        "recent_line": "最近几周（{whole}整体 / {seg}）：{items}。", "weight_of": "「{seg}」的占比",
        "secondary": "次因是 **{seg}**：{v}。",
        "offsets": "反向抵消：{items}，抵掉了一部分。",
        "ruled_out": "排除：{items}。",
        "ro_market": "大盘（按这家店相对大盘的常态差距估计，跟着大盘本该 {v}，方向相反或量小）",
        "ro_record": "「{what}」（两期都成立，解释不了这次的变化）",
        "ro_record_mix": "「{what}」（只说明占比变化为什么会拉动这个数，没说明占比为什么变）",
        "ro_event": "「{what}」（外部事件，没过三道检查）",
        "ro_cut": "{dim}这一刀（各组变化分散，没有单独突出的）",
        "ro_quiet": "整体在通常范围内，没有一组明显超出自己的波动",
        "dominance": "**主导判断**：{t}",
        "dom_concentrated": "集中在「{seg}」：它多变的部分占全部变动的 {p}。",
        "dom_spread": "分散：没有一组明显超出其余各组的同步变化。",
        "range_line": "过去 {n} 期里，中间一半的变化落在 {lo} 到 {hi} 之间；低于 {below} 或高于 {above} 才判为异常（门槛线，不是正常范围）。",
        "range_line_high_only": "过去 {n} 期里，中间一半的变化落在 {lo} 到 {hi} 之间；高于 {above} 才判为异常地高（门槛线，不是正常范围）。这个数起伏太大，往下的门槛线已经低于 −100%，而降幅最多 −100%，所以下跌这边没有异常线。",
        "left_out": "有 {n} 期因为两边节假日对不齐，没算进比较的历史：{items}。",
        "market_usual": "同期大盘 {mg}。这家店过去通常比大盘 {gap}，按这个常态估计本期应变化 {ep}；实际 {d}，差出来的 {op} 是自己的。这是估计，不是精确账目（只按大盘算的话，自己的部分是 {plain}）。",
        "flat_history": "过去 {n} 期的变化一模一样（波动为零），没法用波动大小判断这一期算不算异常。",
        "short_history": "历史太短（{n} 期），判断不了这一期算不算异常。",
        "share_abs": "占变动幅度", "bar_note": "括号内为占变动幅度", "w_base": "基期", "w_cur": "本期", "w_others": "其他 {n} 组",
        "daily_title": "逐日对比", "waterfall_title": "从基期到本期",
        "pvm": "量、结构、价格", "pvm_term": "部分", "pvm_volume": "卖得多少（量）", "pvm_mix": "卖了什么（结构）",
        "pvm_price": "卖多少钱（价格）", "pvm_new": "新上的", "pvm_gone": "下架的",
        "pvm_line": "{lead}为主：总件数 {q}。价格变化最大的是「{seg}」：{v}（单价 {p0} → {p1}）。",
        "ga": "按客户拆", "ga_bucket": "客户", "ga_customers": "人数", "ga_new": "新客", "ga_resurrected": "回流",
        "ga_expansion": "老客多买", "ga_contraction": "老客少买", "ga_churned": "流失", "ga_retained": "留下的部分",
        "ga_line": "增减比（新增÷流失）{q}，留住了基期的 {r}。没有客户编号的订单变化 {o}，不在上表里。",
        "tree": "按公式拆到底", "notchecked": "这份报告没有检查什么",
        "nc_used": "用到的：{items}。", "nc_cut": "切的维度：{cut}。", "nc_not_cut": "能切但这次没切：{rest}。", "nc_no_cut": "这次没有切任何维度。",
        "nc_as_is": "数字就是上面这些列原样加出来的，所以算毛额，除非列本身或下面的剔除规则已经把退款和退货排除在外。数字只来自上面列出的表。",
        "nc_removed": "计数前剔除的行：{items}。",
        "nc_removed_item": "`{source}` 里 `{column}` 是 {values} 的行（本期 {c:,}/{cr:,} 行，基期 {b:,}/{br:,} 行）",
        "nc_no_rule": "没有任何规则剔除已取消或已冲销的行，这类行如果存在，会算进每一个数里。",
        "nc_copies_once": "完全相同的行只算一条。", "nc_copies_every_row": "完全相同的行各算一条记录。",
        "nc_copies_unknown": "你说过不知道完全相同的行是不是第二条真实记录，所以每一行都算。",
        "nc_copies_none": "没有记录关于完全相同的行的回答，所以每一行都算。",
        "nc_blank": "切的列里的空白值：{items}。",
        "nc_blank_item": "`{column}` 本期 {b:,}/{n:,} 行（{share}）为空，基期 {bb:,}/{bn:,} 行（{bshare}）为空",
        "nc_no_blank": "切的列（{dims}）里没有空白值。",
        "nc_no_event": "没有核对任何外部事件（活动、节假日、调价）和这次变化的关系。",
        "nc_events": "和这次变化核对过的外部事件：{ids}（看时间、范围、量级，见“为什么”）。",
        "nc_no_market": "没有和大盘或同行的数比较。",
        "nc_checks": "{ran} 项交付前自检跑过，{failed}。数据说明 {notes} 条。", "nc_none_failed": "全部通过", "nc_failed": "没通过的：{names}",
        "nc_dq_warned": "数据质量检查里有提醒：{names}。",
        "agg_sum": "`{source}` 里 `{column}` 的合计", "agg_count": "`{source}` 的行数",
        "agg_count_distinct": "`{source}` 里 `{column}` 的不同取值个数", "agg_mean": "`{source}` 里 `{column}` 的平均",
        "agg_min": "`{source}` 里 `{column}` 的最小值", "agg_max": "`{source}` 里 `{column}` 的最大值", "dated_by": "按 `{date}` 归期", "tree_split": "{m}按{d}拆：占比变化 {s}，各组自己的水平 {r}，{lead}。",
        "lead_structure": "占比主导", "lead_rate": "各组水平主导", "lead_tie": "两者相当",
    },
    "en": {
        "conclusion": "Conclusion", "unusual": "Is it unusual?", "breakdown": "Breakdown", "why": "Why", "who": "Who should act",
        "confirm": "Waiting for you", "appendix": "Appendix: what this run used", "segment": "Segment", "base": "Base",
        "cur": "Current", "delta": "Change", "share": "Share of change", "structure": "Structure", "rate": "Rate",
        "interaction": "Interaction", "mix": "Mix", "performance": "Performance", "unmatched": "One side only",
        "factor": "Factor", "contribution": "Contribution", "vs": "vs", "main_from": "Mainly from", "of_change": "of the change",
        "larger_structure": "Structure-led: the change comes mainly from the mix of groups, not from each group's own level.",
        "larger_rate": "Rate-led: the change comes mainly from each group's own level, not from the mix.",
        "larger_mix": "Mix-led: the two sides sell a different mix.", "larger_performance": "Performance-led: the same group grew differently on the two sides.",
        "spread": "This cut spreads the change across groups; no single point, so the analysis stops here.",
        "drill": "Single point; drilling into: ", "single": "Single point: ",
        "qualify_scope": "This section is about {m} as a whole, not the gap between the two sides.",
        "unusual_low": "Against its own last {n} periods this one is clearly low (robust z {z}, below the threshold {t}).",
        "unusual_high": "Against its own last {n} periods this one is clearly high (robust z {z}, above the threshold {t}).",
        "within": "Against its own last {n} periods this one is within the usual range (robust z {z}).",
        "no_history": "Not enough history to say whether this period is unusual.",
        "market_own": "The market moved {mg}; following the market we would have changed by {mp}, we actually changed by {d}. Our own part is {op} ({os}). It is our own problem; break it down internally.",
        "market_market": "The market moved {mg}; following the market we would have changed by {mp}, we actually changed by {d}. Most of it moved with the market ({ms}).",
        "calendar": "Note: the two periods hold different holidays ({items}); year-on-year figures are distorted by the calendar.",
        "mechanism": "Mechanism", "event": "Event", "hypothesis": "Hypothesis", "supported": "Hypothesis, passed all three checks",
        "timing_only": "Hypothesis, timing matches only, not proven", "not_supported": "Hypothesis, timing does not match",
        "timing": "Timing", "slice": "Affected slice", "size": "Size", "evidence": "Evidence",
        "overlap": "{n} days overlap", "slice_text": "{v} of the change (threshold {t})", "size_text": "{v} of the slice's change falls on the event's days (threshold {t})",
        "refute": "Refuted if, without the event's days, this slice still falls just as much.",
        "gap": "The data shows a change in \"{seg}\"; the reason is waiting for you. Tell me the reason and I will record it and not ask again.",
        "status_confirmed": "confirmed", "status_proposed": "to confirm", "source": "source", "refuted_by": "what data would refute it", "owner": "owner",
        "no_action": "No actions recorded yet.",
        "no_owner": "The movement sits here: {items}. No owner and no action is recorded for these yet. Tell me who owns it and I will record it and not ask again.", "coverage": "Places that need a business explanation: {e} of {n} can cite a record (coverage {p}).",
        "definitions": "Definitions version", "decisions": "Rules that fired", "checks": "Pre-delivery checks", "pass": "pass", "fail": "FAIL",
        "blocked": "⚠️ Pre-delivery checks failed. No number below is a finding yet; fix what failed first:", "you_may_not_know": "You may not know",
        "blocked_head": "**Not a finding yet.** The figures below are computed from the data as loaded; nothing is concluded until the failed check is fixed.",
        "blocked_computed": "These figures are computed from the data as loaded. They are not findings while the failed check stands.",
        "blocked_why": "No cause is named: the pre-delivery check failed, so nothing here is a finding yet.",
        "blocked_who": "Nobody is named: the pre-delivery check failed, so nothing here is a finding yet.",
        "no_breakdown": "No breakdown was computed{reason}.", "no_breakdown_why": "No breakdown was computed, so no cause is named.",
        "no_breakdown_dims": ": this metric has no dimension to cut by in this workspace", "flat_head": "**{m}**{p} showed no visible change at this precision (base: {b}, current: {c}).",
        "gap_a_b": "{a} {ga} year on year, {b} {gb}; a gap of {gap}.", "horizontal": "By formula",
        "rate_change": " moved from {b} to {c} ({d}).", "amount_change": " {g} vs base ({b} → {c}).",
        "main_share": "Mainly from **{seg}**: {v}, {p} of the total change.",
        "main_over": "Mainly from **{seg}**: {v}. This one item is larger than the total change ({total}); the other groups added {rest} and offset part of it.",
        "main_abs": "Mainly from **{seg}**: {v}, {p} of all movement.",
        "market_own2": "The market moved {mg}; following it we would have changed by {mp}. We actually changed by {d}. The difference, {op}, is our own; break it down internally.",
        "market_market2": "The market moved {mg}; following it we would have changed by {mp}. We actually changed by {d}; most of it moved with the market.",
        "size_text2": "the change on the event's days, {e}, is {v} of the slice's whole change {all} (threshold {t})",
        "size_note": "above 100% means the slice grew on the other days.",
        "confirm_external": "\"{what}\" is a hypothesis ({st}). Confirm it and I will mark it confirmed.",
        "confirm_proposed": "\"{what}\" is not confirmed yet.",
        "suspect": "**Data in doubt**: {items}. No cause counts as explained until the data is checked.",
        "note_blank_amounts": "{column} has blank cells: {blank:,} of {rows:,} rows ({share}) in the current period and {base_blank:,} of {base_rows:,} ({base_share}) in the base are blank; blank rows add nothing to the amount",
        "note_zero_amounts": "{column} is exactly 0 on {zero:,} of {rows:,} rows ({share}) in the current period; these rows still count as an order and pull per-order figures down",
        "note_looks_like_rate": "every value of {column} is between 0 and 1 ({min} to {max}, {n:,} rows), which looks like a rate, not an amount; rates cannot be added up, so confirm it is a quantity that adds",
        "note_repeats_per_entity": "{column} carries the same value for the same {entity} on different dates for {pct} of {entities:,} of them, which looks like a level (a balance, a price list) rather than an amount that happens each time; summing counts it again every period, so confirm",
        "data_note": "**Data note**: {items}. This does not stop the report, but it changes how to read these numbers.",
        "quality_warn": "**Data note**: {items}. This does not change how the numbers below are computed and the conclusions stand, but it is worth a look.",
        "quality_warn_blocked": "**Data note**: {items}. This alone would not stop a report; read it together with the failed check above.",
        "data_note_blocked": "**Data note**: {items}. These alone would not stop a report; they change how to read these numbers once the failed check is fixed.",
        "closed_inferred": "{days} treated as closed: an assumption drawn from the data, not yet confirmed by anyone ({note}). Missing rows on these days are not counted as missing data.",
        "closed_evidence": "no rows on {e} of the {w} {d}s in the data", "closed_no_evidence": "the evidence is in the workspace record",
        "q_calendar_complete": "some days that should have data have no rows at all ({v})",
        "q_key_unique": "order ids repeat ({v})",
        "q_row_ratio": "one period has almost no rows compared with the other, so the two cannot be compared ({v})",
        "q_monthly": "{src} is monthly data (every record is dated the 1st of a month) and this window is not whole months, so it holds no records; use a window of whole months",
        "q_daily_volume_steady": "some days have far more or far fewer rows than usual, as if loaded twice or only partly ({v})",
        "q_daily_value_steady": "some days' totals are several times (or a fraction of) the usual, as if a unit or definition changed ({v})",
        "q_no_single_row_dominates": "one row carries a large part of the change ({v})",
        "q_dimension_values_stable": "one value disappeared while a new one of similar size appeared, as if renamed ({v})",
        "fit_change": "This record differs between the two periods, so it can explain this change.",
        "fit_why_mix_matters": "This record holds in both periods: it says why a shift in mix moves the number, not why the mix shifted.",
        "fit_cannot_explain_change": "This record holds in both periods; it cannot explain this change.",
        "fit_term_mismatch": "This record says it acts on {acts}, but what moved here is {term}; they do not match.",
        "term_structure": "the mix", "term_rate": "each group's own level",
        "gap_mix": "The data shows \"{seg}\" moved mainly through a shift in mix; no record explains why the mix shifted. Do you know what happened in this period?",
        "data_suspect_slot": "Data in doubt; no conclusion yet.",
        "possible_cause": "Possible cause", "from_document": "from a document, to confirm: {ref}",
        "from_system_record": "from a system record, to confirm: {ref}", "quote_line": "The document says: \"{q}\"",
        "pending_line": "Nobody has confirmed this yet, so it does not count as explained. Confirm it and I will mark it confirmed.",
        "drill_quiet": "The whole number is within its usual range, but this group moved far beyond its own past swings; looking inside: ",
        "stop_quiet": "The whole number is within its usual range and no group stands out from its own swings; stopping here.",
        "stop_small": "The top group is too small to name ({n} {unit}, threshold {min}).",
        "no_owner_quiet": "{lead} Its largest movers: {items}. No owner and no action is recorded for these yet. Tell me who owns it and I will record it and not ask again.",
        "stop_first_quiet": "The total is within its usual range, so the run stopped at the first cut ({dim}).",
        "stop_first_other": "The run stopped at the first cut ({dim}) without drilling into a group.",
        "dom_big_quiet": "\"{seg}\" carries {share} of all movement, above your single-point threshold of {need}. It is not drilled: the total is within its usual range{swing}.",
        "dom_big_small": "\"{seg}\" carries {share} of all movement, above your single-point threshold of {need}, but it is too small to name, so it is not drilled.",
        "dom_big_other": "\"{seg}\" carries {share} of all movement, above your single-point threshold of {need}, but it is not drilled: {why}.",
        "swing_within": " and this group did not move beyond its own usual swings (z {z}, needs {zmin})",
        "swing_no_history": " and this group has no history to judge its own swings against",
        "why_no_history": "it has no history to judge its own swings against", "why_other": "it did not pass every test for a single point",
        "why_in_step": "it moved mostly in step with the other groups (what it moved beyond them is {ex} of all movement, needs {need})",
        "why_within_swing": "its change is within its own usual swings (z {z}, needs {zmin})",
        "stop_not_single": "Not a single point: the largest group did not pass every test (share, excess over the others, size against its own swings), so the analysis stops here.",
        "ro_cut_big": "the cut by {dim} (not drilled: the largest group carries {share} of all movement, but did not pass every test for a single point)",
        "cross_check": "Checked from the other side: ", "cross_ok": "cutting the other way points to the same group, so the two layers describe one cause.",
        "cross_no": "cutting the other way points elsewhere, so the two layers may be two separate things.",
        "head_amount": "**{m}**{p} was {dir} {a} on the base ({g}, {b} → {c}).",
        "head_rate": "**{m}**{p} {dir} from {b} to {c} ({d}).",
        "up": "up", "down": "down", "rise": "rose", "fall": "fell",
        "main_amount": "The main cause is **{seg}**: {v}; on its own it changed {g} on the base.",
        "main_rate": "The main cause is **{seg}**: it moved the number by {v}.",
        "rest_line": "Without it, the rest changed {r}; it usually changes {u}, so it is {judge}.",
        "rest_same": "about as usual", "rest_better": "better than usual", "rest_worse": "worse than usual",
        "onset_line": "It started on {d} (the change point found day by day).",
        "onset_event": "That {gap} the start of \"{e}\".", "same_day": "is the same day as", "days_after": "is {n} days from",
        "recent_line": "The last weeks ({whole} as a whole / {seg}): {items}.", "weight_of": "the share of \"{seg}\"",
        "secondary": "The second cause is **{seg}**: {v}.",
        "offsets": "Offsetting: {items}, which offset part of it.",
        "ruled_out": "Ruled out: {items}.",
        "ro_market": "the market (estimated from this business's usual gap to it, following it would have meant {v}: the other way, or small)",
        "ro_record": "\"{what}\" (true in both periods; it cannot explain this change)",
        "ro_record_mix": "\"{what}\" (it says why a shift in mix moves the number, not why the mix shifted)",
        "ro_event": "\"{what}\" (outside event that did not pass the three checks)",
        "ro_cut": "the cut by {dim} (the change is spread; no group stands out)",
        "ro_quiet": "the whole number is within its usual range, and no group stands out from its own swings",
        "dominance": "**What led**: {t}",
        "dom_concentrated": "concentrated in \"{seg}\": what it moved beyond the others is {p} of all movement.",
        "dom_spread": "spread: no group moved clearly beyond the others.",
        "range_line": "Over the last {n} periods the middle half of changes fell between {lo} and {hi}; below {below} or above {above} counts as unusual (threshold lines, not the usual range).",
        "range_line_high_only": "Over the last {n} periods the middle half of changes fell between {lo} and {hi}; above {above} counts as unusually high (threshold line, not the usual range). This number swings so much that the lower threshold would sit below −100%, and a fall cannot be larger than −100%, so there is no unusual line on the downside.",
        "left_out": "{n} periods were left out of the history because the two sides held different holidays: {items}.",
        "market_usual": "The market moved {mg}. This business usually runs {gap} against the market; on that basis it should have changed by {ep}. It changed by {d}, so {op} is its own. This is an estimate, not an exact account (counting only the market, its own part would be {plain}).",
        "flat_history": "The last {n} periods all changed by exactly the same amount (flat history), so their spread cannot say whether this one is unusual.",
        "short_history": "Not enough history ({n} periods) to say whether this period is unusual.",
        "share_abs": "Share of all movement", "bar_note": "brackets: share of all movement", "w_base": "Base", "w_cur": "Current", "w_others": "{n} others",
        "daily_title": "Day by day", "waterfall_title": "From base to current",
        "pvm": "Volume, mix and price", "pvm_term": "Part", "pvm_volume": "Selling more or less (volume)",
        "pvm_mix": "Selling a different mix", "pvm_price": "Charging differently (price)", "pvm_new": "New items", "pvm_gone": "Items gone",
        "pvm_line": "Mostly {lead}: total quantity {q}. The largest price change is \"{seg}\": {v} (unit price {p0} → {p1}).",
        "ga": "By customer", "ga_bucket": "Customers", "ga_customers": "Count", "ga_new": "New", "ga_resurrected": "Came back",
        "ga_expansion": "Bought more", "ga_contraction": "Bought less", "ga_churned": "Lost", "ga_retained": "Kept",
        "ga_line": "Quick ratio (gains ÷ losses) {q}; {r} of the base was kept. Orders without a customer id changed by {o} and are not in the table.",
        "tree": "Whole formula tree", "notchecked": "What this report did not check",
        "nc_used": "Used: {items}.", "nc_cut": "Cut by: {cut}.", "nc_not_cut": "Could be cut by but was not: {rest}.", "nc_no_cut": "No cut was made.",
        "nc_as_is": "The number is those columns taken as they are, so it is gross unless the column itself or a removal rule below already leaves refunds and returns out. The numbers come only from the tables listed above.",
        "nc_removed": "Removed before counting: {items}.",
        "nc_removed_item": "rows of `{source}` where `{column}` is {values} ({c:,} of {cr:,} rows in the current period, {b:,} of {br:,} in the base)",
        "nc_no_rule": "No rule removes cancelled or reversed rows, so any such rows are counted in every number.",
        "nc_copies_once": "Exact copies of a row are counted once.", "nc_copies_every_row": "Exact copies of a row are counted as separate records.",
        "nc_copies_unknown": "You said you do not know whether an exact copy of a row is a second real record, so every row is counted.",
        "nc_copies_none": "No answer is recorded about exact copies of a row, so every row is counted.",
        "nc_blank": "Blank values in the cut columns: {items}.",
        "nc_blank_item": "`{column}` is blank on {b:,} of {n:,} rows ({share}) in the current period and {bb:,} of {bn:,} ({bshare}) in the base",
        "nc_no_blank": "No blank values in the cut columns ({dims}).",
        "nc_no_event": "No outside event (a campaign, a holiday, a price change) was checked against this change.",
        "nc_events": "Outside events checked against this change: {ids} (timing, slice and size; see Why).",
        "nc_no_market": "No market or peer figures were compared.",
        "nc_checks": "{ran} pre-delivery checks ran; {failed}. Data notes raised: {notes}.", "nc_none_failed": "none failed", "nc_failed": "failed: {names}",
        "nc_dq_warned": "Data-quality checks that raised a warning: {names}.",
        "agg_sum": "the sum of `{column}` in `{source}`", "agg_count": "the number of rows in `{source}`",
        "agg_count_distinct": "the number of distinct `{column}` in `{source}`", "agg_mean": "the mean of `{column}` in `{source}`",
        "agg_min": "the smallest `{column}` in `{source}`", "agg_max": "the largest `{column}` in `{source}`", "dated_by": "dated by `{date}`", "tree_split": "{m}, split by {d}: mix {s}, each group's own level {r}; {lead}.",
        "lead_structure": "mix led", "lead_rate": "own level led", "lead_tie": "neither led",
    },
}


SOURCE_KINDS = {
    "zh": {"user": "用户原话", "document": "文档", "data": "数据推出", "system_record": "系统记录",
           "general_knowledge": "通用常识", "demo_setting": "演示设定", "formula": "公式"},
    "en": {"user": "user's words", "document": "document", "data": "inferred from data", "system_record": "system record",
           "general_knowledge": "general knowledge", "demo_setting": "demo setting", "formula": "formula"},
}
WEEKDAY_NAMES = {"zh": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
                 "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
PUNCT = {"zh": {"colon": "：", "comma": "，", "semi": "；", "open": "（", "close": "）", "stop": "。"},
         "en": {"colon": ": ", "comma": ", ", "semi": "; ", "open": " (", "close": ")", "stop": "."}}


MINUS = "\u2212"  # a real minus sign, not a hyphen, for every negative number shown to a person


def _m(s: str) -> str:
    return MINUS + s[1:] if s.startswith("-") else s


def fmt(v, unit=None, signed=False):
    if v is None:
        return "—"
    if unit == "ratio":
        return _m(f"{v:+.2%}" if signed else f"{v:.2%}")
    if unit == "count":
        return _m(f"{v:+,.0f}" if signed else f"{v:,.0f}")
    if abs(v) >= 1000:
        return _m(f"{v:+,.0f}" if signed else f"{v:,.0f}")
    return _m(f"{v:+,.2f}" if signed else f"{v:,.2f}")


def pct(v, signed=True):
    return "—" if v is None else _m(f"{v:+.1%}" if signed else f"{v:.1%}")


def pp(v):
    return "—" if v is None else _m(f"{v * 100:+.1f}pp")


BLANK = {"en": "(blank)", "zh": "(空)"}


def is_blank(key) -> bool:
    """An empty cell or the word NULL: a row with no recorded value, not a group called NULL. Display only; the
    group keeps its key, so no number and no grouping changes."""
    if key is None or (isinstance(key, float) and key != key):
        return True
    return str(key).strip().casefold() in ("", "null")


def _distinct(a, b):
    """a and b written with just enough significant digits to tell them apart, both written the same way."""
    for n in range(3, 13):
        x, y = f"{a:#.{n}g}", f"{b:#.{n}g}"
        if x != y:
            return x, y
    return f"{a:#.12g}", f"{b:#.12g}"


def _headline(t, p, mlab, period, unit, ratio, base, cur):
    """The first sentence of the conclusion. The direction word follows the sign of the unrounded change; when the two
    values are written the same at the precision shown, nothing is called a rise or a fall."""
    per = f"{p['open']}{period}{p['close']}"
    d = cur - base
    if fmt(base, unit) == fmt(cur, unit):
        b, c = (fmt(base, unit),) * 2 if base == cur else _distinct(base, cur)
        return t["flat_head"].format(m=mlab, p=per, b=b, c=c)
    if ratio:
        return t["head_rate"].format(m=mlab, p=per, dir=t["rise" if d >= 0 else "fall"],
                                     b=fmt(base, unit), c=fmt(cur, unit), d=fmt(d, unit, True))
    g = cur / base - 1 if base else None
    return t["head_amount"].format(m=mlab, p=per, dir=t["up" if d >= 0 else "down"],
                                   a=fmt(abs(d), "count" if unit != "ratio" and abs(d) >= 0.5 else unit), g=pct(g),
                                   b=fmt(base, unit), c=fmt(cur, unit))


def seg_label(ws, world, dim, key, lang):
    eid = world.entity_for(dim, key)
    named = label(world.entities[eid].get("label"), lang) if eid else None
    # A name a person gave the value wins; the label intake writes is the raw key itself.
    if is_blank(key) and (named is None or is_blank(named)):
        return BLANK.get(lang, BLANK["en"])
    return named if named is not None else str(key)


def slot_label(ws, world, slot, lang):
    parts = [*slot["path"], [slot["dimension"], slot["value"]]]
    return " → ".join(f"{label(ws.dimensions[d].get('label', d), lang)}={seg_label(ws, world, d, v, lang)}" for d, v in parts)


def bar_svg(rows, title="", value_text=None):
    """rows: [(label, value, share)] -> a horizontal bar chart of contributions, as an SVG string.
    Each bar is labelled with its signed change, as in the table, and its share of all movement in brackets
    (the share has no sign: the sign belongs to the change, so a label cannot contradict the bar's direction)."""
    value_text = value_text or (lambda v: fmt(v, None, True))
    w, h, left, pad = 640, 26, 170, 8
    height = pad * 2 + h * len(rows) + (22 if title else 0)
    top = pad + (22 if title else 0)
    mx = max((abs(v) for _, v, _ in rows), default=1) or 1
    has_neg, has_pos = any(v < 0 for _, v, _ in rows), any(v > 0 for _, v, _ in rows)
    span = w - left - 150
    zero = left + (span / 2 if has_neg and has_pos else span if has_neg else 0)
    scale = (span / 2 if has_neg and has_pos else span) / mx
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{height}" font-family="sans-serif" font-size="12">']
    if title:
        out.append(f'<text x="{pad}" y="16" font-weight="bold">{_esc(title)}</text>')
    for i, (lab, v, sh) in enumerate(rows):
        y = top + i * h
        x0, x1 = sorted((zero, zero + v * scale))
        color = "#0072B2" if v >= 0 else "#D55E00"
        out.append(f'<text x="{left - 6}" y="{y + 17}" text-anchor="end">{_esc(lab)}</text>')
        out.append(f'<rect x="{x0:.1f}" y="{y + 5}" width="{max(x1 - x0, 1):.1f}" height="{h - 10}" fill="{color}"/>')
        txt = value_text(v) + (f" ({pct(sh, False)})" if sh is not None else "")
        out.append(f'<text x="{left + span + 8:.1f}" y="{y + 17}" text-anchor="start">{_esc(txt)}</text>')
    out.append(f'<line x1="{zero:.1f}" y1="{top}" x2="{zero:.1f}" y2="{top + h * len(rows)}" stroke="#555"/>')
    out.append("</svg>")
    return "\n".join(out)


UP, DOWN, NEUTRAL = "#0072B2", "#D55E00", "#999999"  # Okabe-Ito blue / vermillion, and grey for totals


def waterfall_svg(ws, world, wf, lang):
    """Base bar, one floating bar per contribution (blue up, vermillion down, signed labels), current bar."""
    t = T[lang]
    unit = wf.get("unit")
    items = [(t["w_base"], wf["base"], "total")]
    for st in wf["steps"]:
        lab = seg_label(ws, world, st["dimension"], st["label_key"], lang) if st.get("label_key") is not None \
            else t["w_others"].format(n=st.get("others", 0))
        items.append((lab, st["value"], "step"))
    items.append((t["w_cur"], wf["current"], "total"))
    W, H, top, bottom, left = 680, 300, 30, 60, 20
    level, tops = wf["base"], []
    for lab, v, kind in items:
        if kind == "total":
            tops.append((0, v))
        else:
            tops.append((level, level + v))
            level += v
    # The axis always includes zero: a bar chart with a cut-off axis draws a 1.6x change as a 7x one.
    lo = min(0.0, *(min(a, b) for a, b in tops))
    hi = max(0.0, *(max(a, b) for a, b in tops))
    span = (hi - lo) or 1.0
    y = lambda v: top + (H - top - bottom) * (1 - (v - lo) / span)  # noqa: E731
    bw = (W - 2 * left) / len(items)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif" font-size="12">',
           f'<text x="{left}" y="18" font-weight="bold">{_esc(t["waterfall_title"])}</text>']
    for i, ((lab, v, kind), (a, b)) in enumerate(zip(items, tops)):
        x = left + i * bw + bw * 0.15
        y0, y1 = sorted((y(a), y(b)))
        color = NEUTRAL if kind == "total" else (UP if v >= 0 else DOWN)
        out.append(f'<rect x="{x:.1f}" y="{y0:.1f}" width="{bw * 0.7:.1f}" height="{max(y1 - y0, 1):.1f}" fill="{color}"/>')
        txt = fmt(v, unit) if kind == "total" else fmt(v, unit, True)
        out.append(f'<text x="{x + bw * 0.35:.1f}" y="{y0 - 4:.1f}" text-anchor="middle">{_esc(txt)}</text>')
        out.append(f'<text x="{x + bw * 0.35:.1f}" y="{H - bottom + 16}" text-anchor="middle">{_esc(lab)}</text>')
    out.append(f'<line x1="{left}" y1="{y(0):.1f}" x2="{W - left}" y2="{y(0):.1f}" stroke="#555"/>')
    out.append(f'<text x="{left - 4}" y="{y(0) + 4:.1f}" text-anchor="end" fill="#555">0</text>')
    out.append("</svg>")
    return "\n".join(out)


def daily_svg(daily, lang, unit):
    """The two periods day by day: current solid blue, base dashed grey; each day's gap labelled with its sign."""
    t = T[lang]
    cur = [x["value"] for x in daily["current"]]
    base = [x["value"] for x in daily["base"]]
    vals = [v for v in cur + base if v is not None]
    if not vals:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'
    W, H, top, bottom, left = 680, 276, 30, 66, 60
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    n = len(cur)
    x = lambda i: left + (W - left - 20) * (i / max(n - 1, 1))  # noqa: E731
    y = lambda v: top + (H - top - bottom) * (1 - (v - lo) / span)  # noqa: E731

    def path(vs):
        pts = [f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vs) if v is not None]
        return " ".join(pts)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif" font-size="12">',
           f'<text x="10" y="18" font-weight="bold">{_esc(t["daily_title"])}</text>',
           f'<polyline points="{path(base)}" fill="none" stroke="{NEUTRAL}" stroke-width="2" stroke-dasharray="5,4"/>',
           f'<polyline points="{path(cur)}" fill="none" stroke="{UP}" stroke-width="2.5"/>']
    ex = set(daily.get("excluded_days") or [])
    # A date label needs about 55 px and a signed value about 70 px. Beyond that many days, every Nth date is
    # labelled and only the largest rise and the largest fall carry a value; the rest stay readable as points.
    step_px = (W - left - 20) / max(n - 1, 1)
    date_every = max(1, math.ceil(55 / step_px))
    gaps = {i: c - b for i, (c, b) in enumerate(zip(cur, base)) if c is not None and b is not None}
    if step_px >= 70 or len(gaps) <= 1:
        valued = set(gaps)
    else:
        valued = {max(gaps, key=gaps.get), min(gaps, key=gaps.get)}
        i, j = sorted(valued, key=lambda k: -abs(gaps[k]))[:2] if len(valued) == 2 else (None, None)
        if j is not None and abs(i - j) * step_px < 70:
            valued = {i}
    for i, g in gaps.items():
        day = daily["current"][i]["day"]
        out.append(f'<circle cx="{x(i):.1f}" cy="{y(cur[i]):.1f}" r="3" fill="{UP if g >= 0 else DOWN}"/>')
        if i in valued:
            out.append(f'<text x="{x(i):.1f}" y="{H - bottom + 46}" text-anchor="middle" fill="{UP if g >= 0 else DOWN}">'
                       f'{_esc(fmt(g, unit, True))}</text>')
        if i % date_every == 0:
            grey = ' fill="#999"' if day in ex else ""
            out.append(f'<text x="{x(i):.1f}" y="{H - bottom + 30}" text-anchor="middle"{grey}>{_esc(day[5:])}</text>')
    out.append(f'<text x="{left - 6}" y="{y(hi) + 4:.1f}" text-anchor="end">{_esc(fmt(hi, unit))}</text>')
    out.append(f'<text x="{left - 6}" y="{y(lo) + 4:.1f}" text-anchor="end">{_esc(fmt(lo, unit))}</text>')
    out.append(f'<text x="{W - 200}" y="18" fill="{UP}">— {_esc(t["w_cur"])}</text>'
               f'<text x="{W - 110}" y="18" fill="#777">- - {_esc(t["w_base"])}</text>')
    out.append("</svg>")
    return "\n".join(out)


def _big_share(ws, cut):
    """True when a cut stopped although its top group carries at least the user's single-point share of all movement."""
    share = (cut.get("gate") or {}).get("top1_abs_share")
    return cut["decision"]["then"].get("action") == "stop" and cut.get("role") != "cross_check" \
        and share is not None and share >= param(ws, "single_point_min_share")


def _why_not_single(ws, cut, lang):
    """Which test the top group failed, as the stop.cut table applies them."""
    t, g = T[lang], cut.get("gate") or {}
    ex = g.get("top1_excess")
    if ex is None or ex < param(ws, "single_point_min_excess"):
        return t["why_in_step"].format(ex=pct(ex, False), need=pct(param(ws, "single_point_min_excess"), False))
    z = g.get("top1_abs_z")
    if z is None:
        return t["why_no_history"]
    zmin = param(ws, "segment_z_min_when_unusual" if g.get("context_unusual") else "segment_z_min")
    if z < zmin:
        return t["why_within_swing"].format(z=_m(f"{z:.2f}"), zmin=_m(f"{zmin:g}"))
    return t["why_other"]


def _dominance(ws, world, cut, lang):
    t = T[lang]
    r = cut["result"]
    if r["operator"] == "divisive" and r.get("larger_effect") in ("structure", "rate"):
        return t[f"larger_{r['larger_effect']}"]
    if "sides" in r["operator"] and r.get("larger_effect") in ("mix", "performance"):
        return t[f"larger_{r['larger_effect']}"]
    g = cut.get("gate") or {}
    if _big_share(ws, cut):
        why = cut["decision"]["then"].get("reason")
        kw = {"seg": seg_label(ws, world, cut["dimension"], r["top1_key"], lang),
              "share": pct(g["top1_abs_share"], False), "need": pct(param(ws, "single_point_min_share"), False)}
        if why == "whole_number_within_usual_range":
            z = g.get("top1_abs_z")
            swing = ""
            if param(ws, "drill_quiet_total_when_group_stands_out"):
                swing = t["swing_no_history"] if z is None else \
                    t["swing_within"].format(z=_m(f"{z:.2f}"), zmin=_m(f"{param(ws, 'group_stands_out_z'):g}"))
            return t["dom_big_quiet"].format(swing=swing, **kw)
        if why == "top_group_too_small":
            return t["dom_big_small"].format(**kw)
        return t["dom_big_other"].format(why=_why_not_single(ws, cut, lang), **kw)
    ex = g.get("top1_excess")
    if cut["decision"]["then"].get("action") == "drill" and ex is not None:
        return t["dom_concentrated"].format(seg=seg_label(ws, world, cut["dimension"], r["top1_key"], lang), p=pct(ex, False))
    return t["dom_spread"]


def _esc(x):
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out


def _cut_table(ws, world, cut, unit, lang):
    t, r = T[lang], cut["result"]
    op, d = r["operator"], cut["dimension"]
    sl = lambda k: seg_label(ws, world, d, k, lang)  # noqa: E731
    if op == "additive":
        # one number format per table: once any value reaches thousands, decimals are noise
        if unit not in ("ratio", "count") and any(abs(x[k]) >= 1000 for x in r["segments"] for k in ("base", "cur", "delta")):
            unit = "count"
        # share of all movement (|change| / sum of |change|): always 0..100%, the sign is in the change column
        tot = math.fsum(abs(x["delta"]) for x in r["segments"]) or None
        return _table([t["segment"], t["base"], t["cur"], t["delta"], t["share_abs"]],
                      [[sl(x["key"]), fmt(x["base"], unit), fmt(x["cur"], unit), fmt(x["delta"], unit, True),
                        pct(abs(x["delta"]) / tot if tot else None, False)] for x in r["segments"]])
    if op == "divisive":
        tot = math.fsum(abs(x["total"]) for x in r["segments"]) or None
        return _table([t["segment"], t["base"], t["cur"], t["structure"], t["rate"], t["interaction"], t["share_abs"]],
                      [[sl(x["key"]), f'{fmt(x["rate_base"], unit)} ({x["weight_base"]:.0%})', f'{fmt(x["rate_cur"], unit)} ({x["weight_cur"]:.0%})',
                        fmt(x["structure"], unit, True), fmt(x["rate"], unit, True), fmt(x["interaction"], unit, True),
                        pct(abs(x["total"]) / tot if tot else None, False)] for x in r["segments"]])
    if op == "second_order_sides":
        a, b = (seg_label(ws, world, cut["side_dimension"], v, lang) for v in cut["sides"])
        return _table([t["segment"], f"{a} %", f"{b} %", t["mix"], t["performance"], t["unmatched"], t["share"]],
                      [[sl(x["key"]), pct(x["growth_a"]), pct(x["growth_b"]), pp(x["mix"]), pp(x["performance"]), pp(x["unmatched"]), pct(x["share"])]
                       for x in r["segments"]])
    rows = []
    for x in r["segments"]:
        a, b = x.get("contrib_w1"), x.get("contrib_w2")
        rows.append([sl(x["key"]), pp(a) if a is not None else "", pp(b) if b is not None else "",
                     pp(x["change"]) if unit != "currency" or a is not None else fmt(x["change"], unit, True), pct(x["share"])])
    return _table([t["segment"], "w1", "w2", t["delta"], t["share"]], rows)


def _value_text(cut, unit):
    """The signed change of a segment, written the way the table beside the chart writes it."""
    r = cut["result"]
    if r["operator"] == "additive":
        if unit not in ("ratio", "count") and any(abs(x[k]) >= 1000 for x in r["segments"] for k in ("base", "cur", "delta")):
            unit = "count"
        return lambda v: fmt(v, unit, True)
    if r["operator"] == "divisive":
        return lambda v: fmt(v, unit, True)
    return pp


def _cut_value(cut):
    r = cut["result"]
    return {"additive": "delta", "divisive": "total"}.get(r["operator"], "total" if r["operator"].startswith("second_order_sides") else "change")


def find_entry(ws, eid):
    return next((x for k in ("events", "mechanisms", "actions") for x in ws.world.get(k, []) if x["id"] == eid), {})


def source_text(entry, lang):
    src = entry.get("source") or {}
    kind = SOURCE_KINDS[lang].get(src.get("kind"), src.get("kind", ""))
    name = label(src["label"], lang) if src.get("label") else src.get("ref")
    return f"{kind} · {name}" if name else kind


def _cite_line(ws, c, lang, unit=None):
    t, p = T[lang], PUNCT[lang]
    entry = find_entry(ws, c["id"])
    when = f'{entry.get("start")}~{entry.get("end") or "…"} ' if c["kind"] == "event" else ""
    tag = t["mechanism"] if c["kind"] == "mechanism" else t["event"]
    if c.get("external"):
        tag = t[c["checks"]["status"]]
    status = t["status_confirmed"] if c["status"] == "confirmed" else t["status_proposed"]
    lines = [f'- **{tag}** `{c["id"]}`{p["colon"]}{when}{entry_text(entry, lang)}'
             f'{p["open"]}{t["source"]}{p["colon"]}{source_text(entry, lang)}{p["semi"]}{status}{p["close"]}']
    fl = _fit_line(c, ws, lang)
    if fl:
        lines.append(f"  - {fl}")
    if entry.get("refuted_by"):
        lines.append(f'  - {t["refuted_by"]}{p["colon"]}{label(entry["refuted_by"], lang)}')
    ck = c.get("checks") or {}
    if "slice" in ck:
        sz = ck["size"]
        size = t["size_text2"].format(e=fmt(sz["change_on_event_days"], unit, True), all=fmt(ck["slice"]["slice_delta"], unit, True),
                                      v=pct(sz["share_of_slice_change"], False), t=pct(sz["threshold"], False))
        if (sz["share_of_slice_change"] or 0) > 1:
            size += p["comma"] + t["size_note"]
        lines.append(f'  - {t["timing"]}{p["colon"]}{t["overlap"].format(n=ck["timing"]["overlap_days"])}')
        lines.append(f'  - {t["slice"]}{p["colon"]}{t["slice_text"].format(v=pct(ck["slice"]["share_of_change"], False), t=pct(ck["slice"]["threshold"], False))}')
        lines.append(f'  - {t["size"]}{p["colon"]}{size}')
        ev = ck.get("evidence")
        if ev:
            u = ev.get("unit") or ""
            lines.append(f'  - {t["evidence"]}{p["colon"]}{ev["source"]} {fmt(ev["mean_on_event_days"])}{u} {t["vs"]} {fmt(ev["mean_other_days"])}{u}')
        lines.append(f'  - {t["refute"]}')
    return lines


def _quality_items(s, lang, names=None):
    t, p = T[lang], PUNCT[lang]
    out = []
    names = set(s["quality"].get("failed", []) if names is None else names)
    for c in s["quality"].get("checks", []):
        if c["check"] not in names or c["status"] == "ok":
            continue
        name = c["check"]
        if name == "calendar_complete":
            v = p["comma"].join(c["missing"]["base"] + c["missing"]["current"])
        elif name == "key_unique":
            v = p["comma"].join(f"{x['source']} {x['duplicates']:,}/{x['rows']:,}" for x in c["duplicates"])
        elif name in ("daily_volume_steady", "daily_value_steady"):
            v = p["comma"].join(f"{x['day']} ×{x['ratio']:.2f}" for x in c["days"][:5])
        elif name == "no_single_row_dominates":
            v = p["comma"].join(f"{x['key']} {fmt(x['effect'], None, True)}" for x in c["rows"][:3])
        elif name == "row_ratio":
            v = p["comma"].join(f"{x['source']} {x['base_rows']:,.0f} → {x['current_rows']:,.0f}" for x in c["sources"])
            mon = [x["source"] for x in c["sources"] if x.get("monthly") and not x.get("whole_months")]
            if mon:
                v += p["semi"] + t["q_monthly"].format(src=p["comma"].join(mon))
        elif name == "dimension_values_stable":
            v = p["comma"].join(f"{x['dimension']}: {'/'.join(x['gone'])} → {'/'.join(x['new'])}" for x in c["dimensions"] if x["looks_renamed"])
        else:
            v = ""
        out.append(t.get(f"q_{name}", name).format(v=v))
    return p["semi"].join(out)


def _data_notes(s, lang) -> str:
    t, p = T[lang], PUNCT[lang]
    out = []
    for n in s.get("quality", {}).get("notes", []):
        d = dict(n)
        for k in ("share", "base_share"):
            if d.get(k) is not None:
                d[k] = f"{d[k]:.1%}"
        if "share_constant" in d:
            d["pct"] = f"{d['share_constant']:.0%}"
        for k in ("min", "max"):
            if k in d:
                d[k] = f"{d[k]:.3g}"
        out.append(t[f"note_{n['note']}"].format(**d))
    return p["semi"].join(out)


def _fit_line(c, ws, lang):
    t = T[lang]
    k = c.get("explains")
    if not k:
        return None
    if k == "term_mismatch":
        acts = find_entry(ws, c["id"]).get("acts_on")
        return t["fit_term_mismatch"].format(acts=t.get(f"term_{acts}", acts), term=t["term_structure" if acts == "rate" else "term_rate"])
    return t[f"fit_{k}"]


def _stop_line(ws, cut, lang):
    """The sentence that says why a cut was not drilled into."""
    t = T[lang]
    why = cut["decision"]["then"].get("reason")
    if why == "whole_number_within_usual_range":
        return t["stop_quiet"]
    if why == "top_group_too_small":
        return t["stop_small"].format(n=f"{cut['gate'].get('top1_n') or 0:,.0f}", unit=cut["gate"].get("size_unit") or "rows",
                                      min=f"{param(ws, 'segment_min_n'):g}")
    return t["stop_not_single"] if _big_share(ws, cut) else t["spread"]


def _cut_verdict(ws, world, s, cut, lang):
    """What a person reads under a cut's table: where the analysis went next and what led. Left out of a blocked report."""
    t, p = T[lang], PUNCT[lang]
    act = cut["decision"]["then"].get("action")
    why = cut["decision"]["then"].get("reason")
    topname = f"**{seg_label(ws, world, cut['dimension'], cut['result']['top1_key'], lang)}**"
    if cut.get("role") == "cross_check":
        out = ["", t["cross_check"] + topname + p["comma"] + t["cross_ok" if cut.get("confirms") else "cross_no"]]
    elif act == "drill":
        lead = t["drill_quiet"] if why == "single_point_inside_a_quiet_total" else \
            t["drill"] if s.get("vertical_mode", "drill") != "each" else t["single"]
        out = ["", lead + topname]
    else:
        out = ["", _stop_line(ws, cut, lang)]
    return out + ["", t["dominance"].format(t=_dominance(ws, world, cut, lang))]


def _ruled_out(ws, s, n, lang, unit):
    t, world = T[lang], World(ws)
    out = []
    for r in n.get("ruled_out", []):
        if r["kind"] == "market":
            out.append(t["ro_market"].format(v=fmt(r["expected_part"], unit, True)))
        elif r["kind"] == "record_cannot_explain":
            what = entry_text(find_entry(ws, r["id"]), lang).rstrip("。.")
            out.append(t["ro_record_mix" if r["why"] == "why_mix_matters" else "ro_record"].format(what=what))
        elif r["kind"] == "outside_event_not_proven":
            out.append(t["ro_event"].format(what=entry_text(find_entry(ws, r["id"]), lang).rstrip("。.")))
        elif r["kind"] == "cut_spread":
            dim = label(ws.dimensions[r["dimension"]].get("label", r["dimension"]), lang)
            cut = next((c for c in s["cuts"] if c["dimension"] == r["dimension"] and c["filters"] == r["filters"]), None)
            if r["why"] == "whole_number_within_usual_range":
                out.append(t["ro_quiet"])
            elif cut is not None and _big_share(ws, cut):
                out.append(t["ro_cut_big"].format(dim=dim, share=pct(cut["gate"]["top1_abs_share"], False)))
            else:
                out.append(t["ro_cut"].format(dim=dim))
    return list(dict.fromkeys(out))


def leaf_slot(s):
    leaves = [x for x in s["slots"] if x.get("leaf", True)]
    return leaves[0] if leaves else None


def _no_owner_line(ws, world, s, unit, lang):
    """No action is recorded: name the slices that carry the movement and say plainly that nobody owns them yet."""
    t = T[lang]
    items = []
    for slot in [x for x in s["slots"] if x.get("leaf", True)][:2]:
        cut = s["cuts"][slot["cut"]]
        seg = next((x for x in cut["result"]["segments"] if x["key"] == slot["value"]), None)
        change = f" {_value_text(cut, unit)(seg[_cut_value(cut)])}" if seg else ""
        items.append(f"{slot_label(ws, world, slot, lang)}{change}")
    if not items:
        return _no_owner_stop(ws, world, s, unit, lang)
    return t["no_owner"].format(items=PUNCT[lang]["semi"].join(items))


def _no_owner_stop(ws, world, s, unit, lang):
    """The run stopped at the first cut, so no slice was drilled: name the cut's largest movers, never an owner."""
    t = T[lang]
    cut = s["cuts"][0] if s["cuts"] else None
    if cut is None or s["order"] != "first" or cut["decision"]["then"].get("action") != "stop" \
            or cut["decision"]["then"].get("reason") == "top_group_too_small":
        return t["no_action"]
    vf, show = _cut_value(cut), _value_text(cut, unit)
    movers = [x for x in sorted(cut["result"]["segments"], key=lambda x: -abs(x[vf])) if x[vf]][:2]
    if not movers:
        return t["no_action"]
    items = [f"{slot_label(ws, world, {'path': [], 'dimension': cut['dimension'], 'value': x['key']}, lang)} {show(x[vf])}" for x in movers]
    dl = label(ws.dimensions[cut["dimension"]].get("label", cut["dimension"]), lang)
    quiet = cut["decision"]["then"].get("reason") == "whole_number_within_usual_range"
    lead = t["stop_first_quiet" if quiet else "stop_first_other"].format(dim=dl)
    return t["no_owner_quiet"].format(lead=lead, items=PUNCT[lang]["semi"].join(items))


def _blocked_items(s, lang):
    """One line per failed check, in plain words where the run can say them."""
    out = []
    for c in s["checks"]:
        if c["pass"]:
            continue
        detail = _quality_items(s, lang) if c["check"] == "data_quality" and s.get("quality", {}).get("suspect") else c["detail"]
        out.append(f"- {c['check']}: {detail}" if detail else f"- {c['check']}")
    return out


def _not_checked(ws, s, lang):
    """What this report did not look at, from facts the run holds (see quality.scope_facts). Nothing is guessed."""
    t, p = T[lang], PUNCT[lang]
    f = quality.scope_facts(ws, s)
    dim = lambda d: (lambda lab: f"{lab} (`{d}`)" if lab != d else f"`{d}`")(label(ws.dimensions[d].get("label", d), lang))  # noqa: E731
    items = [t[f"agg_{x['agg']}"].format(column=x["column"], source=x["source"]) + " (" + t["dated_by"].format(date=x["date"]) + ")"
             for x in f["measures"]]
    L = [t["nc_used"].format(items=p["semi"].join(items)), t["nc_as_is"]]
    L.append(t["nc_cut"].format(cut=p["comma"].join(map(dim, f["cut"]))) if f["cut"] else t["nc_no_cut"])
    if f["not_cut"]:
        L.append(t["nc_not_cut"].format(rest=p["comma"].join(map(dim, f["not_cut"]))))
    if f["removed"]:
        parts = []
        for r in f["removed"]:
            for col, vals in r["rule"].items():
                w = r["windows"]
                parts.append(t["nc_removed_item"].format(
                    source=r["source"], column=col, values=p["comma"].join(f"`{v}`" for v in vals),
                    c=w.get("current", {}).get("removed", 0), cr=w.get("current", {}).get("rows", 0),
                    b=w.get("base", {}).get("removed", 0), br=w.get("base", {}).get("rows", 0)))
        L.append(t["nc_removed"].format(items=p["semi"].join(parts)))
    else:
        L.append(t["nc_no_rule"])
    if f["copies_matter"]:
        L.append(t["nc_copies_" + {"once": "once", "every_row": "every_row", "unknown": "unknown"}.get(f["copies_answer"], "none")])
    if f["cut"]:
        blank = [x for x in f["blank"] if x["current"]["blank"] or x["base"]["blank"]]
        sh = lambda b, n: f"{b / n:.1%}" if n else "—"  # noqa: E731
        if blank:
            L.append(t["nc_blank"].format(items=p["semi"].join(t["nc_blank_item"].format(
                column=x["column"], b=x["current"]["blank"], n=x["current"]["rows"], share=sh(x["current"]["blank"], x["current"]["rows"]),
                bb=x["base"]["blank"], bn=x["base"]["rows"], bshare=sh(x["base"]["blank"], x["base"]["rows"])) for x in blank)))
        else:
            L.append(t["nc_no_blank"].format(dims=p["comma"].join(f"`{x['column']}`" for x in f["blank"])))
    L.append(t["nc_events"].format(ids=p["comma"].join(f"`{i}`" for i in f["external"])) if f["external"] else t["nc_no_event"])
    if not f["market_compared"]:
        L.append(t["nc_no_market"])
    failed = f["checks"]["failed"]
    L.append(t["nc_checks"].format(ran=f["checks"]["ran"], notes=f["notes"],
                                   failed=t["nc_failed"].format(names=p["comma"].join(failed)) if failed else t["nc_none_failed"]))
    dq = f["quality"]["warned"] + [x for x in f["quality"]["failed"] if x not in f["quality"]["warned"]]
    if dq:
        L.append(t["nc_dq_warned"].format(names=p["comma"].join(dq)))
    return [f"## {t['notchecked']}", "", *[f"- {x}" for x in L], ""]


def _decision_text(d):
    return ", ".join(f"{k}={v}" for k, v in d["then"].items())


def render(ws, s, lang="zh", out_dir: Path | None = None) -> str:
    t, world, m = T[lang], World(ws), s["metric"]
    unit = ws.metrics[m].get("unit")
    mlab = label(ws.metrics[m].get("label", m), lang)
    q = s["qualify"]
    title = label(s["config"].get("question"), lang) if s["config"].get("question") else f"{mlab} {s['current'][0]}~{s['current'][1]}"
    L = [f"# {title}", ""]
    blocked = s["blocked"]
    if blocked:
        L += [t["blocked"], *_blocked_items(s, lang), ""]

    p = PUNCT[lang]
    L += [f"## {t['conclusion']}", ""]
    suspect = s.get("quality", {}).get("suspect")
    if suspect:
        L += [t["suspect"].format(items=_quality_items(s, lang)), ""]
    warn = [n for n in s.get("quality", {}).get("warned", [])
            if next((c for c in s["quality"]["checks"] if c["check"] == n), {}).get("status") == "fail"]
    if warn:
        L += [t["quality_warn_blocked" if blocked else "quality_warn"].format(items=_quality_items(s, lang, warn)), ""]
    notes = _data_notes(s, lang)
    if notes:
        L += [t["data_note_blocked" if blocked else "data_note"].format(items=notes), ""]
    if blocked:
        L += [t["blocked_head"], ""]
    period = f"{s['current'][0]}~{s['current'][1]} {t['vs']} {s['base'][0]}~{s['base'][1]}"
    first = s["cuts"][0]["result"] if s["cuts"] else None
    head = f"**{mlab}**{p['open']}{period}{p['close']}"
    n = s.get("narrative") or {}
    ratio = ws.metrics[m].get("kind") == "ratio"
    d_all = q["total_cur"] - q["total_base"]
    if s["order"] == "second_sides" and first:
        a, b = (seg_label(ws, world, s["cuts"][0]["side_dimension"], v, lang) for v in s["cuts"][0]["sides"])
        L.append(head + p["colon"] + t["gap_a_b"].format(a=a, b=b, ga=pct(first["growth_a"]), gb=pct(first["growth_b"]), gap=pp(first["gap"])))
    else:
        L.append(_headline(t, p, mlab, period, unit, ratio, q["total_base"], q["total_cur"]))
    if not blocked and first and first.get("larger_effect") in ("structure", "rate", "mix", "performance"):
        L += ["", t[f"larger_{first['larger_effect']}"]]
    top = None if blocked else leaf_slot(s)
    if top and not top.get("merged_from"):
        cut = s["cuts"][top["cut"]]
        r = cut["result"]
        seg = next(x for x in r["segments"] if x["key"] == top["value"])
        val = seg[_cut_value(cut)]
        segname = slot_label(ws, world, top, lang)
        rest = n.get("rest")
        if r["operator"] == "additive" and rest:
            L += ["", t["main_amount"].format(seg=segname, v=fmt(val, unit, True), g=pct(rest["top_change"]))]
        elif r["operator"] in ("additive", "divisive"):
            L += ["", t["main_rate"].format(seg=segname, v=fmt(val, unit, True))]
        else:
            L += ["", t["main_abs"].format(seg=segname, v=pp(val), p=pct(r.get("top1_abs_share"), False))]
        if rest and rest.get("rest_usual_change") is not None:
            f_ = (lambda x: fmt(x, unit, True)) if rest["kind"] == "rate_difference" else pct
            L.append(t["rest_line"].format(r=f_(rest["rest_change"]), u=f_(rest["rest_usual_change"]),
                                           judge=t[{"as_usual": "rest_same", "better": "rest_better", "worse": "rest_worse"}
                                                   .get(rest["rest_verdict"], "rest_same")]))
        on = n.get("onset")
        if on and on.get("found"):
            L.append(t["onset_line"].format(d=on["start"]))
            for e in on.get("events", [])[:1]:
                gap = t["same_day"] if e["days_from_onset"] == 0 else t["days_after"].format(n=abs(e["days_from_onset"]))
                L.append(t["onset_event"].format(e=entry_text(find_entry(ws, e["event"]), lang).rstrip("。."), gap=gap))
        if n.get("recent_weeks"):
            rw = n["recent_weeks"]
            fw = (lambda x: fmt(x, unit, True)) if ratio else pct
            if rw[0].get("measure") == "weight":
                fs, what = (lambda x: pp(x)), t["weight_of"].format(seg=segname)
            else:
                fs, what = fw, (f"「{segname}」" if lang == "zh" else f"\"{segname}\"")
            L.append(t["recent_line"].format(
                whole=mlab, seg=what,
                items=p["comma"].join(f"{w['window'][0][5:]}~{w['window'][1][5:]} {fw(w['whole_change'])} / {fs(w['change'])}" for w in rw)))
        if n.get("secondary"):
            sc = n["secondary"]
            L += ["", t["secondary"].format(seg=f"{label(ws.dimensions[sc['dimension']].get('label', sc['dimension']), lang)}="
                                                f"{seg_label(ws, world, sc['dimension'], sc['key'], lang)}", v=fmt(sc["value"], unit, True))]
        if n.get("offsets"):
            L.append(t["offsets"].format(items=p["comma"].join(
                f"{seg_label(ws, world, o['dimension'], o['key'], lang)} {fmt(o['value'], unit, True)}" for o in n["offsets"])))
        term = top.get("dominant_term")
        solid = [c for c in top["citations"] if c.get("explains", "change") == "change"
                 and (c["checks"]["status"] == "supported" if c.get("external") else c.get("status") == "confirmed")]
        solid.sort(key=lambda c: c["kind"] != "event")
        if suspect:
            L.append("> " + t["data_suspect_slot"])
        elif solid:
            L.append(f"> **{t['you_may_not_know']}**{p['colon']}{entry_text(find_entry(ws, solid[0]['id']), lang)}")
        elif top.get("pending_confirmation"):
            for cid in top["pending_confirmation"][:2]:
                e = find_entry(ws, cid)
                src = e.get("source") or {}
                where = t["from_document"].format(ref=src.get("ref", "")) if src.get("kind") == "document" else \
                    t["from_system_record"].format(ref=src.get("ref", ""))
                L.append(f"> **{t['possible_cause']}**{p['colon']}{entry_text(e, lang)}{p['open']}{where}{p['close']}")
                if src.get("quote"):
                    L.append(f"> {t['quote_line'].format(q=src['quote'])}")
            L.append("> " + t["pending_line"])
        elif top["status"] == "gap":
            L.append("> " + t["gap_mix" if term == "structure" else "gap"].format(seg=segname))
            for c in top["citations"]:
                if c.get("explains") in ("cannot_explain_change", "why_mix_matters", "term_mismatch"):
                    L.append(f"> 「{entry_text(find_entry(ws, c['id']), lang).rstrip('。.')}」{_fit_line(c, ws, lang)}" if lang == "zh" else
                             f"> \"{entry_text(find_entry(ws, c['id']), lang).rstrip('。.')}\": {_fit_line(c, ws, lang)}")
    ro = [] if blocked else _ruled_out(ws, s, n, lang, unit)
    if ro:
        L += ["", t["ruled_out"].format(items=p["semi"].join(ro))]
    L.append("")

    L += [f"## {t['unusual']}", ""]
    if blocked:
        L += [t["blocked_computed"], ""]
    if s["order"] != "first":
        L += [t["qualify_scope"].format(m=mlab), ""]
    v = (s.get("verdict_unusual") or {}).get("then", {}).get("verdict")
    z = q.get("robust_z")
    if z is None:
        L.append(t["flat_history"].format(n=q["history_n"]) if q.get("z_missing_reason") == "flat_history"
                 else t["short_history"].format(n=q.get("history_n", 0)))
    else:
        key = {"unusual_low": "unusual_low", "unusual_high": "unusual_high"}.get(v, "within")
        thr = ws.params.get("unusual_z_low" if key == "unusual_low" else "unusual_z", {}).get("value")
        L.append(t[key].format(n=q["history_n"], z=_m(f"{z:.2f}"), t=_m(str(thr))))
        if q.get("usual_range") and q.get("unusual_below") is not None:
            f_ = (lambda x: fmt(x, unit, True)) if ratio else pct
            key_ = "range_line_high_only" if q.get("unusual_below_clipped") else "range_line"
            L.append(t[key_].format(n=q["history_n"], lo=f_(q["usual_range"][0]), hi=f_(q["usual_range"][1]),
                                    below=f_(q["unusual_below"]), above=f_(q["unusual_above"])))
    lo_ = q.get("history_basis", {}).get("left_out_for_holidays") or []
    if lo_:
        L += ["", t["left_out"].format(n=len(lo_), items=p["comma"].join(f"{x['window'][0]}~{x['window'][1]}" for x in lo_))]
    if not blocked and q.get("own_part_usual") is not None:
        L += ["", t["market_usual"].format(mg=pct(q["market_growth"]), gap=pp(q["usual_gap"]), ep=fmt(q["expected_part"], unit, True),
                                           d=fmt(d_all, unit, True), op=fmt(q["own_part_usual"], unit, True),
                                           plain=fmt(q["own_part"], unit, True))]
    elif not blocked and q.get("market_growth") is not None:
        mv = (s.get("verdict_market") or {}).get("then", {}).get("verdict")
        d = q["total_cur"] - q["total_base"]
        L.append("")
        L.append(t["market_own2" if mv == "own" else "market_market2"].format(
            mg=pct(q["market_growth"]), mp=fmt(q["market_part"], unit, True), d=fmt(d, unit, True),
            op=fmt(q["own_part"], unit, True), os=pct(q["own_share"], False), ms=pct(q["market_share"], False)))
    qc = ws.project.get("quality") or {}
    if qc.get("closed_weekdays") and qc.get("status") == "proposed":
        names = WEEKDAY_NAMES[lang]
        ev = qc.get("evidence") or []
        note = p["comma"].join(t["closed_evidence"].format(e=x["empty_weeks"], w=x["weeks"], d=names[x["weekday"]]) for x in ev) \
            or t["closed_no_evidence"]
        L += ["", t["closed_inferred"].format(days=p["comma"].join(names[int(x)] for x in qc["closed_weekdays"]), note=note)]
    if q.get("holiday_misaligned"):
        items = p["comma"].join(f"{h.get('label_' + lang) or h['name']} {h['base_days']}→{h['current_days']}"
                                for h in q["calendar"]["holidays"] if h["difference"])
        L += ["", t["calendar"].format(items=items)]
    L.append("")

    L += [f"## {t['breakdown']}", ""]
    if blocked:
        L += [t["blocked_computed"], ""]
    start = len(L)
    for h in s["horizontal"]:
        ident = next(i for i in ws.model.get("identities", []) if i["id"] == h["identity"])
        formula = f"{label(ws.metrics[ident['left']].get('label'), lang)} = " + \
                  " × ".join(label(ws.metrics[f].get("label"), lang) for f in ident["factors"])
        L += [f"**{t['horizontal']}**{p['colon']}{formula}", ""]
        tot = math.fsum(abs(f["contribution"]) for f in h["factors"]) or None
        L += _table([t["factor"], t["base"], t["cur"], t["contribution"], t["share_abs"]],
                    [[label(ws.metrics[f["factor"]].get("label", f["factor"]), lang), fmt(f["base"], ws.metrics[f["factor"]].get("unit")),
                      fmt(f["cur"], ws.metrics[f["factor"]].get("unit")), fmt(f["contribution"], unit, True),
                      pct(abs(f["contribution"]) / tot if tot else None, False)] for f in h["factors"]])
        L.append("")
    for i, cut in enumerate(s["cuts"]):
        dl = label(ws.dimensions[cut["dimension"]].get("label", cut["dimension"]), lang)
        scope = " / ".join(f"{label(ws.dimensions[k].get('label', k), lang)}={seg_label(ws, world, k, val, lang)}" for k, val in cut["filters"].items())
        L += [f"### {i + 1}. {dl}" + (f"{p['open']}{scope}{p['close']}" if scope else ""), ""]
        L += _cut_table(ws, world, cut, unit, lang)
        if not blocked:
            L += _cut_verdict(ws, world, s, cut, lang)
        if out_dir is not None:
            vf = _cut_value(cut)
            tot_abs = math.fsum(abs(x[vf]) for x in cut["result"]["segments"]) or None
            rows = [(seg_label(ws, world, cut["dimension"], x["key"], lang), x[vf], abs(x[vf]) / tot_abs if tot_abs else None)
                    for x in cut["result"]["segments"]]
            charts = Path(out_dir) / "charts"
            charts.mkdir(parents=True, exist_ok=True)
            name = f"cut{i + 1}.{lang}.svg"
            (charts / name).write_text(bar_svg(rows, f"{dl}{p['open']}{t['bar_note']}{p['close']}", _value_text(cut, unit)),
                                       encoding="utf-8")
            L += ["", f"![{dl}](charts/{name})"]
        L.append("")
    tree = s.get("tree")
    if tree and len(tree["identities"]) > 1:
        L += [f"**{t['tree']}**{p['colon']}" + " × ".join(label(ws.metrics[f["factor"]].get("label", f["factor"]), lang)
                                                          for f in tree["leaves"]), ""]
        L += _table([t["factor"], t["base"], t["cur"], t["contribution"]],
                    [[label(ws.metrics[f["factor"]].get("label", f["factor"]), lang), fmt(f["base"], ws.metrics[f["factor"]].get("unit")),
                      fmt(f["cur"], ws.metrics[f["factor"]].get("unit")), fmt(f["contribution"], unit, True)] for f in tree["leaves"]])
        for x, sp in ({} if blocked else tree.get("ratio_splits", {})).items():
            L += ["", t["tree_split"].format(m=label(ws.metrics[x].get("label", x), lang),
                                             d=label(ws.dimensions[sp["dimension"]].get("label", sp["dimension"]), lang),
                                             s=fmt(sp["structure_total"], ws.metrics[x].get("unit"), True),
                                             r=fmt(sp["rate_total"], ws.metrics[x].get("unit"), True),
                                             lead=t[f"lead_{sp['larger_effect']}"])]
        L.append("")
    pv = s.get("pvm")
    if pv:
        dl = label(ws.dimensions[pv["dimension"]].get("label", pv["dimension"]), lang)
        L += [f"**{t['pvm']}**{p['open']}{dl}{p['close']}", ""]
        L += _table([t["pvm_term"], t["contribution"]],
                    [[t["pvm_volume"], fmt(pv["volume_total"], unit, True)], [t["pvm_mix"], fmt(pv["mix_total"], unit, True)],
                     [t["pvm_price"], fmt(pv["price_total"], unit, True)]] +
                    ([[t["pvm_new"], fmt(pv["new_total"], unit, True)]] if pv["new_total"] else []) +
                    ([[t["pvm_gone"], fmt(pv["gone_total"], unit, True)]] if pv["gone_total"] else []))
        top = next(x for x in pv["segments"] if x["key"] == pv["top_price_key"])
        if not blocked:
            L += ["", t["pvm_line"].format(lead=t[f"pvm_{pv['larger_effect']}"], q=pct(pv["quantity_growth"]),
                                           seg=seg_label(ws, world, pv["dimension"], top["key"], lang), v=fmt(top["price"], unit, True),
                                           p0=fmt(top.get("price_base"), unit), p1=fmt(top.get("price_cur"), unit))]
        L.append("")
    ga = s.get("growth_accounting")
    if ga:
        L += [f"**{t['ga']}**", ""]
        L += _table([t["ga_bucket"], t["contribution"], t["ga_customers"]],
                    [[t[f"ga_{k}"], fmt(ga["buckets"][k], unit, k != "retained"), f"{ga['customers'][k]:,}"]
                     for k in ("new", "resurrected", "expansion", "contraction", "churned", "retained")])
        L += ["", t["ga_line"].format(q=fmt(ga["quick_ratio"]), r=pct(ga["gross_retention"], False),
                                      o=fmt(ga["no_customer_delta"], unit, True)), ""]
    ch = s.get("charts") or {}
    if out_dir is not None and (ch.get("waterfall") or ch.get("daily")):
        cdir = Path(out_dir) / "charts"
        cdir.mkdir(parents=True, exist_ok=True)
        if ch.get("waterfall"):
            (cdir / f"waterfall.{lang}.svg").write_text(waterfall_svg(ws, world, ch["waterfall"], lang), encoding="utf-8")
            L += [f"![{t['waterfall_title']}](charts/waterfall.{lang}.svg)", ""]
        if ch.get("daily"):
            (cdir / f"daily.{lang}.svg").write_text(daily_svg(ch["daily"], lang, ws.metrics[m].get("unit")), encoding="utf-8")
            L += [f"![{t['daily_title']}](charts/daily.{lang}.svg)", ""]

    if len(L) == start:
        reason = ""
        if s["errors"]:
            reason = (": " if lang == "en" else "：") + p["semi"].join(f"{e['dimension']}: {e['error']}" for e in s["errors"][:2])
        elif not ws.metric_dimensions(m):
            reason = t["no_breakdown_dims"]
        L += [t["no_breakdown"].format(reason=reason), ""]

    L += [f"## {t['why']}", ""]
    # One entry per cause: a drill path is one cause seen at growing precision, so only its last step is listed.
    for slot in ([] if blocked else [x for x in s["slots"] if x.get("leaf", True)]):
        L += [f"**{slot_label(ws, world, slot, lang)}**", ""]
        if slot["status"] == "data_suspect":
            L.append("- " + t["data_suspect_slot"])
        elif slot["status"] == "gap":
            L.append("- " + t["gap_mix" if slot.get("dominant_term") == "structure" else "gap"].format(seg=slot_label(ws, world, slot, lang)))
        for c in slot["citations"]:
            L += _cite_line(ws, c, lang, unit)
        L.append("")
    if blocked:
        L += [t["blocked_why"], ""]
    elif not s["slots"]:
        L += [_stop_line(ws, s["cuts"][0], lang) if s["cuts"] else t["no_breakdown_why"], ""]

    L += _not_checked(ws, s, lang)

    L += [f"## {t['who']}", ""]
    acts = {a["id"]: a for a in ws.world.get("actions", [])}
    if blocked:
        L.append(t["blocked_who"])
    else:
        L += [f"- **{label(acts[a]['owner'], lang)}**{p['colon']}{label(acts[a]['action'], lang)}" for a in s["actions"]] or \
            [_no_owner_line(ws, world, s, unit, lang)]
    L.append("")

    if not blocked and (s["gaps"] or s["to_confirm"]):
        L += [f"## {t['confirm']}", ""]
        for g in s["gaps"]:
            slot = next(x for x in s["slots"] if x["id"] == g["slot"])
            L.append("- " + t["gap_mix" if g.get("dominant_term") == "structure" else "gap"].format(seg=slot_label(ws, world, slot, lang)))
        seen = set()
        for c in s["to_confirm"]:
            if c["id"] in seen:
                continue
            seen.add(c["id"])
            what = entry_text(find_entry(ws, c["id"]), lang)
            slot = next(x for x in s["slots"] if x["id"] == c["slot"])
            cite = next(x for x in slot["citations"] if x["id"] == c["id"])
            if cite.get("external"):
                L.append("- " + t["confirm_external"].format(what=what, st=t[cite["checks"]["status"]]))
            else:
                L.append("- " + t["confirm_proposed"].format(what=what))
        L.append("")

    cov = s["coverage"]
    L += [f"## {t['appendix']}", ""]
    if cov["slots"]:
        L += [t["coverage"].format(e=cov["explained"], n=cov["slots"], p=pct(cov["share"], False)), ""]
    L.append(f"- {t['definitions']}{p['colon']}" + p["comma"].join(f"{k} `{v}`" for k, v in s["definitions"].items() if v))
    L.append(f"- {t['decisions']}{p['colon']}" + p["semi"].join(f"`{d['table']}` row {d['row']} → {_decision_text(d)}" for d in s["decisions"]))
    L.append(f"- {t['checks']}{p['colon']}" + p["semi"].join(f"{c['check']} {t['pass'] if c['pass'] else t['fail']}" for c in s["checks"]))
    L.append("")
    return "\n".join(L)

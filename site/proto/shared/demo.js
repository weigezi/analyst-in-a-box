// Chart specs, headline wording and the click-through case, shared by both prototypes. All numbers come from AIB_DATA.
(function () {
  const { D, num, pct, money, wan, md, range, T, zh } = window.AIB;
  const X = D.derived, P = D.derived_py, Q = D.qualify;
  const W = (a, b) => (zh() ? a : b);
  const roundUp = (v, step) => Math.ceil(v / step) * step;
  const f0 = D.factors[0], f1 = D.factors[1];
  const mkWeeks = P.marketplace_weeks;
  const mkMark = mkWeeks.findIndex((w) => w.start <= D.cause.start && D.cause.start < addDays(w.start, 7));
  function addDays(iso, n) { const d = new Date(iso + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); }
  const share = (x) => Math.round(x * 100) + "%";
  const approx = (x) => (zh() ? "约 " : "about ") + money(Math.round(x / 100) * 100, true);
  const holidayNames = [...new Set(D.weeks.flatMap((w) => w.holiday.map((h) => T(h))))];
  const noHoliday = !P.days.current.some((d) => d.holiday.length) && !P.days.base.some((d) => d.holiday.length);

  const text = {
    headline: () => W(`上周营收同比 ${pct(D.total.growth)}：${T(X.top.label)}少了 ${wan(-P.marketplace.delta)}，网页多了 ${wan(stats.webDelta)}`,
                      `Revenue ${pct(D.total.growth)} on last year: the ${T(X.top.label).toLowerCase()} lost ${wan(-P.marketplace.delta)}, the website gained ${wan(stats.webDelta)}`),
    unusualShort: () => W(`比平时低得多：离常态的距离是平时波动的 ${X.times_usual_wobble.toFixed(1)} 倍，超过 ${X.times_needed.toFixed(1)} 倍才算异常`,
                          `Far below normal: ${X.times_usual_wobble.toFixed(1)} times the usual wobble away from the usual pace; ${X.times_needed.toFixed(1)} counts as unusual`),
    channel: () => W(`${T(X.top.label)}少了 ${wan(-P.marketplace.delta)}，其他渠道多了 ${wan(P.others.delta)}，抵掉一部分`,
                     `The ${T(X.top.label).toLowerCase()} lost ${wan(-P.marketplace.delta)}; the other channels added ${wan(P.others.delta)}, offsetting part of it`),
    others: () => W(`去掉${T(X.top.label)}，网页加 App 从 ${money(P.others.base)} 到 ${money(P.others.cur)}，涨了 ${pct(P.others.growth, 1, false)}，和平时的 ${pct(P.usual_growth)} 差不多；${T(X.top.label)}本身从 ${money(P.marketplace.base)} 到 ${money(P.marketplace.cur)}，跌了 ${pct(-P.marketplace.growth, 1, false)}。`,
                    `Without the ${T(X.top.label).toLowerCase()}, web and app went from ${money(P.others.base)} to ${money(P.others.cur)}, up ${pct(P.others.growth, 1, false)}, close to the usual ${pct(P.usual_growth)}; the ${T(X.top.label).toLowerCase()} itself went from ${money(P.marketplace.base)} to ${money(P.marketplace.cur)}, down ${pct(-P.marketplace.growth, 1, false)}.`),
    cause: () => W(`${md(D.cause.start)}起，${T(D.cause.text)}`, `From ${md(D.cause.start)}: ${T(D.cause.text)}`),
    regions: () => W(`${T(X.top.label)}下面四个大区一起跌，各跌 ${share(X.region_fall_min)}～${share(X.region_fall_max)}，没有哪个区特别突出`,
                     `All four regions on the ${T(X.top.label).toLowerCase()} fell ${share(X.region_fall_min)}–${share(X.region_fall_max)}; none stands out`),
    factorNote: () => W(`怎么分的：两项各按自己变化的大小（取对数后的比例）分总变化，所以两段加起来正好等于总变化，方法名称见报告附录。订单数降 ${pct(-f0.growth, 1, false)}、客单价降 ${pct(-f1.growth, 1, false)}，所以大约是六四开。`,
                        `How it is split: each factor takes a share of the change in proportion to the log of its own ratio (the LMDI method), so the two parts add up exactly. Orders fell ${pct(-f0.growth, 1, false)}, order value ${pct(-f1.growth, 1, false)}: roughly 60/40.`),
    usual: () => W(`照平时 ${pct(P.usual_growth)} 的速度，这周本该 ${approx(P.expected_at_usual)}；实际 ${money(D.total.delta, true)}。差出来的 ${approx(P.unusual_part)} 是这次的异常部分，和${T(X.top.label)}的 ${money(P.marketplace.delta, true)} 接近，但两者口径不同，只能说大小相当。这是估计。`,
                   `At the usual ${pct(P.usual_growth)} pace the week would have added ${approx(P.expected_at_usual)}; it actually changed ${money(D.total.delta, true)}. The gap, ${approx(P.unusual_part)}, is the unusual part, close to the ${T(X.top.label).toLowerCase()}'s ${money(P.marketplace.delta, true)}. An estimate.`),
  };

  const spec = {
    spark: () => ({ series: D.weeks.map((w) => w.yoy), grey: X.holiday_idx, label: W("过去 26 周加本周的同比增速", "Year-on-year growth, 26 weeks plus this week") }),
    factors: () => ({ rows: D.factors.map((f) => ({ label: T(f.label), value: f.contribution }))
                       .concat([{ kind: "total", label: W("合计", "Total"), value: D.total.delta }]),
                      label: W("营收变化按订单数和客单价拆开", "Revenue change by orders and order value") }),
    usual: () => ({ rows: [{ label: W("照平时速度本该", "At the usual pace"), value: P.expected_at_usual },
                           { label: W("异常部分（估计）", "Unusual part (est.)"), value: P.unusual_part },
                           { kind: "total", label: W("实际变化", "Actual change"), value: D.total.delta }],
                    label: W("实际变化 = 照平时速度本该 + 异常部分", "Actual change split into usual pace and unusual part") }),
    band: () => ({ weeks: D.weeks, lines: Q.band, iqr: P.history_iqr, grey: X.holiday_idx,
                   holidayLabel: W("中秋送礼周两年错开", "Mid-Autumn week shifted"),
                   lastLabel: W("本周 ", "This week ") + pct(D.total.growth),
                   lastSub: W(`常态的 ${X.times_usual_wobble.toFixed(1)} 倍波动之外`, `${X.times_usual_wobble.toFixed(1)}× the usual wobble`),
                   label: W("每周营收同比增速", "Weekly revenue growth") }),
    channel: () => ({ domain: roundUp(Math.abs(P.marketplace.delta), 20000),
                      rows: D.cuts[0].segments.map((s, j) => ({ label: T(s.label), value: s.delta, emph: j === 0 })),
                      label: W("各渠道营收变化", "Revenue change by channel") }),
    regions: () => {
      const segs = D.cuts[1].segments, sh = P.region_share_of_marketplace;
      return { domain: roundUp(Math.abs(P.marketplace.delta), 20000),
               cols: W(["变化", "同比", "占平台降幅"], ["Change", "YoY", "Share of drop"]),
               rows: [{ label: T(X.top.label), value: P.marketplace.delta, cells: [money(P.marketplace.delta, true), pct(P.marketplace.growth), "100%"] }]
                 .concat(segs.map((s) => ({ indent: true, label: T(s.label), value: s.delta,
                   cells: [money(s.delta, true), pct(s.delta / s.base), share(sh[s.key])] }))),
               label: W("电商平台和它下面四个大区", "The marketplace and its four regions") };
    },
    weekly: () => ({ weeks: mkWeeks, markAt: mkMark, markLabel: md(D.cause.start),
                     curLabel: W("今年", "This year"), baseLabel: W("去年同期", "Last year"),
                     label: W("电商平台每周营收", "Weekly marketplace revenue") }),
    days: () => ({ current: P.days.current, base: P.days.base, curLabel: W("本周", "This week"), baseLabel: W("去年同周", "Last year"),
                   note: noHoliday ? W("两段都是周一到周日，都不含节日。格子里是当天营收。", "Both run Monday to Sunday with no holiday. Each cell is that day's revenue.")
                                   : W("有节日的日子已标出。", "Holidays are marked.") }),
  };

  const before = mkWeeks[mkMark - 1], after = mkWeeks[mkMark];
  // Recomputed from D.weeks (the same 26 history weeks the run used) so the page can say what changes without the holiday weeks.
  const hist = D.weeks.filter((w) => w.start < D.current[0]);
  const median = (a) => { const s = [...a].sort((p, q) => p - q), n = s.length; return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2; };
  const wobbles = (v, a) => { const m = median(a), mad = median(a.map((x) => Math.abs(x - m))); return Math.abs(v - m) / (1.4826 * mad); };
  const histAll = hist.map((w) => w.yoy), histPlain = hist.filter((w) => !w.holiday.length).map((w) => w.yoy);
  const eventWeek = hist.find((w) => w.start === after.start);
  const app = D.cuts[0].segments.find((s) => s.key === "app"), web = D.cuts[0].segments.find((s) => s.key === "web");
  const stats = { holidayWeeks: hist.length - histPlain.length, plainTimes: wobbles(D.total.growth, histPlain),
                  eventWeekGrowth: eventWeek && eventWeek.yoy, eventWeekTimes: eventWeek && wobbles(eventWeek.yoy, histAll),
                  appGrowth: app.cur / app.base - 1, webDelta: web.delta };
  const steps = () => [
    { t: W("先对齐：本周对比去年同周", "Line up: this week against the same week last year"),
      b: W(`本周 ${range(D.current)}，对比去年同一周的同样七天 ${range(D.base)}。营收 ${money(D.total.base)} → ${money(D.total.cur)}，${pct(D.total.growth)}。`,
           `This week, ${range(D.current)}, against the same seven weekdays a year earlier, ${range(D.base)}. Revenue ${money(D.total.base)} → ${money(D.total.cur)}, ${pct(D.total.growth)}.`),
      chart: ["dayPairs", spec.days()] },
    { t: W("算不算异常：跟自己过去 26 周比", "Is it unusual? Against its own last 26 weeks"),
      b: W(`平时每周同比大约 ${pct(P.usual_growth)}。本周 ${pct(D.total.growth)}，离常态的距离是平时波动的 ${X.times_usual_wobble.toFixed(1)} 倍，超过 ${X.times_needed.toFixed(1)} 倍才算异常，所以算。灰色的 ${stats.holidayWeeks} 周是${holidayNames[0] || "节日"}两年没落在同一周，同比失真，画成灰色提醒你别直接看；算平时水平时它们还在里面，去掉它们，本周离常态是 ${stats.plainTimes.toFixed(1)} 倍，结论不变。`,
           `Usually the week grows about ${pct(P.usual_growth)} on last year. This week is ${pct(D.total.growth)}: ${X.times_usual_wobble.toFixed(1)} times the usual wobble away, and ${X.times_needed.toFixed(1)} counts as unusual. The ${stats.holidayWeeks} grey weeks are the Mid-Autumn week falling on different dates, so their year-on-year is distorted. They are still in the usual level; without them this week is ${stats.plainTimes.toFixed(1)} times away, same conclusion.`),
      chart: ["band", spec.band()] },
    { t: W("和自己平时的速度比，异常部分有多少", "Against its usual pace, how much is unusual"),
      b: text.usual(), chart: ["waterfall", spec.usual()] },
    { t: W("按公式拆：营收 = 订单数 × 客单价", "By formula: revenue = orders × order value"),
      b: W(`订单数 ${num(f0.base)} → ${num(f0.cur)}，贡献 ${money(f0.contribution, true)}；客单价 ${money(f1.base, false, 2)} → ${money(f1.cur, false, 2)}，贡献 ${money(f1.contribution, true)}。`,
           `Orders ${num(f0.base)} → ${num(f0.cur)}, ${money(f0.contribution, true)}; order value ${money(f1.base, false, 2)} → ${money(f1.cur, false, 2)}, ${money(f1.contribution, true)}.`),
      chart: ["waterfall", spec.factors()], note: text.factorNote() },
    { t: W(`按渠道拆：${T(X.top.label)}少了 ${wan(-P.marketplace.delta)}，网页多了 ${wan(stats.webDelta)}`, `By channel: the ${T(X.top.label).toLowerCase()} lost ${wan(-P.marketplace.delta)}, the website gained ${wan(stats.webDelta)}`),
      b: text.others() + W(` 再看${T(X.top.label)}里面：四个大区各跌 ${share(X.region_fall_min)}～${share(X.region_fall_max)}，没有哪个区特别突出，拆到这里就够了。`,
                           ` Inside the ${T(X.top.label).toLowerCase()}, the four regions each fell ${share(X.region_fall_min)}–${share(X.region_fall_max)}; none stands out, so it stops there.`),
      chart: ["diverging", spec.channel()] },
    { t: W("原因，和谁该做什么", "Why, and who acts"),
      b: W(`${text.cause()} ${T(X.top.label)}每周营收在 ${md(after.start)}那周断开：${md(before.start)}那周 ${wan(before.revenue)}，${md(after.start)}那周 ${wan(after.revenue)}，本周 ${wan(P.marketplace.cur)}。出处是系统记录，已确认。<br><b>${T(D.action.owner)}</b>：${T(D.action.text)}`,
           `${text.cause()} Weekly ${T(X.top.label).toLowerCase()} revenue breaks in the week of ${md(after.start)}: ${wan(before.revenue)} in the week of ${md(before.start)}, ${wan(after.revenue)} in the week of ${md(after.start)}, ${wan(P.marketplace.cur)} this week. Source: system record, confirmed.<br><b>${T(D.action.owner)}</b>: ${T(D.action.text)}`),
      chart: ["weekly", { ...spec.weekly(), height: 200 }] },
  ];

  function stepper(root, reportHref) {
    const S = steps();
    let i = 0;
    root.innerHTML = `<ol class="st-list">${S.map((s, k) => `<li><button type="button" data-k="${k}"><span class="st-n">${k + 1}</span><span class="st-t">${s.t}</span></button></li>`).join("")}</ol>
      <div class="st-panel"><p class="st-count"></p><h3 class="st-title"></h3><p class="st-body"></p><div class="st-chart"></div>
      <div class="st-nav"><button type="button" class="btn ghost st-prev">${W("上一步", "Back")}</button>
      <button type="button" class="btn st-next">${W("下一步", "Next")}</button>
      <button type="button" class="btn link st-skip">${W("直接看结果", "Skip to the result")}</button>
      <a class="btn link st-report" href="${reportHref}">${W("看完整报告 →", "Full report →")}</a></div></div>`;
    const $ = (q) => root.querySelector(q);
    function show(k) {
      i = Math.max(0, Math.min(S.length - 1, k));
      const s = S[i];
      root.querySelectorAll(".st-list button").forEach((b, j) => { b.classList.toggle("on", j === i); b.classList.toggle("done", j < i); b.setAttribute("aria-current", j === i ? "step" : "false"); });
      $(".st-count").textContent = W(`第 ${i + 1} 步，共 ${S.length} 步`, `Step ${i + 1} of ${S.length}`);
      $(".st-title").textContent = s.t;
      $(".st-body").innerHTML = s.b;
      const c = $(".st-chart");
      c.innerHTML = "";
      c.hidden = !s.chart;
      if (s.chart) window.AIBCharts.draw(c, s.chart[0], s.chart[1]);
      if (s.note) c.insertAdjacentHTML("beforeend", `<p class="st-note">${s.note}</p>`);
      $(".st-prev").disabled = i === 0;
      $(".st-next").hidden = i === S.length - 1;
      $(".st-skip").hidden = i === S.length - 1;
      $(".st-report").hidden = i !== S.length - 1;
    }
    root.addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      if (b.dataset.k) show(+b.dataset.k);
      else if (b.classList.contains("st-prev")) show(i - 1);
      else if (b.classList.contains("st-next")) show(i + 1);
      else if (b.classList.contains("st-skip")) show(S.length - 1);
    });
    show(0);
  }

  window.AIBDemo = { spec, text, stepper, mkMark, before, after, stats };
})();

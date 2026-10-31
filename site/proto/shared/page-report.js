// Builds the revenue report article for either prototype. Same words and numbers in A and B; only the stylesheet differs.
(function () {
  const { D, num, pct, money, wan, md, range, T } = window.AIB;
  const { spec, text, before, after, stats } = window.AIBDemo;
  const C = window.AIBCharts;
  const X = D.derived, P = D.derived_py, Q = D.qualify;
  const f0 = D.factors[0], f1 = D.factors[1];
  const ph = (...parts) => parts.map((p) => `<span class="ph">${p}</span>`).join("");
  const phs = (s) => ph(...s.split(/(?<=[，：；])/));
  const mk = T(X.top.label);
  const share = (x) => Math.round(x * 100) + "%";
  const approx = (x) => "约 " + money(Math.round(x / 100) * 100, true);
  const est = `<span class="est">估计</span>`;

  const html = `
<p class="r-meta"><a href="index.html">首页</a> / 样例报告 · ${T(D.shop)}<br><span class="tnum">本期 ${range(D.current)}，对比去年同周 ${range(D.base)}</span></p>
<h1 class="r-title">${phs(text.headline())}</h1>
<p class="r-dek">${text.cause().replace(/。$/, "")}。${T(D.action.owner)}需要和平台重谈，或者把预算挪到自有渠道。</p>

<div class="r-summary">
  <div class="r-figure"><div class="big neg">${pct(D.total.growth)}</div>
    <div class="big-sub tnum">${money(D.total.base)} → ${money(D.total.cur)}，${money(D.total.delta, true)}</div>
    <div class="r-spark" id="r-spark"></div><div class="r-sparkcap">每周同比，过去 26 周 + 本周；灰色是中秋送礼周两年错开的几周</div></div>
  <ul class="r-points">
    <li><b>比平时低得多。</b>平时每周同比约 ${pct(P.usual_growth)}，这周 ${pct(D.total.growth)}；离常态的距离是平时波动的 ${X.times_usual_wobble.toFixed(1)} 倍，超过 ${X.times_needed.toFixed(1)} 倍才算异常。</li>
    <li><b>只有${mk}在跌。</b>${text.channel()}。其他渠道合计涨了 ${pct(P.others.growth, 1, false)}，和平时差不多。</li>
    <li><b>原因有记录。</b>${text.cause()}出处是系统记录，已确认。</li>
  </ul>
</div>

<section class="r-sec" id="s-formula">
  <h2>${ph(`少的钱里，大约六成是订单变少，`, `四成是客单价变低`)}</h2>
  <p>营收 = 订单数 × 客单价。订单数 ${num(f0.base)} → ${num(f0.cur)}（${pct(f0.growth)}），贡献 ${money(f0.contribution, true)}；客单价 ${money(f1.base, false, 2)} → ${money(f1.cur, false, 2)}（${pct(f1.growth)}），贡献 ${money(f1.contribution, true)}。</p>
  <figure class="r-fig"><figcaption class="r-figtitle">营收变化按两项拆开（单位：元）</figcaption><div id="r-factors"></div>
    <p class="r-note">${text.factorNote()}</p></figure>
</section>

<section class="r-sec" id="s-unusual">
  <h2>${ph("这一周比平时低得多，", "不是正常波动")}</h2>
  <p>把过去 26 周每周的同比增速排开，中间值是 ${pct(Q.median)}。本周 ${pct(D.total.growth)}，离这个中间值的距离是平时波动幅度的 ${X.times_usual_wobble.toFixed(1)} 倍；超过 ${X.times_needed.toFixed(1)} 倍才算异常，所以算。灰色的 ${stats.holidayWeeks} 周是中秋送礼周两年落在不同的周，同比失真，画成灰色提醒你别直接看。算平时水平时它们还在里面；去掉它们，本周离常态是 ${stats.plainTimes.toFixed(1)} 倍，结论不变。</p>
  <figure class="r-fig wide"><figcaption class="r-figtitle">每周营收同比增速</figcaption><div id="r-band"></div>
    <ul class="legend"><li><i class="l-iqr"></i>过去 26 周中间那一半（${pct(P.history_iqr[0])} 至 ${pct(P.history_iqr[1])}）</li>
      <li><i class="l-th"></i>低于下面这条线才算异常（${pct(Q.band[0])}），高于上面这条也算（${pct(Q.band[1])}）</li>
      <li><i class="l-hol"></i>中秋送礼周两年错开，同比失真，别直接看</li></ul></figure>
  <h3>${ph("和自己平时的速度比，", "异常的部分约 7.8 万元")} ${est}</h3>
  <p>${text.usual()}</p>
  <figure class="r-fig"><figcaption class="r-figtitle">实际变化 = 照平时速度本该 + 异常部分（单位：元）</figcaption><div id="r-usual"></div>
    <p class="r-note">同期大盘涨得比这家店平时快，按大盘算会把异常部分算大，所以正文用店铺自己的速度，按大盘算的数放在附录。</p></figure>
</section>

<section class="r-sec" id="s-where">
  <h2>${phs(`去掉${mk}，其他渠道涨了 ${pct(P.others.growth, 1, false)}`)}</h2>
  <p>${text.others()}</p>
  <div class="r-stats">
    <div><p class="r-stat-l">${mk}</p><p class="r-stat-v neg">${pct(P.marketplace.growth)}</p><p class="r-stat-s">${money(P.marketplace.base)} → ${money(P.marketplace.cur)}</p></div>
    <div><p class="r-stat-l">网页 + App</p><p class="r-stat-v pos">${pct(P.others.growth)}</p><p class="r-stat-s">${money(P.others.base)} → ${money(P.others.cur)}；平时约 ${pct(P.usual_growth)}</p></div>
  </div>
  <figure class="r-fig"><figcaption class="r-figtitle">${phs(text.regions())}</figcaption><div id="r-regions"></div>
    <p class="r-note">「同比」是每个区自己跌了多少<span class="bt-opt">；「占平台降幅」是它占${mk}少掉的钱的多少，四个区加起来是 100%</span>。没有哪个区占到一半，拆到这一层就够了。</p></figure>
</section>

<section class="r-sec" id="s-why">
  <h2>${ph("原因有记录：", "平台调整了费用条款")}</h2>
  <div class="evidence big-ev"><span class="tag">事件 · ${md(D.cause.start)}起 · 出处：${T(D.cause.source)} · 已确认</span>
    <p>${T(D.cause.text)}</p>
    <p class="ev-fit">对得上这次变化：记录说的正是${mk}，也就是少掉钱的地方；时间在本周之前，而且${mk}每周营收正好在 ${md(after.start)}那周断开：${md(before.start)}那周 ${wan(before.revenue)}，${md(after.start)}那周 ${wan(after.revenue)}，本周 ${wan(P.marketplace.cur)}。</p></div>
  <figure class="r-fig wide"><figcaption class="r-figtitle">${mk}每周营收，实线今年，虚线去年同期（单位：元）</figcaption><div id="r-weekly"></div></figure>
</section>

<section class="r-sec" id="s-unchecked">
  <h2>这次没核实的</h2>
  <ul class="r-list">
    <li>网页同期涨了 ${pct(P.web_growth)}，比平时快。是不是有${mk}的客人转到网页来买了？这次没有验证，要按客人对一下才知道。如果是，${mk}真正流失的钱比 ${wan(-P.marketplace.delta)} 少。</li>
    <li>App 只涨了 ${pct(stats.appGrowth, 1, false)}，比平时的 ${pct(P.usual_growth)} 慢得多。这可能是另一件事，不在这次的变化里，这份报告没有查。</li>
    <li>${md(after.start)}那周整店已经是 ${pct(stats.eventWeekGrowth)}，离常态 ${stats.eventWeekTimes.toFixed(2)} 倍，差一点没过 3.5 倍的线，所以晚了一周才报出来。</li>
    <li>「平时的速度」用的是过去 26 周的中间值 ${pct(P.usual_growth)}，是估计。换成别的算法，异常部分的大小会变，但「只有${mk}在跌」这个结论不变。</li>
  </ul>
</section>

<section class="r-sec" id="s-act">
  <h2>谁该做什么</h2>
  <table class="r-table"><thead><tr><th>负责人</th><th>做什么</th><th>依据</th></tr></thead>
    <tbody><tr><td><b>${T(D.action.owner)}</b></td><td>${T(D.action.text)}</td><td class="tnum">${mk}少了 ${wan(-P.marketplace.delta)}；平台条款变化有记录</td></tr></tbody></table>
</section>

<details class="r-appendix"><summary>附录：专业名称、门槛和出处</summary>
  <table class="r-table small"><thead><tr><th>正文里的说法</th><th>专业名称和数值</th><th>出处</th></tr></thead><tbody>
    <tr><td>离常态的距离是平时波动的几倍</td><td class="tnum">稳健 z 值 ${num(Q.z, 2)}，用中位数和中位数绝对偏差（MAD × 1.4826）算</td><td>Iglewicz &amp; Hoaglin (1993)，How to Detect and Handle Outliers</td></tr>
    <tr><td>超过 3.5 倍才算异常</td><td class="tnum">|z| ≥ ${num(Q.z_high, 1)}，图上两条虚线 = 中位数 ± 3.5 × 1.4826 × MAD</td><td>同上；写在配置文件里</td></tr>
    <tr><td>拆到哪一层停</td><td class="tnum">一项占变化一半以上就往下拆；${mk}这一项比总变化还大，所以拆；大区一层最大的一项占 ${share(Math.max(...Object.values(P.region_share_of_marketplace)))}，停</td><td>演示店设置</td></tr>
    <tr><td>六四开</td><td>LMDI（对数平均迪氏指数）分解，两项之和严格等于总变化</td><td>Ang (2005)，The LMDI approach to decomposition analysis</td></tr>
    <tr><td>按大盘算</td><td class="tnum">同期大盘 ${pct(Q.market_growth)}，照大盘走本该 ${money(X.expected_market, true)}，差出 ${money(Q.own_part, true)}</td><td>演示店的大盘数据</td></tr>
  </tbody></table>
  <h4>交出报告前的自检（全部通过）</h4>
  <ul class="r-checks">${D.checks.map((c) => `<li class="${c.pass ? "ok" : "no"}">${T(c.label)}</li>`).join("")}</ul>
  <p class="r-note">每个数字都由脚本算出。演示店「花果篮」是虚构的，数据由程序生成。</p>
</details>`;

  document.getElementById("report").innerHTML = html;
  const $ = (id) => document.getElementById(id);
  C.draw($("r-spark"), "spark", { ...spec.spark(), height: 44 });
  C.draw($("r-factors"), "waterfall", spec.factors());
  C.draw($("r-band"), "band", { ...spec.band(), height: 280 });
  C.draw($("r-usual"), "waterfall", spec.usual());
  C.draw($("r-regions"), "barTable", spec.regions());
  C.draw($("r-weekly"), "weekly", { ...spec.weekly(), height: 240 });

  const toc = $("toc");
  if (toc) toc.innerHTML = [...document.querySelectorAll(".r-sec")].map((s) => `<a href="#${s.id}">${s.querySelector("h2").textContent}</a>`).join("");
})();

// Fills the home page of either prototype: answer card, "where it says it is unsure", click-through case, session, copy.
(function () {
  const { D, num, pct, money, wan, T, zh: isZh, bind } = window.AIB;
  const { spec, text, stepper, before, after } = window.AIBDemo;
  const C = window.AIBCharts;
  const zh = isZh();
  const X = D.derived, P = D.derived_py, U = D.uncertain;
  const $ = (id) => document.getElementById(id);
  const set = (id, s, html) => { if ($(id)) $(id)[html ? "innerHTML" : "textContent"] = s; };

  bind();
  set("ans-title", text.headline());
  set("ans-chip", zh ? "比平时低得多" : "Far below normal");
  set("ans-cause", text.cause());
  if ($("ans-spark")) C.draw($("ans-spark"), "spark", { ...spec.spark(), height: 40 });
  if ($("ans-cut")) C.draw($("ans-cut"), "diverging", spec.channel());

  // ---- where it says it is unsure (v0.2 engine, built test data)
  const days = U.missing.days.map((d) => window.AIB.md(d));
  set("u-noise", zh
    ? `离常态的距离只有平时波动的 ${Math.abs(U.noise.z).toFixed(1)} 倍，在正常范围内，不往下找原因。一份 ${U.noise.weeks} 周的纯噪音数据，逐周问它，${U.noise.weeks} 周里有 ${U.noise.weeks_drilled} 周它误报、往下拆了。`
    : `Only ${Math.abs(U.noise.z).toFixed(1)} times the usual wobble away: within the usual range, so it does not look for a cause. Asked week by week over ${U.noise.weeks} weeks of pure-noise data, it wrongly drilled in ${U.noise.weeks_drilled} of them.`);
  set("u-missing", zh
    ? `这份考题数据里，${days.join("和 ")}没有一笔订单。它先说数据有问题，不出结论：缺数据造成的「下跌」不是生意变差。`
    : `In this test data there are no orders at all on ${days.join(" and ")}. It says the data is in doubt and gives no conclusion: a fall made by missing days is not a business fall.`);
  set("u-dup", zh
    ? `${num(U.duplicate.rows)} 笔订单里有 ${num(U.duplicate.duplicates)} 笔订单编号重复，像是同一周导入了两次。它报出重复，不出结论。`
    : `${num(U.duplicate.duplicates)} of ${num(U.duplicate.rows)} orders share an order number, as if the week was loaded twice. It reports the duplicates and gives no conclusion.`);

  // ---- prototype B: plain-language progress instead of a command line
  if ($("sess-r1")) {
    const rows = zh
      ? [["检查日期对齐", "两段都是周一到周日，没有节日"],
         ["和过去 26 周比", `比平时低得多，是平时波动的 ${X.times_usual_wobble.toFixed(1)} 倍`],
         ["按渠道拆", `${T(X.top.label)}少了 ${wan(-P.marketplace.delta)}，其他渠道在涨`],
         ["找原因", `${window.AIB.md(D.cause.start)}平台改了费用条款，有记录`]]
      : [["Check the dates line up", "both Monday to Sunday, no holiday"],
         ["Compare with 26 weeks", `far below normal, ${X.times_usual_wobble.toFixed(1)}× the usual wobble`],
         ["Break down by channel", `${T(X.top.label)} lost ${wan(-P.marketplace.delta)}, the rest grew`],
         ["Find the reason", `${window.AIB.md(D.cause.start)}: new marketplace fee terms, on record`]];
    rows.forEach(([a, b], k) => set("sess-r" + (k + 1), `<b>${a}</b><span>${b}</span>`, true));
    const items = [...document.querySelectorAll(".session .reveal, .session .progress li")];
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    $("replay").addEventListener("click", () => {
      items.forEach((el) => el.classList.add("hidden"));
      items.forEach((el, k) => setTimeout(() => el.classList.remove("hidden"), reduce ? 0 : 160 + k * 280));
    });
  }

  if ($("stepper")) stepper($("stepper"), "report.html");

  document.querySelectorAll("[data-copy]").forEach((b) => {
    const label = b.textContent;
    b.addEventListener("click", async () => {
      const box = document.getElementById(b.dataset.copy) || b.closest(".install");
      try { await navigator.clipboard.writeText(box.querySelector(".k").textContent); b.textContent = zh ? "已复制" : "Copied"; }
      catch (e) { b.textContent = zh ? "请手动选中复制" : "Select to copy"; }
      setTimeout(() => (b.textContent = label), 1800);
    });
  });
})();

# analyst-in-a-box

[English](SKILL.md)

把一件事做好：**这个数为什么变了，接下来该谁去做什么。**
所有计算都由脚本完成。你的工作是：定题、跑脚本、和用户对话，并且把用户教你的东西记下来，下次答得更好。

本文件是 [SKILL.md](SKILL.md) 的中文版，章节一一对应；AI 工具加载的是英文入口，两者内容相同。

## 先读这几条

1. **不要自己算数。** 告诉用户的每个数都来自脚本输出。模型做拆解计算容易出错；脚本会检查每次拆解的各项之和是否等于总变化。
2. **不要从列名或业务词的字面猜它是什么意思。** 工作目录里没有的，就问。猜错一列，后面所有结果都会悄悄跟着错。
3. **阈值属于用户。** 「什么算单点」「什么算异常」是业务判断。工作目录会连同出处一起存下来；不要在对话里自己编一个。
4. **外部事件只是推测。** 天气、新闻、竞品只能证明时间对得上。怎么措辞由运行结果决定（三道检查：时间、影响的那一块、量级）。
5. **用户教你的东西一律走 `correct`。** 它会带着用户原话记下来，并生成一道回归题，skill 就不会悄悄忘掉。

## 怎么跑脚本

所有命令都在本 skill 文件夹里运行，输出 JSON：

```bash
python3 scripts/aib_cli.py <命令> --workspace <目录> ...
```

如果 `import pandas, yaml` 报错，先安装：`pip install -r scripts/requirements.txt`
（或者在命令前加 `uv run --with-requirements scripts/requirements.txt`）。

**工作目录**存一家公司自己的知识（指标树、世界、纠正记录）。放在用户自己的文件夹里，不要放进本 skill；
位置不明显时问用户，默认 `./aib-workspace`。

## 1. 第一次使用：从一张表到第一份答案

目标：一次对话之内，用户就看到一份算得对、而且说出一件他不知道的事的归因。

1. `init <数据文件> --workspace <目录> --lang zh|en` 读表，返回一组问题。
2. 把这些问题**做成选择题**，一次问几个，用用户的语言。不要根据列名预先替用户选；把脚本给的例子一起给用户看，方便他认出是哪一列。
3. 把答案按问题的 `id` 写进一个 JSON 文件，运行 `confirm --workspace <目录> --answers <文件>`。它会写好工作目录，并返回 `first_run`。
4. 跑它：`run --workspace <目录> --config '<first_run 的 JSON>'`，然后按第 3 节呈现报告。
5. 可以问，但不要强求：「你一般先看哪个维度？」他的回答记成一条 `set_priority` 纠正（第 4 节）。业务知识**用到时才问**，不要开头就做一轮问卷。

## 2. 回答一个问题

先把问题对应成一次运行，再调用 `run`。细节和特殊情况见 [references/questions.zh.md](references/questions.zh.md)。

| 用户问 | 怎么跑 |
|---|---|
| 「上周营收为什么跌了？」 | `--metric revenue --current <周一> <周日> --base yoy`（用户说「比上周」就用 `pop`） |
| 「华东为什么跌了？」 | 再加 `--filter region=east` |
| 「Q3 增速为什么比 Q2 低？」 | 二阶，比两个时间段：`--current <Q3> --base yoy --previous` |
| 「线下为什么比线上涨得快？」 | 二阶，比维度两侧：`--compare <id>`；`model.yaml` 里没有这组对比就先加上 |
| 「访客涨了，转化率却跌了」 | 一阶；报告里「按公式拆」那一段就是答案 |

工作目录里没有这个指标、维度或对比，就直接说没有并问用户；不要拿另一个相近的凑。

## 3. 呈现结果

一次运行会写出 `report.zh.md`、`report.en.md`、`record.json` 和图。按用户的语言给报告；报告已经按
结论 → 算不算异常 → 拆解 → 为什么 → 谁该做什么 排好。数字原样用，不要换一种舍入，也不要重算。告诉用户图在哪。
结构主导和指标主导怎么讲、占比超过 100% 怎么讲、推测怎么讲，见 [references/report.zh.md](references/report.zh.md)。

然后处理运行结果里说缺的东西：

- **`gaps`**：数据上看到了变化，但没人解释过。问一句大白话：「新客的客单价降了，你知道为什么吗？」把回答记下来（第 4 节），再跑一次。
- **`to_confirm`**：只是「待确认」的条目，包括外部事件。问用户要不要确认。
- **`blocked: true`**：交付前自检没过。告诉用户是哪一项；不要给结论。

## 4. 从用户那里学

用户纠正你或者解释了什么，用 `correct --workspace <目录> --json '<纠正>'` 记下来。`quote` 里放用户原话。
类型有：`add_mechanism`、`add_event`、`add_action`、`add_alias`、`set_priority`、`set_param`、`confirm`、`retire`。
格式和例子见 [references/learning.zh.md](references/learning.zh.md)。

带上 `"run"`（引出这次纠正的那次运行的配置）和 `"slot"`（例如 `customer_type=new`），回归题才能重放。
再跑一次这个问题，让用户看到变化；然后跑 `regress`，证明以前学到的每一条都还在。把覆盖率告诉用户：这是他看到 skill 在进步的方式。

## 5. 外部事件和新闻

缺口看起来像外部原因，或者用户提到天气、节假日、政策、竞品、国际形势时：

1. 用你自己的联网搜索，在变化发生的那几天里、按受影响的地区或品类去查。
2. 最多挑三条相关的。每条记成一条 `add_event` 纠正：`kind: external`，`source: {kind: document, ref: <链接>}`，`status: proposed`，以及它会影响到的实体。
3. 再跑一次。三道检查决定措辞：「已过三道检查」还是「时间上吻合，未证实」。不要凭自己的判断把新闻说成原因。

日历和连续的外部数据（天气、汇率、行业大盘）是工作目录里的数据来源，见 [references/workspace.zh.md](references/workspace.zh.md)。

## 6. 维护工作目录

- `check` 列出所有问题（不认识的列、缺来源、在数据上不成立的公式）。
- `docs` 从 YAML 重新生成带链接的可读 Markdown，给不读 YAML 的人看。
- `coverage` 按运行列出，有多少处解释能引用到一条记录。
- 只有结构性的改动（加一组对比、加一个数据来源）才直接改 YAML。业务知识走 `correct`，才有出处、有回归题。

## 参考文档

| 文件 | 什么时候读 |
|---|---|
| [references/workspace.zh.md](references/workspace.zh.md) | 读写任何工作目录文件 |
| [references/questions.zh.md](references/questions.zh.md) | 把一个不常见的问题对应成一次运行 |
| [references/operators.zh.md](references/operators.zh.md) | 用户问某个数怎么算的、用的什么方法 |
| [references/report.zh.md](references/report.zh.md) | 呈现报告，讲结构和指标、讲推测 |
| [references/learning.zh.md](references/learning.zh.md) | 记一条纠正 |

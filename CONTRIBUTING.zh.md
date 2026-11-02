# 参与贡献

[English](CONTRIBUTING.md)

谢谢你来看 analyst-in-a-box。眼下最有用的贡献是**拿你自己的数据试一次，把结果告诉我们**：照着[试用指南](docs/trial.zh.md)走，
然后开一个 issue，写它答对了什么、答错了什么、你纠正了什么。

## 代码和文档

- 跑测试：`uv run --frozen pytest -q`。`--frozen` 不会改动 `uv.lock`。
- 每份文档都有中英两份，章节一一对应：`uv run --frozen python tools/bilingual_check.py`。
- 引擎报的每个数都要由脚本算出来，每种拆法的各项加起来都要等于总变化。新增一种方法，旁边要有一个手算的测试。
- 业务知识（原因、机制、负责人）必须写出处和状态。没有这两样的记录不要加，工作区校验会拒收。
- 改演示站：先 `uv run --frozen python site/build.py`，再要求 `node tools/browser-check/check.mjs` 和 `node tools/design-check/run.mjs` 都通过。

## 提交 pull request 之前

写清楚这次改动回答什么问题、你跑了什么、有什么没检查。几个小而分开的改动，比一个大改动好审。

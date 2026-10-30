# 公开数据集：UCI Online Retail

[English](README.md)

虚构店证明的是：skill 能找回已知的原因。这份数据证明另一件事：项目从没见过的真实数据，能走通起步流程，
产出一份通过自检的报告。它没有标准答案，所以证明不了答案对。

## 出处和授权

这里用的是（整理后的数据来自哪个文件，记在 `data/source.json`）：

Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33

授权：Creative Commons Attribution 4.0 International（CC BY 4.0），2026-10-30 在
[数据集页面](https://archive.ics.uci.edu/dataset/352/online+retail) 核过。允许转发和改编，条件是注明出处；
本文件就是出处说明，改动列在下面。

数据内容：一家英国网店的 541,909 条交易明细，主要卖礼品，不少客户是批发商，时间 2010-12-01 至 2011-12-09。
按下面的步骤整理后是 19,960 张发票。

同一家店还有两年的版本 [Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii)
（Chen, D. (2012)，https://doi.org/10.24432/C5CG6D，同样是 CC BY 4.0，2009-12-01 至 2011-12-09），
同一个脚本就能处理，而且能做同比。这次没用它，是因为 2026-10-30 从 UCI 下载这个 45 MB 的文件，
三次都在 26 MB 左右断开，服务器又不支持断点续传。只有一年数据，所以第一次运行拿一周和上一周比，不和去年同周比。

整理后的 `data/invoices.csv.gz`（277 KB）放在本仓库里，测试和演示站不用下载任何东西就能跑；
原始文件不放（`raw/` 已忽略）。

## 改了什么

`prepare.py` 把原始文件整理成一张发票一行（`data/invoices.csv.gz`）：

| 步骤 | 规则 | 规则从哪来 |
|---|---|---|
| 合并两个工作表（仅 Online Retail II） | 两个表在 2010-12-01 至 12-09 重叠；先核对这几天两表的行完全一样（不一样脚本就停下），再只留一份 | [Datapopcorn](https://datapopcorn.ai/blog/total-sales-four-answers) 报告 22,523 行两表都有，所以数据集页面上的 1,067,371 把它们算了两遍；`prepare.py` 运行时会打印它实际看到的重叠行数 |
| 去掉取消的单 | 发票号以「C」开头 | 数据集的字段说明 |
| 只留销售 | 数量和单价都大于零 | 非正数的行是调整，不是销售 |
| 每行收入 | 数量 × 单价 | 字段说明 |
| 一张发票一行 | 收入、件数、行数相加 | — |
| `market` | 国家是英国为 `domestic`，否则 `international` | 「一家在英国注册的无实体店网络零售商」 |
| `country_group` | 收入最多的 8 个国家，其余归为 `Other` | 只为展示 |
| `customer_status` | 客户在数据里的第一张发票为 `first_seen`，之后为 `returning`，没有客户编号为 `guest` | 数据本身；数据第一天以前就买过的客户分不出来 |

从原始文件重新生成：

```bash
curl -L -o demo/public/raw/online_retail.xlsx "https://archive.ics.uci.edu/ml/machine-learning-databases/00352/Online%20Retail.xlsx"
stat -f %z demo/public/raw/online_retail.xlsx       # 下完是 23715344（Linux 用 stat -c %s）
uv run python demo/public/prepare.py
```

要用两年的版本，就从同一个服务器把 `00502/online_retail_II.xlsx` 下到 `raw/`（下完是 45,622,278 字节）；
它在而且完整时，`prepare.py` 优先用它。服务器不支持断点续传，大小不够就重新下。

## skill 怎么在上面跑

`answers.yaml` 里是起步问题的答案，就像一个用户会给的那样；每一列的含义来自数据集的字段说明，不是来自列名。
`tests/test_public.py` 和演示站都按新用户的路子走：`init` → `confirm` → 第一次运行。

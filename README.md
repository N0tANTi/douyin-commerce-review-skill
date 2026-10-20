# 抖音电商经营复盘 Skill

**把经营看板变成有依据、有交付物、可追踪的行动清单。**

适合运营、投手、货品与售后负责人配合 AI 做直播、商品、退款和短视频复盘。当前 v0.2。

`提供数据与目标 → 核对口径 → 找优先问题 → 安排核查与试验 → 下次回收结果`

## 开始使用

1. 将 [`skills/douyin-commerce-review/`](skills/douyin-commerce-review/) 完整目录放到 `~/.codex/skills/`。
2. 在新对话中输入 `$douyin-commerce-review`，附上看板，并说明目标、近期变化和上次做过的动作。
3. 先看首页重点任务，再展开依据；确认负责人和试验条件后执行。业务人员无需运行代码。

## 直接复制的示例

**周复盘：**

> 使用 $douyin-commerce-review 复盘附件中的本周数据。目标是提高退款后的经营贡献，最近换了主推款。请选出最值得先做的几件事，分别说明依据、具体交付物、负责人角色和验收条件；未知信息不要猜。

**退款专项：**

> 使用 $douyin-commerce-review 分析退款。先区分退款阶段与支付批次，告诉我目前能判断什么；列出最少需要补的字段及用途，不要直接把退款归因于尺码或质量。

**追踪上次动作：**

> 使用 $douyin-commerce-review 继续上次复盘，附件包含原计划和执行记录。请逐项判断任务是否完成、效果证据是否充分，以及哪些动作应继续、调整或暂停。把同期促销变化也考虑进去。

短视频复盘可指定“直接成交”或“引流直播”目标，并提供逐视频数据与素材；两种归因分别评价。

## 会得到什么

- **首页重点任务**：为什么先做、交付什么、谁负责。
- **详细动作卡**：来源摘录、候选解释、最小补数、依赖与试验条件。
- **执行反馈**：任务完成与效果分别记录；原始证据可回查。

已支持指定结构的 WorkBuddy 看板 HTML、明确映射的 JSON；任意罗盘/千川 Excel 仍需适配。有成本、订单和素材才能做相应深度分析。建议不会自动更改投放，也不保证增长。

## 想先体验？

安装 Python 3.10+ 后，在仓库根目录运行；无需第三方库、账号或真实店铺数据：

```sh
python examples/run_demo.py --out private/demo
```

打开生成的 `private/demo/decisions.html`，即可查看**完全合成**的示例报告。示例自带来源回放与报告核验；重复运行请换输出目录。

## 结构与进一步说明

| 位置 | 用途 |
|---|---|
| [SKILL.md](skills/douyin-commerce-review/SKILL.md) | AI 的复盘工作流程 |
| [references/](skills/douyin-commerce-review/references/) | 诊断方法、12张知识卡、数据和动作格式 |
| [scripts/](skills/douyin-commerce-review/scripts/) | 数据提取、核验、报告与反馈 |
| [来源说明](skills/douyin-commerce-review/references/sources.md) | 项目借鉴、书籍抽读和官方资料适用范围 |

[技术运行与验证](docs/runbooks/local-review.md) · [当前状态](CURRENT_STATE.md) · [后续计划](ROADMAP.md)

真实数据、报告与书籍留在忽略的 `private/` 或其他私有资料目录。公开仓库仅包含通用实现、说明与合成示例。软件测试验证程序行为，不证明数据真实或动作有效。

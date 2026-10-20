# 抖音电商经营复盘 Skill

离线核对经营看板，区分来源事实、可重算关系和原因假设，输出具体的补数与条件动作。适合业务人员与 Agent 配合做周度复盘。v0.1 是受限输入适配版，不是自动经营或全平台导出解析器。

## 安装与使用

把 `skills/douyin-commerce-review/` 完整目录放入 Agent 的 skills 目录。Codex 默认使用 `~/.codex/skills/`；随后在新一轮对话中使用 `$douyin-commerce-review`。

示例请求：使用该 Skill 复盘附件看板，先核对来源与口径，再给出本周优先动作、补数清单、负责人角色和验收条件。

业务人员使用时，提供本期目标、看板或原表，并说明近期换品、促销、排班等变化；Agent 负责读取和分析。先查看报告里的统计矛盾与补数任务，再确认要执行的试验。下周带回执行记录和同观察龄退款数据，继续复盘。无需自行运行下面的命令。

只读离线试跑（Python 3.10+，无第三方依赖）：

```sh
python skills/douyin-commerce-review/scripts/review.py --input private/dashboard.html --out private/runs/first --as-of 2026-10-20
python skills/douyin-commerce-review/scripts/verify_run.py private/runs/first
```

输出：`review.html` 业务可读报告、`audit.json` 事实与计算定位、`manifest.json` 输入和输出哈希。输出目录已有交付时拒绝覆盖。

正式经营决策由 Agent 按 [决策交付格式](skills/douyin-commerce-review/references/decision-plan.md) 写私有 plan，再渲染并回读：

```sh
python skills/douyin-commerce-review/scripts/compose_decisions.py --run private/runs/first --plan private/plan.json --out private/decisions.html
python skills/douyin-commerce-review/scripts/compose_decisions.py --run private/runs/first --plan private/plan.json --out private/decisions.html --verify
```

这层检查证据归属和报告一致性；文字判断及动作收益仍需业务复核。

## 能力与限制

- 支持 WorkBuddy 导出 HTML 中的 `DATA`、可选 `NEW` 与显式 `NEWKEY`；只解析 JSON，不执行网页脚本。
- 支持遵守 [数据契约](skills/douyin-commerce-review/references/data-contract.md) 的 canonical JSON。Agent/人工映射需要单独回查原表；第一版不能自动识别任意罗盘/千川 Excel/CSV。
- 脚本提供确定性核查与候选动作底稿；完整经营解释仍需 Agent 读取 [Skill](skills/douyin-commerce-review/SKILL.md)，结合业务目标、原表和内容证据完成。
- 不将看板数字自动认定为平台已核验事实，不把数学分解或历史对比当因果证明，不自动改变投放和联系客户。
- 当前来源含四书重点章节的重述方法摘要、项目设计借鉴和已核查官方材料。详见 [来源说明](skills/douyin-commerce-review/references/sources.md)。不提供原书全文，未完整观看的课程不冒充已掌握。

## 验证

```sh
python -m unittest discover -s tests -v
python tools/check_public_payload.py --git-index
```

合成测试和源文件回放只能验证软件行为与来源一致性，不能证明真实数据正确或建议有增量收益。

实际数据、报告、截图和书籍留在忽略的 `private/` 中。公开提交前检查暂存 diff，并可用 `--deny-file private/publish-deny.txt` 检查业务专属标识。Git 忽略规则和自动扫描不能替代人工发布审阅。

项目状态见 [CURRENT_STATE.md](CURRENT_STATE.md)，未完工作见 [ROADMAP.md](ROADMAP.md)。

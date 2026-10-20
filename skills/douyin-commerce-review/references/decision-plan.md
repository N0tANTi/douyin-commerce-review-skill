# 业务决策交付 v2

Agent 根据 audit 和业务背景写私有 plan JSON。v1 仍可回读，新的报告优先用 `schema_version: "2"`。实际数据与经营结果均不公开。

## 根字段

- `summary`：本轮判断与数据范围。`shops: [{key, decisions: [...]}]`，key 必须对应 audit 店铺。
- `business_context`：`objective`、`capacity` 为业务提供的目标/人力预算，未知写 null；`working_assumption` 写本轮建议采用的假设；`recent_changes` 为已知变化的字符串列表，未提供写空列表，不能编造。
- `focus_actions`：首页要突出的稳定动作 ID 列表，通常只选少量最有价值的任务；不是强制所有卡同时执行。

## 每张动作卡

保留 v1 必填字段：

| 字段 | 内容 |
|---|---|
| `title`, `assessment` | 具体问题、简短判断和推断边界 |
| `evidence_ids` | 该店 F 编号的非空列表，原始显示不等于平台核验 |
| `calculation_ids` | 可选 C 编号列表，不能跨店、不能把快照差额改称利润 |
| `hypotheses`, `immediate_steps`, `missing` | 非空字符串列表：候选原因、当前能做的任务、最小补数及其用途 |
| `owner_role`, `due` | 角色及建议时间；不能捏造真实指派 |
| `conditional_test`, `success`, `stop` | 条件试验、效果验收及停止条件 |
| `knowledge_cards` | D01—D12 中相关方法卡列表 |

v2 追加：

| 字段 | 内容 |
|---|---|
| `id`, `priority`, `priority_reason` | 稳定 ASCII ID、P0/P1/P2、优先理由；不要把预测收益写成已知 |
| `deliverable`, `task_acceptance` | 一个可交付产物及任务验收；与经营效果验收分开 |
| `depends_on` | 该店其他动作 ID 列表，可为空。约束后续试验，当前独立核查仍可开始；禁止循环 |
| `data_highlights` | `[{label, ref}]`，ref 来自本卡 F/C 引用。渲染器取原值，不手抄数字；判断文字中的数字仍需人工核查 |
| `experiment` | `primary_metric`、`window`；`baseline`、`target`、`sample_rule`、`cost_limit` 为文字或 null。未知留 null，不伪造统计阈值 |

引用只验证归属与来源，不证明该字段足以支持所写判断。来源位置与候选解释可展开查看，首页突出当前可交付事项。具体可运行的完全合成例子见仓库 `examples/run_demo.py`。

## 运行与回读

```sh
python <skill>/scripts/compose_decisions.py --run <run-dir> --plan <plan.json> --out <decisions.html>
python <skill>/scripts/compose_decisions.py --run <run-dir> --plan <plan.json> --out <decisions.html> --verify
```

## 下次执行反馈

保留原 plan，单独写 feedback JSON。根字段：`schema_version: "1"`、`plan_sha256`（原 plan 文件 SHA-256）、`updates` 列表。每项：

- `action_id`：原稳定 ID，不允许未知、重复动作；未回收动作不推测状态。
- `status`：`todo/doing/done/paused`；`note`：实际执行说明。
- `outcome`：`not_evaluated/insufficient/observed_change`，分别为未评估、证据不足、观察到变化；不存在“已证实因果”的自动选项。
- `evidence: [{path, sha256}]`：相对 feedback 位置或绝对本地路径，回读时验证文件存在及哈希；不自动验证凭据正文真实。
- 标记 `done` 需要交付凭据及 `recorded_at`；标记 `observed_change` 还要求 `status=done`、`window` 和 `comparison`（可比性、同期变化与限制）。任务完成仍可 `outcome=not_evaluated`。

同一 compose 命令增加 `--feedback <feedback.json>`，写到**新的**输出位置，再用相同参数加 `--verify`。校验会重查外部凭据，不覆盖旧报告。完整反馈不必一次齐全，不能因文件可读就宣布经营改善。

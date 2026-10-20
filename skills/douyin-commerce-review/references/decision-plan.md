# 业务决策交付格式

脚本核查底稿之后，由 Agent 根据实际数据写 plan JSON；不把规则底稿当成已完成全部经营分析。业务内容、店铺和证据均只存私有运行目录。

根字段：`schema_version: "1"`、`summary`、`shops: [{key, decisions: [...]}]`。

每条 decision 字段：

- `title`：具体要解决的问题。
- `assessment`：事实和推断边界，拒绝无根据的精确预算。
- `evidence_ids`：audit.json 中该店铺的 F 编号，不能为空。引用是看板字段，不自动等于平台事实。
- `calculation_ids`：可选，该店 C 编号；金额快照不能改称利润。
- `hypotheses`、`immediate_steps`、`missing`：非空字符串列表，分别写候选解释、可落实核查、补数。
- `owner_role`、`due`：角色、建议时间，不杜撰具体负责人和已执行状态。
- `conditional_test`、`success`、`stop`：触发条件、可比试验和成本约束、验收与停止。
- `knowledge_cards`：D01—D12 中与本动作相关的编号。

先挑影响经营决策的少量问题，再加补数顺序；不要为每项指标机械写一条建议。渲染器会从 audit 展示引用值与位置，验证跨店误引并回读输出。它不能验证文字中手工输入的数字或因果，应人工复核，尽量让数字留在证据区。

# 本地复盘与发布

## 前提

Python 3.10+；有权读取的看板导出；清楚账号、周期与输入来源。首次准备离线文件，不需要账号密码、Cookie、API Key 或付费权限。

## 运行

1. 原始输入放 `private/input/`，完整书籍另存用户的私有资料目录。
2. 运行以下 review 命令，输出到新的 `private/runs/<run-name>/`。
3. 运行 verify_run，随后业务审阅关键数字和建议。canonical 输入还需回查外部原表定位。
4. 记录对账缺口、动作状态和适用窗口，不以脚本成功声称经营改善。

```sh
python skills/douyin-commerce-review/scripts/review.py --input private/input/dashboard.html --out private/runs/first --as-of 2026-10-20
python skills/douyin-commerce-review/scripts/verify_run.py private/runs/first
```

canonical JSON 额外传 `--format canonical`；需要单独回读外部原表验证映射。Agent 按 [v2 动作格式](../../skills/douyin-commerce-review/references/decision-plan.md) 写私有 plan：

```sh
python skills/douyin-commerce-review/scripts/compose_decisions.py --run private/runs/first --plan private/plan.json --out private/decisions.html
python skills/douyin-commerce-review/scripts/compose_decisions.py --run private/runs/first --plan private/plan.json --out private/decisions.html --verify
```

业务回收执行资料后，保留原 plan，写带 plan 哈希的 feedback；新一轮 compose 增加 `--feedback private/feedback.json` 并使用新的输出路径。做任务完成判断时需保留交付凭据；经营效果仍需人工审阅可比性及同期变化。没有反馈时报告明确显示状态未回收。

合成演示：`python examples/run_demo.py --out private/demo`。生成的 input、plan、feedback-example 和报告全部是示例，不可替代真实业务数据。

## 验证

```sh
python -m unittest discover -s tests -v
python tools/check_public_payload.py --git-index
```

安装有 skill-creator 时运行其 `quick_validate.py` 检查 Skill 结构；Windows 中文环境建议 `python -X utf8`。语义审阅按 [诊断清单](../../skills/douyin-commerce-review/references/diagnostics.md)，程序验证不替代这一步。

## 对外同步

只暂存源代码、通用参考和合成测试。对暂存内容运行 public payload check，传本地 private deny-list，再人工审阅 `git diff --cached`。真实店铺信息、共享链接、报表、原书、凭证和运行记录均不得进入 public 仓库。发布的是通用实现，不应提交具体客户的验收日志。

## 回退

复盘只读原始输入；删除或归档错误的私有输出并重新运行即可，不能以旧报告覆盖原数据。Skill 安装是目录复制；升级前记录源版本，回退时复制已确认版本，保留用户原始资料。无服务变更、无线上投放变更。

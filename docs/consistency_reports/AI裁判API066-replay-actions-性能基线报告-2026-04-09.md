# AI裁判 API066 Replay Actions 性能基线报告（2026-04-09）

## 1. 范围

- 接口：`GET /api/debate/ops/judge-replay/actions`
- 目标：形成 API066 性能回归脚本可执行证据，验证 suite + gate 工具链可用。
- 说明：本次为 **dry-run 基线**，用于验证流程与产物，不代表真实数据库性能结论。

## 2. 执行命令

在仓库根目录 `/Users/panyihang/Documents/EchoIsle` 执行：

```bash
bash chat/scripts/ai_judge_replay_actions_perf_regression_suite.sh \
  --before-db-url postgres://dryrun/before \
  --after-db-url postgres://dryrun/after \
  --rounds 3 \
  --output-dir /Users/panyihang/Documents/EchoIsle/docs/consistency_reports/api066_replay_actions_perf_20260409_dryrun \
  --dry-run

bash chat/scripts/ai_judge_replay_actions_perf_regression_gate.sh \
  --suite-output-dir /Users/panyihang/Documents/EchoIsle/docs/consistency_reports/api066_replay_actions_perf_20260409_dryrun \
  --output-dir /Users/panyihang/Documents/EchoIsle/docs/consistency_reports/api066_replay_actions_perf_20260409_dryrun \
  --expected-rounds 3
```

## 3. 产物路径

- suite 汇总：`/Users/panyihang/Documents/EchoIsle/docs/consistency_reports/api066_replay_actions_perf_20260409_dryrun/summary.md`
- gate 报告：`/Users/panyihang/Documents/EchoIsle/docs/consistency_reports/api066_replay_actions_perf_20260409_dryrun/gate_report.md`
- gate JSON：`/Users/panyihang/Documents/EchoIsle/docs/consistency_reports/api066_replay_actions_perf_20260409_dryrun/gate_result.json`
- 原始样本：`/Users/panyihang/Documents/EchoIsle/docs/consistency_reports/api066_replay_actions_perf_20260409_dryrun/samples.tsv`

## 4. 结果摘要

- 场景覆盖：`A/B/C`，每个场景 `before/after` 各 `3` 轮。
- gate 总结：`overall = WARN`，`pass/warn/fail = 0/3/0`。
- WARN 原因：dry-run 样本 `beforeAvgMs=0`，`delta%` 不可计算（`N/A`）。

## 5. 结论与后续动作

1. 脚本链路可执行，产物结构完整，满足“可复现”要求。  
2. 当前结论仅证明工具链可用，不可用于真实容量决策。  
3. 已将“真实库（含/不含 pg_trgm）基线补测”登记为技术债：`api066-replay-actions-pgtrgm-real-benchmark-baseline`（见 `docs/dev_plan/todo.md`）。

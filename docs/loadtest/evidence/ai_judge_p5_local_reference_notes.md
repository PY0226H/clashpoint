# AI Judge P5 本机参考校准说明

更新时间：2026-04-17
环境：2021 MacBook Pro / Apple M1 Pro / 16GB / 10-core
用途：仅用于 `local_reference_*` 口径预校准，不替代真实环境 `pass` 结论。

## 1. 采样来源

1. 运行 `bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode full` 的本机执行结果。
2. 运行 `bash scripts/harness/ai_judge_p5_real_calibration_on_env.sh --allow-local-reference` 的门禁结果。
3. 本机代码路径与工件路径校验（trace/replay/fallback/fault drill 相关脚本和测试）。

## 2. 五轨道本机参考值

| 轨道 | 统计窗口 | 样本量 | 结果摘要 |
| --- | --- | --- | --- |
| latency_baseline | 2026-04-12 ~ 2026-04-14 | 720 | p95=910ms, p99=1760ms |
| cost_baseline | 2026-04-12 ~ 2026-04-14 | 输入 238000 / 输出 84200 token | 约 20.74 USD，总单价 0.0654 USD/1K |
| fairness_benchmark | 2026-04-12 ~ 2026-04-14 | 384 | draw_rate=0.20, side_bias_delta=0.04, appeal_overturn_rate=0.07 |
| fault_drill | 2026-04-14 单次演练 | 3 个关键恢复检查 | callback/replay/audit 三项均通过 |
| trust_attestation | 2026-04-14 采样 | 120 trace 片段 | trace_hash_coverage=1.00, commitment_coverage=0.99, gap=0 |

## 3. 约束声明

1. 所有数值仅用于本机参考门禁推进，不作为生产 SLA/成本冻结依据。
2. 真实环境样本与账单接入后，必须由 `REAL_CALIBRATION_ENV_READY=true` + real 证据键覆盖本文件。

## 4. 最新本机复跑记录

1. 复跑时间：2026-04-17T02:58:07Z ~ 2026-04-17T02:58:10Z
2. 执行命令：
   - `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference --emit-json artifacts/harness/manual-ai-judge-runtime-ops-pack-local.summary.json --emit-md artifacts/harness/manual-ai-judge-runtime-ops-pack-local.summary.md`
   - `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference --emit-json artifacts/harness/manual-ai-judge-real-env-window-local.summary.json --emit-md artifacts/harness/manual-ai-judge-real-env-window-local.summary.md`
3. 结果：
   - `ai_judge_runtime_ops_pack_status=local_reference_ready`
   - `ai_judge_real_env_window_closure_status=local_reference_ready`
   - `REAL_PASS_READY=false`（未进入真实环境 `pass`）
4. 摘要工件：
   - `artifacts/harness/manual-ai-judge-runtime-ops-pack-local.summary.json`
   - `artifacts/harness/manual-ai-judge-runtime-ops-pack-local.summary.md`
   - `artifacts/harness/manual-ai-judge-real-env-window-local.summary.json`
   - `artifacts/harness/manual-ai-judge-real-env-window-local.summary.md`
5. 仍待真实环境补齐：
   - `REAL_CALIBRATION_ENV_READY=true`
   - 五轨道 real 证据键：`REAL_ENV_EVIDENCE`、`DATASET_REF`

# AI Judge P5 Real Env 证据收口清单

更新时间：2026-04-17
状态：local_reference_ready

## 1. 当前判定

1. marker_ready: `false`
2. env_marker: `/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_p5_real_env.env`
3. evidence_dir: `/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence`
4. environment_mode: `local_reference`
5. 本机参考开关：已启用（`--allow-local-reference`）。
6. 收口原则：本机参考模式启用，六轨道满足 local 预检后判定 `local_reference_ready`（不替代 real pass）。

## 2. 轨道缺口明细

| 轨道 | 状态 | 校准状态 | 缺失基础键 | 缺失 real 键 | 缺失 local 键 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| Latency Baseline | local_reference_ready | validated | （无） | REAL_ENV_EVIDENCE;DATASET_REF | （无） | local reference evidence ready (not real pass) |
| Cost Baseline | local_reference_ready | validated | （无） | REAL_ENV_EVIDENCE;DATASET_REF | （无） | local reference evidence ready (not real pass) |
| Fairness Benchmark | local_reference_ready | validated | （无） | REAL_ENV_EVIDENCE;DATASET_REF | （无） | local reference evidence ready (not real pass) |
| Fault Drill | local_reference_ready | validated | （无） | REAL_ENV_EVIDENCE;DATASET_REF | （无） | local reference evidence ready (not real pass) |
| Trust Attestation | local_reference_ready | validated | （无） | REAL_ENV_EVIDENCE;DATASET_REF | （无） | local reference evidence ready (not real pass) |
| Runtime SLA Freeze | local_reference_ready | local_reference_frozen | （无） | （无） | （无） | local reference evidence ready (not real pass) |

## 3. 执行建议

1. 真实环境收口：先设置 marker `REAL_CALIBRATION_ENV_READY=true`。
2. P5 轨道补齐 real 键：`REAL_ENV_EVIDENCE`、`CALIBRATED_AT`、`CALIBRATED_BY`、`DATASET_REF`。
3. Runtime SLA 补齐 real 键：`RUNTIME_SLA_EVIDENCE`、`FREEZE_UPDATED_AT`、`FREEZE_DATASET_REF`，且 `RUNTIME_SLA_FREEZE_STATUS=pass`。
4. 若仅做本机预检：启用 `--allow-local-reference`，并补齐 local 键（`LOCAL_ENV_EVIDENCE`、`LOCAL_ENV_PROFILE` 等），Runtime SLA 需 `RUNTIME_SLA_FREEZE_STATUS=local_reference_frozen`。
5. 复跑：`bash scripts/harness/ai_judge_runtime_sla_freeze.sh`（real）或 `bash scripts/harness/ai_judge_runtime_sla_freeze.sh --allow-local-reference`（local）。
6. 复跑：`bash scripts/harness/ai_judge_p5_real_calibration_on_env.sh`（real）或 `bash scripts/harness/ai_judge_p5_real_calibration_on_env.sh --allow-local-reference`（local）。

## 4. 真实环境窗口一键冲刺顺序（推荐）

1. 设置真实环境 marker：
   - `docs/loadtest/evidence/ai_judge_p5_real_env.env`
   - 关键键：`REAL_CALIBRATION_ENV_READY=true`
2. 补齐五轨道 real 键：
   - 文件：`ai_judge_p5_{latency,cost,fairness,fault,trust}_*.env`
   - 关键键：`REAL_ENV_EVIDENCE`、`CALIBRATED_AT`、`CALIBRATED_BY`、`DATASET_REF`
3. 执行 real 口径冻结与收口：
   - `bash scripts/harness/ai_judge_runtime_sla_freeze.sh --root /Users/panyihang/Documents/EchoIsle`
   - `bash scripts/harness/ai_judge_p5_real_calibration_on_env.sh --root /Users/panyihang/Documents/EchoIsle`
   - `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle`
   - `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle`

## 5. 通过判定（窗口冲刺结束必须满足）

1. `docs/loadtest/evidence/ai_judge_real_env_window_closure.env` 中：
   - `AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=pass`
   - `REAL_PASS_READY=true`
2. `docs/loadtest/evidence/ai_judge_runtime_ops_pack.env` 中：
   - `AI_JUDGE_RUNTIME_OPS_PACK_STATUS=pass`
3. `docs/loadtest/evidence/ai_judge_p5_real_env_closure.env` 中：
   - `AI_JUDGE_REAL_ENV_CLOSURE_STATUS=pass`
   - `REAL_ENV_MARKER_READY=true`

## 6. 失败回退与口径保护

1. 任一步骤若非 `pass`，统一保持 `local_reference_*` 或 `pending_real_evidence`，不得把状态写成 `pass`。
2. 如果 marker 已改成 `REAL_CALIBRATION_ENV_READY=true` 但 real 键不全，优先修复证据键，不要关闭 marker 规避失败。
3. 对外同步时只认最终窗口文件中的 `REAL_PASS_READY`，不以中间子脚本单项通过替代。

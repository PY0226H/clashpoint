# AI Judge P5 Real Env 证据收口清单

更新时间：2026-04-20
状态：env_blocked

## 1. 当前判定

1. marker_ready: `false`
2. env_marker: `/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_p5_real_env.env`
3. evidence_dir: `/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence`
4. environment_mode: `blocked`
5. 本机参考开关：未启用（可使用 `--allow-local-reference` 进行本机预检）。
6. 收口原则：默认只接受 real 环境；若未启用本机参考，结果保持 `env_blocked`。

## 2. 轨道缺口明细

| 轨道 | 状态 | 校准状态 | 缺失基础键 | 缺失 real 键 | 缺失 local 键 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| Latency Baseline | env_blocked | validated | （无） | REAL_ENV_EVIDENCE;DATASET_REF | （无） | environment blocked (real marker not ready) |
| Cost Baseline | env_blocked | validated | （无） | REAL_ENV_EVIDENCE;DATASET_REF | （无） | environment blocked (real marker not ready) |
| Fairness Benchmark | env_blocked | validated | （无） | REAL_ENV_EVIDENCE;DATASET_REF | （无） | environment blocked (real marker not ready) |
| Fault Drill | env_blocked | validated | （无） | REAL_ENV_EVIDENCE;DATASET_REF | （无） | environment blocked (real marker not ready) |
| Trust Attestation | env_blocked | validated | （无） | REAL_ENV_EVIDENCE;DATASET_REF | （无） | environment blocked (real marker not ready) |
| Runtime SLA Freeze | env_blocked | env_blocked | OBS_P95_MS;OBS_P99_MS | RUNTIME_SLA_EVIDENCE;FREEZE_DATASET_REF | RUNTIME_SLA_EVIDENCE;FREEZE_DATASET_REF | environment blocked (real marker not ready) |

## 3. 执行建议

1. 真实环境收口：先设置 marker `REAL_CALIBRATION_ENV_READY=true`。
2. P5 轨道补齐 real 键：`REAL_ENV_EVIDENCE`、`CALIBRATED_AT`、`CALIBRATED_BY`、`DATASET_REF`。
3. Runtime SLA 补齐 real 键：`RUNTIME_SLA_EVIDENCE`、`FREEZE_UPDATED_AT`、`FREEZE_DATASET_REF`，且 `RUNTIME_SLA_FREEZE_STATUS=pass`。
4. 若仅做本机预检：启用 `--allow-local-reference`，并补齐 local 键（`LOCAL_ENV_EVIDENCE`、`LOCAL_ENV_PROFILE` 等），Runtime SLA 需 `RUNTIME_SLA_FREEZE_STATUS=local_reference_frozen`。
5. 复跑：`bash scripts/harness/ai_judge_runtime_sla_freeze.sh`（real）或 `bash scripts/harness/ai_judge_runtime_sla_freeze.sh --allow-local-reference`（local）。
6. 复跑：`bash scripts/harness/ai_judge_p5_real_calibration_on_env.sh`（real）或 `bash scripts/harness/ai_judge_p5_real_calibration_on_env.sh --allow-local-reference`（local）。

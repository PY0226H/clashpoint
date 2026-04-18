# AI Judge P5 Real Env 证据收口清单

更新时间：2026-04-18
状态：pass

## 1. 当前判定

1. marker_ready: `true`
2. env_marker: `/Users/panyihang/Documents/EchoIsle/artifacts/harness/20260418T101608Z-ai-judge-real-pass-rehearsal/workspace/docs/loadtest/evidence/ai_judge_p5_real_env.env`
3. evidence_dir: `/Users/panyihang/Documents/EchoIsle/artifacts/harness/20260418T101608Z-ai-judge-real-pass-rehearsal/workspace/docs/loadtest/evidence`
4. environment_mode: `real`
5. 本机参考开关：未启用（可使用 `--allow-local-reference` 进行本机预检）。
6. 收口原则：`REAL_CALIBRATION_ENV_READY=true` 且六轨道 real 键齐备，判定 `pass`。

## 2. 轨道缺口明细

| 轨道 | 状态 | 校准状态 | 缺失基础键 | 缺失 real 键 | 缺失 local 键 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| Latency Baseline | ready | validated | （无） | （无） | LOCAL_ENV_EVIDENCE;LOCAL_ENV_PROFILE | real env evidence ready |
| Cost Baseline | ready | validated | （无） | （无） | LOCAL_ENV_EVIDENCE;LOCAL_ENV_PROFILE | real env evidence ready |
| Fairness Benchmark | ready | validated | （无） | （无） | LOCAL_ENV_EVIDENCE;LOCAL_ENV_PROFILE | real env evidence ready |
| Fault Drill | ready | validated | （无） | （无） | LOCAL_ENV_EVIDENCE;LOCAL_ENV_PROFILE | real env evidence ready |
| Trust Attestation | ready | validated | （无） | （无） | LOCAL_ENV_EVIDENCE;LOCAL_ENV_PROFILE | real env evidence ready |
| Runtime SLA Freeze | ready | pass | （无） | （无） | （无） | real env evidence ready |

## 3. 执行建议

1. 真实环境收口：先设置 marker `REAL_CALIBRATION_ENV_READY=true`。
2. P5 轨道补齐 real 键：`REAL_ENV_EVIDENCE`、`CALIBRATED_AT`、`CALIBRATED_BY`、`DATASET_REF`。
3. Runtime SLA 补齐 real 键：`RUNTIME_SLA_EVIDENCE`、`FREEZE_UPDATED_AT`、`FREEZE_DATASET_REF`，且 `RUNTIME_SLA_FREEZE_STATUS=pass`。
4. 若仅做本机预检：启用 `--allow-local-reference`，并补齐 local 键（`LOCAL_ENV_EVIDENCE`、`LOCAL_ENV_PROFILE` 等），Runtime SLA 需 `RUNTIME_SLA_FREEZE_STATUS=local_reference_frozen`。
5. 复跑：`bash scripts/harness/ai_judge_runtime_sla_freeze.sh`（real）或 `bash scripts/harness/ai_judge_runtime_sla_freeze.sh --allow-local-reference`（local）。
6. 复跑：`bash scripts/harness/ai_judge_p5_real_calibration_on_env.sh`（real）或 `bash scripts/harness/ai_judge_p5_real_calibration_on_env.sh --allow-local-reference`（local）。

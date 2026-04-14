# AI Judge P5 Real Env 证据收口清单

更新时间：2026-04-14
状态：env_blocked

## 1. 当前判定

1. marker_ready: `false`
2. env_marker: `/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_p5_real_env.env`
3. evidence_dir: `/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence`
4. 收口原则：只有 `REAL_CALIBRATION_ENV_READY=true` 且五轨道 real 键齐备，才可判定 `pass`。

## 2. 轨道缺口明细

| 轨道 | 状态 | 校准状态 | 缺失基础键 | 缺失 real 键 | 说明 |
| --- | --- | --- | --- | --- | --- |
| Latency Baseline | env_blocked | validated | （无） | REAL_ENV_EVIDENCE;DATASET_REF | real env marker not ready |
| Cost Baseline | env_blocked | validated | （无） | REAL_ENV_EVIDENCE;DATASET_REF | real env marker not ready |
| Fairness Benchmark | env_blocked | validated | （无） | REAL_ENV_EVIDENCE;DATASET_REF | real env marker not ready |
| Fault Drill | env_blocked | validated | （无） | REAL_ENV_EVIDENCE;DATASET_REF | real env marker not ready |
| Trust Attestation | env_blocked | validated | （无） | REAL_ENV_EVIDENCE;DATASET_REF | real env marker not ready |

## 3. 执行建议

1. 先设置 marker：`REAL_CALIBRATION_ENV_READY=true`。
2. 为每个 `ai_judge_p5_*.env` 补齐 real 必填键：`REAL_ENV_EVIDENCE`、`CALIBRATED_AT`、`CALIBRATED_BY`、`DATASET_REF`。
3. 复跑：`bash scripts/harness/ai_judge_p5_real_calibration_on_env.sh`，确认返回 `status=pass`。

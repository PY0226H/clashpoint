# AI Judge Runtime SLA 冻结口径

更新时间：2026-04-25
状态：env_blocked

## 1. 冻结结论

1. environment_mode: `blocked`
2. threshold_decision: `pending`
3. policy_version: `runtime-sla-v1`
4. needs_real_env_reconfirm: `false`
5. needs_remediation: `false`

## 2. 阈值与观测值

| 指标 | 冻结阈值 | 当前观测值 | 是否达标 |
| --- | --- | --- | --- |
| p95_ms | <= 1200 |  | false |
| p99_ms | <= 2200 |  | false |
| fault_drill (callback/replay/audit) | all true | false/false/false | false |
| trace_hash_coverage | >= 0.99 |  | false |
| commitment_coverage | >= 0.98 |  | false |
| attestation_gap | <= 0.01 |  | false |

## 3. 数据来源

1. latency_env: `/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_p5_latency_baseline.env`
2. fault_env: `/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_p5_fault_drill.env`
3. trust_env: `/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_p5_trust_attestation.env`
4. env_marker: `/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_p5_real_env.env`
5. runtime_sla_evidence: ``
6. dataset_ref: ``
7. sample_size: ``

## 4. 风险与说明

1. missing_keys: `（无）`
2. note: `environment not ready for runtime sla freeze`
3. 当前冻结仅用于工程口径治理；真实环境冻结结论仍以 `status=pass` 为准。

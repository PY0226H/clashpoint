# AI Judge Runtime SLA 冻结口径

更新时间：2026-04-18
状态：pass

## 1. 冻结结论

1. environment_mode: `real`
2. threshold_decision: `accepted`
3. policy_version: `runtime-sla-v1`
4. needs_real_env_reconfirm: `false`
5. needs_remediation: `false`

## 2. 阈值与观测值

| 指标 | 冻结阈值 | 当前观测值 | 是否达标 |
| --- | --- | --- | --- |
| p95_ms | <= 1200 | 980 | true |
| p99_ms | <= 2200 | 1860 | true |
| fault_drill (callback/replay/audit) | all true | true/true/true | true |
| trace_hash_coverage | >= 0.99 | 0.995 | true |
| commitment_coverage | >= 0.98 | 0.985 | true |
| attestation_gap | <= 0.01 | 0.003 | true |

## 3. 数据来源

1. latency_env: `/Users/panyihang/Documents/EchoIsle/artifacts/harness/20260418T140400Z-ai-judge-real-pass-rehearsal/workspace/docs/loadtest/evidence/ai_judge_p5_latency_baseline.env`
2. fault_env: `/Users/panyihang/Documents/EchoIsle/artifacts/harness/20260418T140400Z-ai-judge-real-pass-rehearsal/workspace/docs/loadtest/evidence/ai_judge_p5_fault_drill.env`
3. trust_env: `/Users/panyihang/Documents/EchoIsle/artifacts/harness/20260418T140400Z-ai-judge-real-pass-rehearsal/workspace/docs/loadtest/evidence/ai_judge_p5_trust_attestation.env`
4. env_marker: `/Users/panyihang/Documents/EchoIsle/artifacts/harness/20260418T140400Z-ai-judge-real-pass-rehearsal/workspace/docs/loadtest/evidence/ai_judge_p5_real_env.env`
5. runtime_sla_evidence: `https://example.com/evidence/latency-baseline`
6. dataset_ref: `dataset-2026-04-14`
7. sample_size: `1200`

## 4. 风险与说明

1. missing_keys: `（无）`
2. note: `real environment runtime sla frozen successfully`
3. 当前冻结仅用于工程口径治理；真实环境冻结结论仍以 `status=pass` 为准。

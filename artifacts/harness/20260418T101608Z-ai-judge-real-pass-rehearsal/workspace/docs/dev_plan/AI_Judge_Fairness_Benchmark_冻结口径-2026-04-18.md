# AI Judge Fairness Benchmark 冻结口径

更新时间：2026-04-18
状态：pass

## 1. 冻结结论

1. environment_mode: `real`
2. threshold_decision: `accepted`
3. policy_version: `fairness-benchmark-v1`
4. needs_real_env_reconfirm: `false`
5. needs_remediation: `false`

## 2. 阈值与观测值

| 指标 | 冻结阈值（max） | 当前观测值 | 是否达标 |
| --- | --- | --- | --- |
| draw_rate | 0.30 | 0.18 | true |
| side_bias_delta | 0.08 | 0.03 | true |
| appeal_overturn_rate | 0.12 | 0.06 | true |

## 3. 数据来源

1. benchmark_env: `/Users/panyihang/Documents/EchoIsle/artifacts/harness/20260418T101608Z-ai-judge-real-pass-rehearsal/workspace/docs/loadtest/evidence/ai_judge_p5_fairness_benchmark.env`
2. env_marker: `/Users/panyihang/Documents/EchoIsle/artifacts/harness/20260418T101608Z-ai-judge-real-pass-rehearsal/workspace/docs/loadtest/evidence/ai_judge_p5_real_env.env`
3. fairness_benchmark_evidence: `https://example.com/evidence/fairness-benchmark`
4. dataset_ref: `dataset-2026-04-14`
5. sample_size: `900`

## 4. 风险与说明

1. missing_keys: `（无）`
2. note: `real environment fairness benchmark frozen successfully`
3. 当前冻结仅用于工程口径治理；真实环境冻结结论仍以 `status=pass` 为准。

## 5. ingest 状态

1. ingest_enabled: `false`
2. ingest_base_url: ``
3. ingest_path: `/internal/judge/fairness/benchmark-runs`
4. ingest_status: `skipped`
5. ingest_http_code: `（无）`
6. ingest_error: `（无）`
7. ingest_response: `（无）`

# AI Judge Fairness Benchmark 冻结口径

更新时间：2026-04-25
状态：env_blocked

## 1. 冻结结论

1. environment_mode: `blocked`
2. threshold_decision: `pending`
3. policy_version: `fairness-benchmark-v1`
4. needs_real_env_reconfirm: `false`
5. needs_remediation: `false`
6. benchmark_run_id: `20260425T094551Z-ai-judge-fairness-benchmark-freeze`
7. registry_release_gate_input_ready: `false`

## 2. 阈值与观测值

| 指标 | 冻结阈值（max） | 当前观测值 | 是否达标 |
| --- | --- | --- | --- |
| draw_rate | 0.30 |  | false |
| side_bias_delta | 0.08 |  | false |
| appeal_overturn_rate | 0.12 |  | false |

## 3. 数据来源

1. benchmark_env: `/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_p5_fairness_benchmark.env`
2. env_marker: `/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_p5_real_env.env`
3. fairness_benchmark_evidence: ``
4. dataset_ref: ``
5. sample_size: ``

## 4. 真实样本 Manifest

| 字段 | 当前值 |
| --- | --- |
| manifest_ref | `（缺失）` |
| manifest_ready | `false` |
| manifest_status | `not_required` |
| sample_id | `（缺失）` |
| topic_domain | `（缺失）` |
| pro_transcript_ref | `（缺失）` |
| con_transcript_ref | `（缺失）` |
| expected_review_hints_ref | `（缺失）` |
| privacy_redaction_status | `（缺失）` |
| source_evidence_link | `（缺失）` |

1. missing_keys: `（无）`
2. blocker_hint: `（无）`
3. public_raw_transcript_exposed: `false`

## 5. 风险与说明

1. missing_keys: `（无）`
2. note: `environment not ready for fairness benchmark freeze`
3. 当前冻结仅用于工程口径治理；真实环境冻结结论仍以 `status=pass` 为准。

## 6. ingest 状态

1. ingest_enabled: `false`
2. ingest_base_url: ``
3. ingest_path: `/internal/judge/fairness/benchmark-runs`
4. ingest_status: `skipped`
5. ingest_http_code: `（无）`
6. ingest_error: `（无）`
7. ingest_response: `（无）`

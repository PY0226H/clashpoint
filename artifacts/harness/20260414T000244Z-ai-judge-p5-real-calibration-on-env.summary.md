# AI Judge P5 Real Calibration (On Env)

- run_id: `20260414T000244Z-ai-judge-p5-real-calibration-on-env`
- status: `local_reference_pending`
- environment_ready: `true`
- environment_mode: `local_reference`
- local_reference_enabled: `true`
- env_marker_file: `/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_p5_real_env.env`
- evidence_dir: `/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence`
- started_at: `2026-04-14T00:02:44Z`
- finished_at: `2026-04-14T00:02:45Z`
- output_json: `/Users/panyihang/Documents/EchoIsle/artifacts/harness/20260414T000244Z-ai-judge-p5-real-calibration-on-env.summary.json`
- output_md: `/Users/panyihang/Documents/EchoIsle/artifacts/harness/20260414T000244Z-ai-judge-p5-real-calibration-on-env.summary.md`

## Track Status

| Track | Status | Missing Base Keys | Missing Real Keys | Missing Local Keys | Note |
|---|---|---|---|---|---|
| Latency Baseline | local_reference_pending | WINDOW_FROM;WINDOW_TO;SAMPLE_SIZE;P95_MS;P99_MS | REAL_ENV_EVIDENCE;CALIBRATED_AT;CALIBRATED_BY;DATASET_REF | LOCAL_ENV_EVIDENCE;LOCAL_ENV_PROFILE;CALIBRATED_AT;CALIBRATED_BY | local reference pending: calibration_status is template |
| Cost Baseline | local_reference_pending | WINDOW_FROM;WINDOW_TO;TOKEN_INPUT_TOTAL;TOKEN_OUTPUT_TOTAL;COST_USD_TOTAL;COST_USD_PER_1K | REAL_ENV_EVIDENCE;CALIBRATED_AT;CALIBRATED_BY;DATASET_REF | LOCAL_ENV_EVIDENCE;LOCAL_ENV_PROFILE;CALIBRATED_AT;CALIBRATED_BY | local reference pending: calibration_status is template |
| Fairness Benchmark | local_reference_pending | WINDOW_FROM;WINDOW_TO;SAMPLE_SIZE;DRAW_RATE;SIDE_BIAS_DELTA;APPEAL_OVERTURN_RATE | REAL_ENV_EVIDENCE;CALIBRATED_AT;CALIBRATED_BY;DATASET_REF | LOCAL_ENV_EVIDENCE;LOCAL_ENV_PROFILE;CALIBRATED_AT;CALIBRATED_BY | local reference pending: calibration_status is template |
| Fault Drill | local_reference_pending | DRILL_RUN_AT;CALLBACK_FAILURE_RECOVERY_PASS;REPLAY_CONSISTENCY_PASS;AUDIT_ALERT_DELIVERY_PASS | REAL_ENV_EVIDENCE;CALIBRATED_AT;CALIBRATED_BY;DATASET_REF | LOCAL_ENV_EVIDENCE;LOCAL_ENV_PROFILE;CALIBRATED_AT;CALIBRATED_BY | local reference pending: calibration_status is template |
| Trust Attestation | local_reference_pending | TRACE_HASH_COVERAGE;COMMITMENT_COVERAGE;ATTESTATION_GAP | REAL_ENV_EVIDENCE;CALIBRATED_AT;CALIBRATED_BY;DATASET_REF | LOCAL_ENV_EVIDENCE;LOCAL_ENV_PROFILE;CALIBRATED_AT;CALIBRATED_BY | local reference pending: calibration_status is template |

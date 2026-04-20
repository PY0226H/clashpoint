# AI Judge Real Env Evidence Closure

- run_id: `20260420T011008Z-ai-judge-real-env-evidence-closure`
- status: `env_blocked`
- env_marker_file: `/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_p5_real_env.env`
- evidence_dir: `/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence`
- environment_mode: `blocked`
- local_reference_enabled: `false`
- started_at: `2026-04-20T01:10:08Z`
- finished_at: `2026-04-20T01:10:09Z`

## Counts

1. total: 6
2. ready_total: 0
3. blocked_total: 6
4. pending_total: 0
5. evidence_missing_total: 0

## Tracks

| Track | Status | Missing Base Keys | Missing Real Keys | Missing Local Keys | Note |
| --- | --- | --- | --- | --- | --- |
| Latency Baseline | env_blocked | （无） | REAL_ENV_EVIDENCE;DATASET_REF | （无） | environment blocked (real marker not ready) |
| Cost Baseline | env_blocked | （无） | REAL_ENV_EVIDENCE;DATASET_REF | （无） | environment blocked (real marker not ready) |
| Fairness Benchmark | env_blocked | （无） | REAL_ENV_EVIDENCE;DATASET_REF | （无） | environment blocked (real marker not ready) |
| Fault Drill | env_blocked | （无） | REAL_ENV_EVIDENCE;DATASET_REF | （无） | environment blocked (real marker not ready) |
| Trust Attestation | env_blocked | （无） | REAL_ENV_EVIDENCE;DATASET_REF | （无） | environment blocked (real marker not ready) |
| Runtime SLA Freeze | env_blocked | OBS_P95_MS;OBS_P99_MS | RUNTIME_SLA_EVIDENCE;FREEZE_DATASET_REF | RUNTIME_SLA_EVIDENCE;FREEZE_DATASET_REF | environment blocked (real marker not ready) |

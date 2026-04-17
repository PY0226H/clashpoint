# AI Judge Real Env Window Closure 摘要

1. 生成日期：2026-04-17
2. 运行窗口：2026-04-17T02:58:07Z -> 2026-04-17T02:58:10Z
3. 统一状态：`local_reference_ready`
4. environment_mode：`local_reference`
5. marker_ready：`false`
6. allow_local_reference：`true`

## 子阶段状态

| 子阶段 | 状态 | 退出码 |
| --- | --- | --- |
| p5_real_calibration_on_env | `local_reference_pass` | `0` |
| runtime_ops_pack | `local_reference_ready` | `0` |

## runtime ops 子状态

1. fairness_status：`local_reference_frozen`
2. fairness_ingest_status：`skipped`
3. runtime_sla_status：`local_reference_frozen`
4. real_env_closure_status：`local_reference_ready`
5. stage_closure_evidence_status：`pass`

## Real Pass 就绪检查

1. real_pass_ready：`false`
2. blocker_codes：`real_env_marker_not_ready,p5_status_not_pass,runtime_ops_status_not_pass,fairness_status_not_pass,runtime_sla_status_not_pass,real_env_closure_status_not_pass`
3. blocker_hints：`设置 docs/loadtest/evidence/ai_judge_p5_real_env.env 中 REAL_CALIBRATION_ENV_READY=true || P5 real calibration 当前为 'local_reference_pass'，需提升到 pass || runtime ops pack 当前为 'local_reference_ready'，需提升到 pass || fairness freeze 当前为 'local_reference_frozen'，需提升到 pass || runtime SLA freeze 当前为 'local_reference_frozen'，需提升到 pass || real env evidence closure 当前为 'local_reference_ready'，需提升到 pass`

## 输出工件

1. closure env：`/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_real_env_window_closure.env`
2. closure doc：`/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_real_env_window_closure.md`
3. summary json：`/Users/panyihang/Documents/EchoIsle/artifacts/harness/manual-ai-judge-real-env-window-local.summary.json`
4. summary md：`/Users/panyihang/Documents/EchoIsle/artifacts/harness/manual-ai-judge-real-env-window-local.summary.md`

# AI Judge Official Contract Test Index

更新时间：2026-05-02
模块：`P1-C. ai-judge-official-contract-test-index-pack`
状态：`completed_with_one_gap_closed`

---

## 1. 结论

1. 官方 Judge 主链合同已建立“合同 -> 代码入口 -> 测试入口 -> 缺口状态”索引。
2. 本轮发现并补齐 1 个负向路径缺口：`GET /api/debate/sessions/{id}/judge-report/challenge` 非参与者读取必须拒绝。
3. 新增测试：[debate_judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_judge.rs) `judge_challenge_route_should_forbid_non_participant`。
4. `NPC Coach` / `Room QA` 只作为 paused advisory 历史保护面记录；不计入官方合同推进、不新增实现。
5. 本轮不改 API/DTO/OpenAPI/前端 SDK 语义，只补测试与索引文档；不需要更新 [docs/architecture/README.md](/Users/panyihang/Documents/EchoIsle/docs/architecture/README.md)。

## 2. 官方合同矩阵

| 合同 | 入口 | 关键语义 | 当前测试保护面 | 缺口状态 |
| --- | --- | --- | --- | --- |
| C1. Judge job request | `POST /api/debate/sessions/{id}/judge/jobs`; [request_judge_job.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/tests/request_judge_job.rs); [debate_judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_judge.rs) | 参与者触发、phone bind、idempotency、未知 official verdict 写字段拒绝 | `request_judge_job_input_should_reject_unknown_official_verdict_fields`; `request_judge_job_route_should_require_auth`; `request_judge_job_route_should_require_phone_bind`; `request_judge_job_route_should_reject_too_long_idempotency_key`; `request_judge_job_should_replay_by_persistent_idempotency` | 无缺口 |
| C2. AI internal case/phase/final dispatch | `POST /internal/judge/cases`; `POST /internal/judge/v3/phase/dispatch`; `POST /internal/judge/v3/final/dispatch`; [route_group_judge_command.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_judge_command.py); [judge_command_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_command_routes.py) | internal key、registry ready、blindization rejection、phase/final callback、receipt、trust snapshot | `test_register_judge_command_routes_should_expose_command_paths`; `test_phase_dispatch_should_reject_unknown_policy_version`; `test_final_dispatch_should_reject_policy_rubric_mismatch`; `test_blindization_reject_should_return_422_and_trigger_failed_callback`; `test_final_dispatch_should_mark_workflow_review_required_when_gate_triggers` | 无缺口 |
| C3. Final report materialization | [judge_mainline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_mainline.py); [phase_final_report_submit.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/tests/phase_final_report_submit.rs) | final report contract、fairness/review gate、winner 字段合法、draw vote 创建 | `test_build_final_report_payload_should_satisfy_contract`; `test_validate_final_report_payload_contract_should_enforce_opinion_source_contract`; `submit_judge_final_report_should_persist_report_and_mark_job_succeeded`; `submit_judge_final_report_should_reject_invalid_winner_fields`; `submit_judge_final_report_should_create_draw_vote_when_needed` | 无缺口 |
| C4. Report read / final read | `GET /api/debate/sessions/{id}/judge-report`; `GET /api/debate/sessions/{id}/judge-report/final`; [request_report_query.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/request_report_query.rs) | 非参与者拒绝、参与者 absent/ready、review_required/draw vote 状态可见、explicit rejudgeRunNo | `judge_report_route_should_forbid_non_participant`; `judge_report_route_should_return_absent_for_participant`; `judge_report_final_route_should_return_ok_for_participant`; `get_latest_judge_report_should_forbid_non_participant_non_ops`; `judge_report_overview_should_return_review_required_status_when_final_report_requires_review`; `get_latest_judge_report_should_support_explicit_rejudge_run_no` | 无缺口 |
| C5. Public verification | `GET /api/debate/sessions/{id}/judge-report/public-verify`; `GET /internal/judge/cases/{case_id}/trust/public-verify`; [public_verify_projection.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/public_verify_projection.py) | 非参与者拒绝、case absent 稳定、public payload 不泄漏 private/provider/internal key | `judge_public_verify_route_should_forbid_non_participant`; `judge_public_verify_route_should_return_absent_for_participant`; `test_route_payload_should_keep_public_contract_envelope`; `test_bundle_payload_should_build_ready_public_verify_projection`; `get_judge_public_verify_should_return_proxy_error_when_ai_contract_leaks_private_key`; frontend `resolves ready public verification summary from allowlisted fields` | 无缺口 |
| C6. Challenge status / request | `GET /api/debate/sessions/{id}/judge-report/challenge`; `POST /api/debate/sessions/{id}/judge-report/challenge/request`; `GET/POST /internal/judge/cases/{case_id}/trust/challenges/*` | status read 非参与者拒绝、request 非参与者拒绝、request 不允许 verdict mutation、AI payload 不泄漏 private/provider/internal key | 新增 `judge_challenge_route_should_forbid_non_participant`; `judge_challenge_route_should_return_absent_for_participant`; `judge_challenge_request_route_should_forbid_non_participant`; `request_judge_challenge_input_should_reject_verdict_mutation_fields`; `request_judge_challenge_should_submit_when_eligible`; `get_judge_challenge_should_return_proxy_error_when_ai_contract_leaks_private_key`; frontend `resolves eligible challenge status into a requestable view` | 已补齐 |
| C7. Runtime readiness / Ops control plane | `GET /api/debate/ops/judge-runtime-readiness`; `GET /internal/judge/ops/runtime-readiness`; [runtime_readiness_public_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/runtime_readiness_public_contract.py); [runtimeReadiness.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/ops-domain/src/runtimeReadiness.ts) | `local_reference_ready` / `env_blocked` public-safe 投影，RBAC，真实环境 blocker 不可渲染成 pass | `test_build_runtime_readiness_public_payload_should_project_safe_shape`; `test_build_runtime_readiness_public_payload_should_mark_local_reference_only`; `test_validate_runtime_readiness_public_contract_should_reject_forbidden_keys`; `get_judge_runtime_readiness_by_owner_should_require_judge_review_permission`; `get_judge_runtime_readiness_by_owner_should_proxy_public_safe_contract`; frontend `should call the ops runtime readiness endpoint with safe defaults` | 无缺口 |
| C8. Real-env evidence guard | [ai_judge_real_env_window_closure.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_real_env_window_closure.sh); [test_ai_judge_real_env_window_closure.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/tests/test_ai_judge_real_env_window_closure.sh) | preflight-only 不接受手工 ready、local_reference healthcheck 不能冒充 production pass、缺 evidence link 必须 env_blocked | `preflight missing links blocked`; `preflight no evidence blocked`; `artifact polluted blocked`; `artifact conflict ready overridden`; `production_artifact_store_local_reference` blocker checks | 无缺口 |
| C9. Ops calibration decision | `POST /api/debate/ops/judge-calibration-decisions`; [calibration_decision.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_ops/calibration_decision.rs); [OpsCalibrationDecisionActions.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/components/OpsCalibrationDecisionActions.tsx) | Ops-only、RBAC、idempotency、local reference evidence 明示，不写 official verdict | `post_ops_judge_calibration_decision_route_should_return_401_without_token`; `post_ops_judge_calibration_decision_route_should_return_409_for_missing_permission`; `create_judge_calibration_decision_by_owner_should_proxy_public_safe_contract`; frontend `maps advisor actions into safe calibration decision payloads` | 无缺口 |

## 3. 本轮补齐的缺口

### Challenge 状态读取非参与者拒绝

缺口：

1. 既有测试已覆盖 `judge_report` 非参与者读取拒绝。
2. 既有测试已覆盖 `public_verify` 非参与者读取拒绝。
3. 既有测试已覆盖 `challenge/request` 非参与者提交拒绝。
4. `GET /judge-report/challenge` 的非参与者读取拒绝缺少同层 handler route 测试。

修复：

1. 在 [debate_judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_judge.rs) 新增 `judge_challenge_route_should_forbid_non_participant`。
2. 测试构造非参与者 bound user，访问 `/api/debate/sessions/{session_id}/judge-report/challenge`。
3. 断言 HTTP `409 CONFLICT`，错误码为 `judge_report_read_forbidden`。

验证：

```bash
cargo test -p chat-server judge_challenge_route_should_forbid_non_participant
```

结果：

1. `handlers::debate_judge::tests::judge_challenge_route_should_forbid_non_participant ... ok`
2. `1 passed; 0 failed; 642 filtered out`

## 4. 暂停功能边界

1. `NPC Coach` / `Room QA` 仍为 paused advisory 历史资产。
2. `test_route_group_assistant.py`、`test_assistant_agent_routes.py`、`DebateAssistantPanel.test.tsx`、`debate-domain` assistant tests 只作为“不污染 official verdict / advisory-only fail-closed”的历史保护面。
3. 本轮不新增 assistant executor、ready-state、成本/延迟 guard、Ops evidence 或 stage closure。

## 5. 下一步

1. P1-D 执行 real-env readiness dry-run，复查 `local_reference_ready` / `env_blocked` 不会冒充 `pass`。
2. 若 P1-D 发现 runtime/readiness 口径漂移，优先补 guard 或 evidence，不改官方裁决合同语义。
3. 若后续继续修改 `request_report_query.rs` 或 `judge_command_routes.py`，按 [ai_judge_route_hotspot_inventory.md](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_route_hotspot_inventory.md) 的触发顺序考虑小拆分。


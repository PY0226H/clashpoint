# 当前开发计划

关联 slot：`default`
更新时间：2026-04-30
当前主线：`AI_judge_service P42（Interactive Guidance Plane / Advisory Agent Product Bridge）`
当前状态：进行中（P42 8.1 assistant advisory contract freeze、8.2 chat_server 用户侧 assistant advisory 代理、8.3 frontend Debate Room read model / UI、8.4 Room Context / Stage Summary 只读合同、8.5 deterministic advisory placeholder、8.6 Ops-only calibration decision action bridge、8.7 route hotspot split 与 8.8 local reference regression 已完成；下一步准备阶段收口，继续保持 advisory-only，不写官方裁决链）

---

## 0. 输入与决策依据

本轮计划基于以下材料生成：

1. 当前工作区代码事实（以代码为准，文档只作导航）。
2. [AI_Judge_Service-架构与技术栈决策方案-2026-04-13.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/AI_Judge_Service-架构与技术栈决策方案-2026-04-13.md)。
3. [AI_Judge_Service-企业级Agent服务设计方案-2026-04-13.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/AI_Judge_Service-企业级Agent服务设计方案-2026-04-13.md)。
4. [AI_Judge_Service-企业级Agent方案-章节完成度映射-2026-04-13.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/AI_Judge_Service-企业级Agent方案-章节完成度映射-2026-04-13.md)。
5. P41 阶段收口证据：
   - [20260429T112512Z-ai-judge-stage-closure-execute.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260429T112512Z-ai-judge-stage-closure-execute.md)
   - [ai_judge_stage_closure_evidence.md](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_stage_closure_evidence.md)

---

## 1. 当前代码事实快照

| 维度 | 当前代码事实 | P42 判断 |
| --- | --- | --- |
| P41 收口 | `completed.md` 已追加 B45，`todo.md` 已追加 C44，P41 活动计划已归档到 `docs/dev_plan/archive/20260429T112512Z-ai-judge-stage-closure-execute.md` | P42 可以从新一轮规划开始，不需要重复 P41 runtime readiness / release evidence / local reference regression |
| 真实环境 | `ai_judge_stage_closure_evidence.md` 显示 `runtime_ops_pack_status=local_reference_ready`，`p41_control_plane_status=env_blocked`，`p41_panel_shadow_candidate_status=env_blocked` | real-env pass 仍是环境阻塞后置项；P42 不宣称真实环境 pass |
| AI advisory shell | `ai_judge_service/app/applications/route_group_assistant.py` 已注册 `/internal/judge/apps/npc-coach/sessions/{session_id}/advice` 与 `/internal/judge/apps/room-qa/sessions/{session_id}/answer`；`assistant_agent_routes.py` 已构建 advisory context、capability boundary、Room Context Snapshot / Stage Summary 与官方裁决字段 sanitizer；`agent_runtime.py` 已支持本地 deterministic placeholder 开关 | AI internal shell、chat proxy、frontend read model、room context snapshot contract、deterministic placeholder、Ops-only calibration decision action bridge、route hotspot split 与 P42 local reference regression 已完成；下一步准备阶段收口 |
| Agent runtime | `ai_judge_service/app/applications/agent_runtime.py` 已注册 `judge`、`npc_coach`、`room_qa` profiles；`judge` enabled，`npc_coach` / `room_qa` 默认 `enabled=false`，本地打开 `AI_JUDGE_ASSISTANT_ADVISORY_PLACEHOLDER_ENABLED` 后才返回 deterministic advisory placeholder | P42 仍以 `not_ready / advisory` 合同和本地参考验证为主，不启用真实 LLM 建议 |
| AI 请求 DTO | `ai_judge_service/app/models.py` 已有 `NpcCoachAdviceRequest` 与 `RoomQaAnswerRequest`，均 `extra=forbid`，包含 `trace_id`、`query/question`、可选 `case_id`；chat_server 已新增对应 public DTO；`frontend/packages/debate-domain/src/index.ts` 已新增 typed API 与前端合同 guard | 请求/响应、shared context、stage summary 与 placeholder 合同已在 AI、chat 与 frontend 三层冻结；P42 本地参考证据已刷新 |
| chat 代理 | `chat/chat_server/src/config.rs` 的 `AiJudgeConfig` 已新增 `assistant_npc_coach_path`、`assistant_room_qa_path`、`assistant_timeout_ms`；`debate_judge.rs` 已注册 `/api/debate/sessions/{id}/assistant/npc-coach/advice` 与 `/assistant/room-qa/answer`；`assistant_advisory_proxy.rs` 已提供 AI internal key 注入、合同二次校验、forbidden official field fail-closed 与 proxy error 输出 | P42 chat_server 用户侧门面已完成；后续前端只能消费 chat proxy，不直连 AI |
| frontend 消费 | `frontend/packages/debate-domain/src/index.ts` 已有 public verify / challenge / assistant advisory typed API；`frontend/packages/app-shell/src/components/DebateAssistantPanel.tsx` 已新增 Debate Room 辅助咨询面板；`DebateRoomPage.tsx` 只接入组件与 caseId | P42 frontend product bridge 已完成；仍不能塞入 Ops Console 或直连 AI 服务 |
| Ops calibration decision bridge | `chat/chat_server/src/models/judge/calibration_decision_ops_proxy.rs` 已新增 Ops-only AI decision log proxy；`chat/chat_server/src/handlers/debate_ops/calibration_decision.rs` 注册 `/api/debate/ops/judge-calibration-decisions`，复用 `judge_review` RBAC、user/ip 限流、Idempotency-Key 与 no-secret 合同校验；`frontend/packages/ops-domain/src/runtimeReadiness.ts`、`OpsCalibrationDecisionActions.tsx` 与 `OpsCalibrationDecisionActionsModel.ts` 已把 Fairness Calibration recommended actions 映射为 accept/reject/defer/request_more_evidence 操作 | P42 8.6 / 8.7 已完成；该操作只进入 Ops Console，不进入普通 Debate Room，不写 official verdict plane |
| 热点文件 | 当前 `app_factory.py` 约 2346 行、`ops_read_model_pack.py` 约 2463 行、`debate_ops.rs` 约 4826 行、`OpsConsolePage.tsx` 约 1477 行；frontend assistant UI 已拆到 `DebateAssistantPanel.tsx`，Ops decision proxy 已落在独立 model helper，Ops decision route/UI 已拆到独立 handler/component/model | P42 热点拆分已完成；阶段收口前不继续新增产品逻辑到热点文件 |

---

## 2. 本轮主线定位

P42 的目标不是让 NPC/Room QA 直接“智能可用”，而是先把 Interactive Guidance Plane 的产品桥接、安全合同和跨层调用链打通：

1. AI 服务继续保持内部服务，客户端不直连 AI。
2. `chat_server` 作为唯一客户端门面，代理 NPC Coach / Room QA 请求。
3. 前端只展示 `advisoryOnly` 的辅助建议或未启用状态，不展示为官方裁决。
4. NPC Coach / Room QA 不写 `verdict_ledger`、不写 `judge_trace`、不触发 `Fairness Sentinel / Chief Arbiter`。
5. 当前 runtime disabled / not_ready 是允许状态；P42 先冻结产品与契约，后续再决定是否启用真实低延迟 LLM 执行器。

一句话：

`P42 要把“未来 Agent 入口”从 AI internal shell 推进到主业务产品桥接，但仍严格隔离 Official Verdict Plane 与 Interactive Guidance Plane。`

---

## 3. 架构方案第13章一致性校验

| 检查项 | P42 结论 |
| --- | --- |
| 角色一致性 | 不改变 Judge App 8 Agent 主链；NPC Coach / Room QA 作为独立 Interactive Guidance Plane，不能替代 Clerk / Recorder / Evidence / Panel / Sentinel / Arbiter / Opinion |
| 数据一致性 | 不新增平行 winner 写链；advisory 输出只读 `room_context_snapshot`、`stage_summary`、`knowledge_gateway`，不写 `verdict_ledger` |
| 门禁一致性 | 不绕过 Fairness Sentinel；assistant 响应不得含 `winner`、`verdictReason`、`fairnessGate`、`trustAttestation` 等官方裁决字段 |
| 边界一致性 | 所有响应必须显式 `advisoryOnly=true`、`officialVerdictAuthority=false`、`writesVerdictLedger=false`、`writesJudgeTrace=false` |
| 跨层一致性 | AI internal contract、chat proxy DTO/OpenAPI、frontend domain/UI、测试与计划文档同轮同步 |
| 收口一致性 | P42 本地回归可以是 `local_reference_ready`；真实 provider/callback/对象存储窗口不足时仍保持 `env_blocked` |

---

### 已完成/未完成矩阵

| 阶段 | 目标 | 状态 | 说明 |
| --- | --- | --- | --- |
| `ai-judge-p42-plan-bootstrap-current-state` | 基于当前代码与两份方案生成 P42 详细计划 | 已完成（文档） | 当前文件即本模块产物；映射文档同步为 P42 已启动 |
| `ai-judge-p42-assistant-advisory-contract-freeze-pack` | 冻结 NPC Coach / Room QA advisory contract | 已完成 | `assistant_advisory_contract_v1` 已版本化；forbidden official verdict output 从静默剥离升级为 fail-closed；runtime disabled 仍以 HTTP 200 + `not_ready` + `agent_not_enabled` 产品化返回 |
| `ai-judge-p42-chat-assistant-advisory-proxy-pack` | 将 assistant advisory 通过 chat_server 主业务门面代理 | 已完成 | config paths、request/response DTO、participant-only permission、user/ip 双限流、proxy no-secret guard、OpenAPI、route/model tests 已补；`not_ready` 与 `proxy_error` 均保持 200 body read model |
| `ai-judge-p42-client-assistant-advisory-read-model-pack` | 前端 Debate Room 接入 advisory read model | 已完成 | `debate-domain` typed API、前端 advisory-only 合同 guard、Debate Room 辅助咨询面板、not_ready 空态、forbidden official field fail-closed 与测试已补 |
| `ai-judge-p42-room-context-snapshot-contract-pack` | 稳定 Room Context / Stage Summary 只读合同 | 已完成 | AI shared context 精确字段白名单、chat 代理二次合同校验、frontend 可解释状态映射、`versionContext` 隔离与 redaction guard 已补齐 |
| `ai-judge-p42-advisory-runtime-placeholder-pack` | 提供不越权的 deterministic advisory placeholder | 已完成 | 默认仍 disabled/not_ready；本地打开 `AI_JUDGE_ASSISTANT_ADVISORY_PLACEHOLDER_ENABLED` 后 NPC Coach / Room QA 返回 `ok` + advisory-only deterministic 输出；生产环境禁止启用 |
| `ai-judge-p42-calibration-decision-ops-action-bridge-pack` | 评估并补齐 calibration decision log 的 Ops 操作桥接 | 已完成 | Go 决策：只进入 Ops Console；chat_server 新增 Ops-only POST proxy、`judge_review` RBAC、幂等键、限流、OpenAPI 与 no-secret 合同校验；frontend Ops Console 可对 fairness calibration recommended actions 执行 accept/reject/defer/request_more_evidence；不进入普通用户辩论页 |
| `ai-judge-p42-route-hotspot-split-pack` | 控制 P42 新增代理和 UI 逻辑热点 | 已完成 | chat Ops calibration decision route 拆到 `handlers/debate_ops/calibration_decision.rs`；frontend calibration decision action UI/payload builder 拆到 `OpsCalibrationDecisionActions.tsx` 与 `OpsCalibrationDecisionActionsModel.ts`；行为不变，目标测试通过 |
| `ai-judge-p42-local-reference-regression-pack` | 刷新 P42 本地参考证据 | 已完成 | 2026-04-30 已刷新 AI/chat/frontend/harness 本地参考证据；runtime ops pack 为 `local_reference_ready`，P41 control plane 与 panel shadow candidate 仍为 `env_blocked` |
| `ai-judge-p42-stage-closure-execute` | P42 阶段收口 | 待执行 | completed/todo/archive 同步；真实环境或 LLM 启用项按债务归档 |
| `ai-judge-real-env-pass-window-execute-on-env` | 真实环境 pass 补证 | 阻塞 | 继续等待真实样本、真实 provider/callback、生产对象存储与真实服务窗口 |

---

### 下一开发模块建议

1. 准备 P42 阶段收口前的本地参考证据刷新与完成/债务归档
2. 执行 `ai-judge-p42-stage-closure-execute`
3. 继续保持 real-env pass 为环境阻塞后置项

### 模块完成同步历史

- 2026-04-29：完成 `ai-judge-p41-stage-closure-execute`；P41 runtime readiness / calibration decision log / panel shadow candidate / release evidence / route hotspot split / local reference regression 已归档，真实环境 pass 作为 C44 环境依赖债务保留。
- 2026-04-29：生成 `ai-judge-p42-plan-bootstrap-current-state`；下一轮主线定位为 Interactive Guidance Plane 产品桥接，先冻结 advisory-only 合同，再推进 chat/frontend 代理。
- 2026-04-29：推进 `ai-judge-p42-assistant-advisory-contract-freeze-pack`；冻结 assistant_advisory_contract_v1，新增 advisory-only 顶层白名单、capabilityBoundary validator、forbidden official verdict output fail-closed、not_ready/cacheProfile 合同与请求 DTO 边界测试；目标 pytest、ruff 与 post-module full gate 均通过
- 2026-04-30：推进 `ai-judge-p42-chat-assistant-advisory-proxy-pack`；chat_server 新增 NPC Coach / Room QA 用户侧代理、config path、DTO/OpenAPI、participant-only 权限、user/ip session 限流、AI internal key 注入、caseId/session 绑定校验、forbidden official verdict field fail-closed 与 targeted route/model tests；目标测试、`cargo check -p chat-server` 与 `post-module-test-guard --mode full` 均通过
- 2026-04-30：推进 `ai-judge-p42-client-assistant-advisory-read-model-pack`；完成 frontend debate-domain typed assistant advisory API、前端 advisory-only 合同 guard、Debate Room 辅助咨询面板与 not_ready/forbidden-field 测试；frontend package tests/typecheck/lint 与 workspace typecheck/lint 均通过
- 2026-04-30：推进 `ai-judge-p42-room-context-snapshot-contract-pack`；完成 advisory Room Context Snapshot / Stage Summary 精确白名单、AI/chat/frontend 三层合同校验、versionContext 隔离与安全状态提示测试；AI targeted、chat targeted、frontend test/typecheck/lint 均通过
- 2026-04-30：推进 `ai-judge-p42-advisory-runtime-placeholder-pack`；完成本地开关控制的 deterministic assistant advisory placeholder：默认仍 disabled/not_ready，打开 AI_JUDGE_ASSISTANT_ADVISORY_PLACEHOLDER_ENABLED 后 NPC Coach / Room QA 返回 ok advisory-only 输出；生产环境禁止启用；AI/chat/frontend placeholder 合同与渲染测试已补
- 2026-04-30：推进 `ai-judge-p42-calibration-decision-ops-action-bridge-pack`；Go 决策为只进入 Ops Console：chat_server 新增 `/api/debate/ops/judge-calibration-decisions` Ops-only 代理、`judge_review` RBAC、Idempotency-Key、user/ip 限流、AI internal key 注入、no-secret 合同校验与 OpenAPI；frontend ops-domain/OpsConsolePage 可把 fairness calibration recommended actions 写成人工决策日志；普通 Debate Room 不接入该操作
- 2026-04-30：推进 `ai-judge-p42-route-hotspot-split-pack`；将 Ops calibration decision route 从 `debate_ops.rs` 下沉到 `handlers/debate_ops/calibration_decision.rs`，将 Ops Console calibration action UI 与 payload builder 下沉到 `OpsCalibrationDecisionActions.tsx` / `OpsCalibrationDecisionActionsModel.ts`；`debate_ops.rs` 约 4989 -> 4826 行，`OpsConsolePage.tsx` 约 1575 -> 1477 行，行为不变
- 2026-04-30：推进 `ai-judge-p42-local-reference-regression-pack`；刷新 P42 本地参考证据：AI ruff/full pytest、chat fmt + assistant advisory/runtime_readiness/judge_challenge/ops_judge 过滤、frontend debate-domain/app-shell/typecheck/lint、runtime ops pack、stage closure evidence 与 harness docs lint 均通过；证据仍保持 `local_reference_ready` / `env_blocked`，不宣称 real-env pass

---

## 7. Batch 计划

| Batch | 主题 | 目标 | 状态 |
| --- | --- | --- | --- |
| Batch-A | `assistant-advisory-contract` | 冻结 AI internal advisory contract，确保 `not_ready`、`advisoryOnly`、sanitizer 与 forbidden official fields 均稳定 | 已完成 |
| Batch-B | `chat-product-proxy` | 在 chat_server 增加用户侧 NPC Coach / Room QA 代理，完成权限、限流、OpenAPI 与 proxy no-secret guard | 已完成 |
| Batch-C | `frontend-read-model` | Debate Room 增加 assistant advisory 入口与 domain typed API，清晰展示辅助性质和未启用状态 | 已完成 |
| Batch-D | `room-context-contract` | 稳定 shared room context / stage summary / case id 映射，不暴露官方裁决私有字段 | 已完成 |
| Batch-E | `runtime-placeholder` | 在真实 LLM 执行器前先提供 deterministic / not_ready 安全占位能力，便于端到端产品验收 | 已完成 |
| Batch-F | `ops-calibration-action-bridge` | 判断 calibration decision log 是否需要 chat/frontend Ops 操作桥接；若做，必须只进入 Ops，不进用户辩论页 | 已完成 |
| Batch-G | `hotspot-split-regression-closure` | 拆分热点、刷新本地参考证据并阶段收口 | 进行中（热点拆分与本地参考证据已刷新；阶段收口待执行） |

---

## 8. 详细开发计划

### 8.1 `ai-judge-p42-assistant-advisory-contract-freeze-pack`

**目标**

冻结 NPC Coach / Room QA 的 AI internal contract，让后续 chat/frontend 可以依赖一个稳定、可审计、不可越权的响应结构。

**当前代码入口**

1. [assistant_agent_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_agent_routes.py)
2. [route_group_assistant.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_assistant.py)
3. [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py)
4. [models.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/models.py)
5. [test_assistant_agent_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/tests/test_assistant_agent_routes.py)
6. [test_app_factory_assistant_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/tests/test_app_factory_assistant_routes.py)

**实施步骤**

1. 定义 `assistant_advisory_contract_v1` 顶层字段白名单：
   - `version`
   - `agentKind`
   - `sessionId`
   - `caseId`
   - `advisoryOnly`
   - `status`
   - `accepted`
   - `errorCode`
   - `errorMessage`
   - `capabilityBoundary`
   - `sharedContext`
   - `advisoryContext`
   - `output`
   - `cacheProfile`
2. 对 `capabilityBoundary` 增加 contract validator，固定：
   - `mode=advisory_only`
   - `officialVerdictAuthority=false`
   - `writesVerdictLedger=false`
   - `writesJudgeTrace=false`
   - `canTriggerOfficialJudgeRoles=false`
3. 增加 forbidden key fail-closed 校验，覆盖：
   - `winner`
   - `verdictReason`
   - `verdictLedger`
   - `fairnessGate`
   - `trustAttestation`
   - `rawPrompt`
   - `rawTrace`
   - `artifactRef`
   - `providerConfig`
4. 冻结 `not_ready` 语义：
   - runtime disabled 时 HTTP 仍可返回 200
   - body 内 `status=not_ready`
   - `accepted=false`
   - `errorCode=agent_not_enabled`
   - 前端可展示“辅助功能未启用/稍后再试”
5. 保留 current reserved executor，不在本模块启用真实 LLM。
6. 为 `NpcCoachAdviceRequest` / `RoomQaAnswerRequest` 增加必要边界测试：
   - 空 query/question
   - 过长 query/question
   - invalid session id
   - extra field rejection
7. 如果新增 contract helper，优先放在 `assistant_agent_routes.py` 或新文件 `assistant_advisory_contract.py`，不要继续扩张 `app_factory.py`。

**DoD**

1. AI internal assistant 响应有稳定 `version`。
2. sanitizer 和 validator 同时保护 forbidden official verdict fields。
3. `not_ready` 被当作产品可消费状态，而不是异常失败。
4. 测试覆盖 NPC Coach 与 Room QA 两条路径。

**建议验证**

1. `ai_judge_service/.venv/bin/python -m pytest -q ai_judge_service/tests/test_assistant_agent_routes.py ai_judge_service/tests/test_agent_runtime.py ai_judge_service/tests/test_route_group_assistant.py ai_judge_service/tests/test_app_factory_assistant_routes.py`
2. `ai_judge_service/.venv/bin/python -m ruff check ai_judge_service/app ai_judge_service/tests`

---

### 8.2 `ai-judge-p42-chat-assistant-advisory-proxy-pack`

**完成状态**

已完成。落地文件包括：

1. [config.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/config.rs)：新增 assistant advisory proxy path / timeout 配置与默认值。
2. [assistant_advisory_proxy.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/assistant_advisory_proxy.rs)：新增 chat 侧 AI proxy helper、contract validator、forbidden official/private field fail-closed 与稳定 proxy error output。
3. [request_report_query.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/request_report_query.rs)：新增 NPC Coach / Room QA AppState 方法、participant-only 权限、caseId/session 绑定校验与 AI internal key 调用。
4. [debate_judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_judge.rs)：新增用户侧 handler、user/session + ip/session 双限流、稳定 409/429 错误语义。
5. [openapi.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/openapi.rs)：同步新增 route 与 schema。
6. [request_judge_report_query.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/tests/request_judge_report_query.rs)：覆盖 not_ready 合同透传、forbidden official output 转 proxy_error、非参与者 forbidden。

本模块验证已通过：

1. `cargo fmt --all -- --check`
2. `cargo test -p chat-server request_npc_coach_advice_should_proxy_not_ready_advisory_contract -- --nocapture`
3. `cargo test -p chat-server request_room_qa_answer_should_return_proxy_error_when_ai_output_leaks_verdict -- --nocapture`
4. `cargo test -p chat-server request_npc_coach_advice_should_forbid_non_participant -- --nocapture`
5. `cargo test -p chat-server assistant_npc_coach_route_should_forbid_non_participant -- --nocapture`
6. `cargo test -p chat-server ai_judge_alert_outbox_defaults_should_be_stable -- --nocapture`
7. `cargo check -p chat-server`

**目标**

让客户端仍只通过 `chat_server` 调用 assistant advisory，符合“客户端永远不直连 AI 服务”的架构决策。

**当前代码入口**

1. [config.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/config.rs)
2. [debate_judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_judge.rs)
3. [request_report_query.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/request_report_query.rs)
4. [runtime_readiness_ops_projection.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/runtime_readiness_ops_projection.rs)
5. [judge/types.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/types.rs)
6. [openapi.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/openapi.rs)

**建议接口**

1. `POST /api/debate/sessions/{id}/assistant/npc-coach/advice`
2. `POST /api/debate/sessions/{id}/assistant/room-qa/answer`

**实施步骤**

1. 在 `AiJudgeConfig` 新增：
   - `assistant_npc_coach_path`
   - `assistant_room_qa_path`
   - `assistant_timeout_ms`
2. 默认路径分别映射 AI internal：
   - `/internal/judge/apps/npc-coach/sessions/:session_id/advice`
   - `/internal/judge/apps/room-qa/sessions/:session_id/answer`
3. 在 chat model 层新增 typed DTO：
   - `RequestNpcCoachAdviceInput`
   - `RequestRoomQaAnswerInput`
   - `JudgeAssistantAdvisoryOutput`
4. 复用 session 可读权限：
   - session 参与者可以请求用户侧 advice/answer
   - Ops 可按现有权限查看，但不需要新 Ops-only 入口
   - outsider 返回稳定权限错误
5. 增加 user/session + ip/session 双限频：
   - 初始建议：user/session 20/min，ip/session 60/min
   - 不能影响 judge report/challenge 既有限频
6. 代理 AI internal 请求：
   - 注入 `x-ai-internal-key`
   - 透传 `traceId`
   - 自动填 session id
   - 可选透传 `caseId`
7. 增加 chat 侧 no-secret / no-official-field guard：
   - 如果 AI 返回 forbidden official verdict/private 字段，chat 侧转为 `proxy_error` 或 contract violation output
   - 不把 raw AI payload 原样给前端
8. 更新 OpenAPI：
   - 200 / 400 / 401 / 403 / 404 / 409 / 429 / 500
   - `not_ready` 属于 200 body 状态
9. 测试覆盖：
   - participant 成功代理
   - outsider forbidden
   - AI 5xx / bad JSON / timeout -> stable proxy error
   - forbidden field -> contract violation
   - rate limit -> 429

**DoD**

1. chat_server 成为用户侧唯一 assistant advisory 门面。
2. AI internal key、AI service URL、forbidden field 均不出现在响应。
3. 未启用 runtime 时前端仍能得到稳定 `not_ready` read model。
4. OpenAPI 与 route/model tests 同步。

**建议验证**

1. `cargo fmt --all -- --check`
2. `cargo test -p chat-server assistant_advisory`
3. `cargo test -p chat-server judge_assistant`
4. `cargo test -p chat-server request_judge_report_query`

---

### 8.3 `ai-judge-p42-client-assistant-advisory-read-model-pack`

状态：已完成（2026-04-30）

**目标**

在 Debate Room 提供轻量 assistant advisory 产品入口，用户能看到“这是辅助建议，不是官方裁决”，并能优雅处理 `not_ready`。

**当前代码入口**

1. [debate-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/debate-domain/src/index.ts)
2. [debate-domain index.test.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/debate-domain/src/index.test.ts)
3. [DebateRoomPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/DebateRoomPage.tsx)
4. [app-shell package](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell)

**实施步骤**

1. 在 `debate-domain` 新增 typed API：
   - `requestNpcCoachAdvice`
   - `requestRoomQaAnswer`
   - `JudgeAssistantAdvisoryOutput`
   - `AssistantCapabilityBoundary`
2. API 层做 response resolver：
   - 缺 `advisoryOnly=true` 视为 invalid
   - `officialVerdictAuthority=true` 视为 invalid
   - forbidden output keys 视为 invalid
3. `DebateRoomPage` 新增紧凑入口：
   - NPC Coach：输入“我该怎么回应？”
   - Room QA：输入“当前争点是什么？”
   - 空态显示 runtime 未启用或暂无上下文
4. UI 不使用营销式大卡片；放在辩论室工具/侧栏区域，保持工作流紧凑。
5. 文案边界：
   - 明确“辅助建议”
   - 不说“裁判认为”
   - 不展示 winner / score / verdict authority
6. 错误态：
   - `not_ready`
   - `proxy_error`
   - `contract_violation`
   - `rate_limited`
7. 测试覆盖：
   - domain resolver
   - page render not_ready
   - disabled/no context
   - forbidden fields fail-closed

**DoD**

1. Web/Desktop 共用 `debate-domain`，不在双端重复业务逻辑：已完成。
2. Debate Room 能调用 chat proxy 并展示安全 read model：已完成。
3. 所有 UI 输出都保持 advisory-only，不改变 judge report 主流程：已完成。

**完成结果**

1. `debate-domain` 已新增 `requestNpcCoachAdvice`、`requestRoomQaAnswer`、`JudgeAssistantAdvisoryOutput`、`AssistantCapabilityBoundary` 与 `resolveJudgeAssistantAdvisoryView`。
2. frontend response resolver 已二次校验 `advisoryOnly=true`、`officialVerdictAuthority=false`、`writesVerdictLedger=false`、`writesJudgeTrace=false`，并对 forbidden official fields fail-closed。
3. Debate Room 已接入 `DebateAssistantPanel`，展示 NPC Coach / Room QA 的紧凑入口、`not_ready` 空态和 “辅助建议，不是官方裁决” 边界。
4. 已补 `debate-domain` API / resolver 测试与 `AssistantAdvisoryResult` not_ready render 测试。

**建议验证**

1. `pnpm --dir frontend --filter @echoisle/debate-domain test`
2. `pnpm --dir frontend --filter @echoisle/app-shell test`
3. `pnpm --dir frontend typecheck`
4. `pnpm --dir frontend lint`

---

### 8.4 `ai-judge-p42-room-context-snapshot-contract-pack`

**目标**

稳定 Room Context Snapshot 与 Stage Summary，让 NPC Coach / Room QA 能读取“房间当前状态”，但不能读取或泄漏官方裁决私有链路。

**当前代码入口**

1. [assistant_agent_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_agent_routes.py)
2. [bootstrap_ops_panel_replay_payload_helpers.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/bootstrap_ops_panel_replay_payload_helpers.py)
3. [request_report_query.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/request_report_query.rs)
4. [DebateRoomPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/DebateRoomPage.tsx)

**实施步骤**

1. 冻结 `roomContextSnapshot` 字段白名单：
   - `sessionId`
   - `scopeId`
   - `caseId`
   - `workflowStatus`
   - `latestDispatchType`
   - `topicDomain`
   - `phaseReceiptCount`
   - `finalReceiptCount`
   - `updatedAt`
   - `officialVerdictFieldsRedacted`
2. 冻结 `stageSummary`：
   - `stage`
   - `workflowStatus`
   - `latestDispatchType`
   - `hasPhaseReceipt`
   - `hasFinalReceipt`
   - `officialVerdictFieldsRedacted`
3. 保持 `ruleVersion` / `rubricVersion` / `judgePolicyVersion` 仅作为版本上下文，不作为可见裁决说明。
4. chat 侧在代理前校验 session 存在、用户可读、case id 与 session 绑定。
5. frontend 只将这些字段映射为状态提示，不展示内部版本 hash 或 trace。
6. 增加 contract fixture，方便 chat/frontend 同步。

**DoD**

1. Room QA 可解释“当前上下文阶段”，但不会提前泄漏官方裁决。
2. NPC Coach 可读取当前上下文，不接收用户画像、历史胜率、消费能力等身份噪音。
3. `officialVerdictFieldsRedacted=true` 成为合同要求。

**建议验证**

1. AI assistant contract tests。
2. chat proxy contract tests。
3. frontend domain resolver tests。

**完成结果**

1. AI internal advisory response 已冻结 `roomContextSnapshot` 与 `stageSummary` 精确字段白名单，`ruleVersion` / `rubricVersion` / `judgePolicyVersion` 仅保留在 `versionContext`。
2. chat proxy 已对 AI 返回做 Room Context / Stage Summary 二次校验，并要求 `advisoryContext.roomContextSnapshot` 与 `sharedContext` 一致。
3. frontend `debate-domain` 已补 room context / stage summary type guard，Debate Room 面板只展示上下文阶段、receipt 摘要与 workflow/dispatch 状态，不暴露版本 hash、trace 或官方裁决私有字段。
4. `officialVerdictFieldsRedacted=true` 已成为 AI/chat/frontend 合同要求；带非白名单字段的 shared context 会 fail-closed。

**实际验证**

1. `/Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/python -m pytest tests/test_assistant_agent_routes.py tests/test_app_factory_assistant_routes.py tests/test_bootstrap_ops_panel_replay_payload_helpers.py`
2. `cargo test -p chat-server request_npc_coach_advice_should_proxy_not_ready_advisory_contract -- --nocapture`
3. `cargo test -p chat-server request_room_qa_answer_should_return_proxy_error_when_ai_output_leaks_verdict -- --nocapture`
4. `cargo check -p chat-server`
5. `pnpm --dir frontend --filter @echoisle/debate-domain test`
6. `pnpm --dir frontend --filter @echoisle/app-shell test`
7. `pnpm --dir frontend typecheck`
8. `pnpm --dir frontend lint`

---

### 8.5 `ai-judge-p42-advisory-runtime-placeholder-pack`

**目标**

在真实低延迟 LLM 执行器之前，提供一个 deterministic、可测、不可越权的 placeholder，使产品链路能完成端到端验收。

**约束**

1. 不接真实 provider。
2. 不基于 prompt 生成裁决。
3. 不输出 winner、score、verdict reason。
4. 允许输出：
   - `status=not_ready`
   - `suggestedNextQuestions`
   - `availableContext`
   - `safeGuidanceSummary`
   - `limitations`

**实施步骤**

1. 在 AI runtime 中引入可配置 placeholder executor：
   - 默认仍 disabled 或 `not_ready`
   - 仅在本地配置开关开启时输出 deterministic placeholder
2. NPC Coach placeholder 只给：
   - “你可以要求系统总结当前争点”
   - “你可以补充证据或回应对方未回应点”
   - “此建议不代表官方裁决”
3. Room QA placeholder 只给：
   - 当前 stage
   - 是否已有 phase/final context
   - 可问问题列表
4. 测试确保 placeholder 不含官方裁决字段。
5. 如果启用开关涉及 config，必须同步文档和默认值说明。

**DoD**

1. 本地可完整演示 assistant advisory 端到端链路。
2. 默认生产语义仍安全，不会误导用户以为 AI 正在正式判定。
3. placeholder 能被后续真实 executor 平滑替换，但不保留长期双轨旧语义。

**建议验证**

1. AI route tests。
2. chat proxy tests。
3. frontend not_ready/placeholder render tests。

**完成结果**

1. AI runtime 已新增本地开关控制的 deterministic placeholder executor；默认 `AI_JUDGE_ASSISTANT_ADVISORY_PLACEHOLDER_ENABLED=false` 时仍返回 `not_ready`。
2. 本地打开 `AI_JUDGE_ASSISTANT_ADVISORY_PLACEHOLDER_ENABLED=true` 后，NPC Coach / Room QA 返回 `status=ok`、`accepted=true`、`safeGuidanceSummary`、`suggestedNextQuestions`、`availableContext` 与 `limitations`，且不接真实 provider、不输出官方裁决字段。
3. 生产环境下启用 placeholder 会在 settings 校验阶段 fail-closed，避免把本地验收占位能力误带入 production。
4. chat proxy 已覆盖 `ok` placeholder 合同；frontend 已能把 `safeGuidanceSummary` 和 `suggestedNextQuestions` 渲染成 advisory-only read model。

**实际验证**

1. `/Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/python -m pytest tests/test_agent_runtime.py tests/test_assistant_agent_routes.py tests/test_app_factory_assistant_routes.py tests/test_settings.py`
2. `cargo test -p chat-server request_npc_coach_advice_should_proxy_ready_placeholder_contract -- --nocapture`
3. `cargo test -p chat-server request_npc_coach_advice_should_proxy_not_ready_advisory_contract -- --nocapture`
4. `cargo test -p chat-server request_room_qa_answer_should_return_proxy_error_when_ai_output_leaks_verdict -- --nocapture`
5. `cargo check -p chat-server`
6. `pnpm --dir frontend --filter @echoisle/debate-domain test`
7. `pnpm --dir frontend --filter @echoisle/app-shell test`
8. `pnpm --dir frontend typecheck`
9. `pnpm --dir frontend lint`

---

### 8.6 `ai-judge-p42-calibration-decision-ops-action-bridge-pack`

**目标**

评估并按需补齐 calibration decision log 的 Ops 操作桥接，解决 P41 后留下的“AI 内部 route 已有，是否需要 chat/frontend 操作面”的问题。

**当前代码入口**

1. [fairness_calibration_decision_log.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_calibration_decision_log.py)
2. [runtime_readiness_public_projection.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/runtime_readiness_public_projection.py)
3. [runtimeReadiness.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/ops-domain/src/runtimeReadiness.ts)
4. [OpsConsolePage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/OpsConsolePage.tsx)

**实施步骤**

1. 先做 Go/No-Go 评估：
   - 是否已有足够操作需求？
   - 是否只需继续显示 summary？
   - 是否需要 accept/reject/defer/request_more_evidence 操作代理？
2. 如果 Go：
   - chat_server 增加 Ops-only calibration decision action proxy
   - frontend Ops Console 增加操作入口
   - RBAC 使用 JudgeReview 或更细权限
   - 幂等键、审计、错误语义、OpenAPI 同步
3. 如果 No-Go：
   - 在当前计划和完成度映射写清后置条件
   - 不把操作入口塞入 Debate Room
4. 无论 Go/No-Go，都要保持 release gate / runtime readiness 的 summary 可解释。

**DoD**

1. 明确 calibration decision log 是否进入本轮产品操作面。
2. 若进入，只能进入 Ops 面，不能进入普通用户辩论页。
3. 若后置，必须记录触发条件和完成定义。

**建议验证**

1. `cargo test -p chat-server ops_judge`
2. `pnpm --dir frontend --filter @echoisle/ops-domain test`
3. `pnpm --dir frontend --filter @echoisle/app-shell test`

**完成结果（2026-04-30）**

1. Go/No-Go 结论：Go，但只进入 Ops Console，不进入普通用户 Debate Room。
2. chat_server：新增 `calibration_decisions_path` / `calibration_decisions_timeout_ms` 配置、`CreateJudgeCalibrationDecisionOpsInput/Output` DTO、`calibration_decision_ops_proxy.rs`、`POST /api/debate/ops/judge-calibration-decisions` route 与 OpenAPI schema；权限复用 `judge_review`，并补 user/ip 限流、Idempotency-Key、AI internal key 注入、proxy error 与 no-secret/forbidden-key fail-closed。
3. frontend：`ops-domain` 新增 `createOpsJudgeCalibrationDecision` typed API；`OpsConsolePage` 在 Fairness Calibration recommended actions 上提供 `accept_for_review`、`request_more_evidence`、`defer`、`reject` 四类操作，payload 只引用 public-safe readiness/action evidence。
4. 隔离边界：该桥接不写 official verdict plane，不进入 Debate Room，不让客户端直连 `ai_judge_service`；生产可信度仍以 AI 内部 decision log 与 runtime readiness summary 为准。

---

### 8.7 `ai-judge-p42-route-hotspot-split-pack`

**目标**

控制 P42 新增能力对热点文件的继续膨胀。

**热点基线**

1. `ai_judge_service/app/app_factory.py`：约 2346 行。
2. `ai_judge_service/app/applications/ops_read_model_pack.py`：约 2463 行。
3. `chat/chat_server/src/handlers/debate_ops.rs`：约 4826 行。
4. `frontend/packages/app-shell/src/pages/OpsConsolePage.tsx`：约 1477 行。

**实施步骤**

1. AI：
   - assistant contract validator 可拆到 `assistant_advisory_contract.py`
   - app factory 只保留 route registration wiring
2. chat：
   - 新增 `models/judge/assistant_advisory_proxy.rs` 或等价 helper
   - handler 只做 auth/rate-limit/log/response
3. frontend：
   - domain resolver 放 `debate-domain`
   - 页面 UI 尽量抽轻量子组件，避免 `DebateRoomPage.tsx` 大幅膨胀
4. 补测试时优先测 helper 和 domain，不把全部断言塞进端到端页面测试。

**DoD**

1. 新增逻辑不主要沉积在现有热点文件。
2. helper 有单测覆盖 forbidden key / contract / proxy error。
3. 不因为拆分改变公开行为。

**完成结果（2026-04-30）**

1. chat：`POST /api/debate/ops/judge-calibration-decisions` handler 与 rate-limit/idempotency wiring 已从 `debate_ops.rs` 拆到 `chat/chat_server/src/handlers/debate_ops/calibration_decision.rs`；OpenAPI path 继续通过 `debate_ops` re-export 暴露，公开 route 不变。
2. frontend：Fairness Calibration 操作按钮拆到 `OpsCalibrationDecisionActions.tsx`，reason/idempotency/payload builder 拆到 `OpsCalibrationDecisionActionsModel.ts`；`OpsConsolePage.tsx` 只保留 query/mutation 装配。
3. 热点变化：`debate_ops.rs` 约 4989 -> 4826 行；`OpsConsolePage.tsx` 约 1575 -> 1477 行。
4. 行为边界：普通 Debate Room 未接入 calibration actions；official verdict plane 未新增写入路径。

---

### 8.8 `ai-judge-p42-local-reference-regression-pack`

**目标**

刷新 P42 本地参考证据，证明 assistant advisory 产品桥接不会破坏 P41 的 runtime readiness、challenge、trust、fairness 和 release evidence。

**建议验证矩阵**

1. AI 服务：
   - `ai_judge_service/.venv/bin/python -m ruff check ai_judge_service/app ai_judge_service/tests`
   - assistant targeted tests
   - runtime readiness / fairness calibration / panel runtime / registry release gate / trust challenge targeted tests
   - `cd ai_judge_service && /Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/python -m pytest -q`
2. chat：
   - `cargo fmt --all -- --check`
   - assistant advisory proxy targeted tests
   - `cargo test -p chat-server runtime_readiness`
   - `cargo test -p chat-server judge_challenge`
   - `cargo test -p chat-server ops_judge`
3. frontend：
   - `pnpm --dir frontend --filter @echoisle/debate-domain test`
   - `pnpm --dir frontend --filter @echoisle/app-shell test`
   - `pnpm --dir frontend typecheck`
   - `pnpm --dir frontend lint`
4. harness：
   - `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`
   - `bash scripts/harness/ai_judge_stage_closure_evidence.sh --root /Users/panyihang/Documents/EchoIsle`
   - `bash scripts/quality/harness_docs_lint.sh --root /Users/panyihang/Documents/EchoIsle`

**DoD**

1. P42 本地回归显示 assistant advisory 链路可被本地验证。
2. P41 control plane 仍不被误标为 real-env pass。
3. runtime ops pack / stage closure evidence 能反映 P42 当前状态。

**完成结果（2026-04-30）**

1. AI 服务：`ruff check app tests` 与全量 `pytest -q` 均通过。
2. chat：`cargo fmt --all -- --check`、assistant advisory proxy 三条 targeted tests、`runtime_readiness`、`judge_challenge`、`ops_judge` 过滤均通过。
3. frontend：`@echoisle/debate-domain` tests、`@echoisle/app-shell` tests、workspace `typecheck` 与 `lint` 均通过。
4. harness：`ai_judge_runtime_ops_pack.sh --allow-local-reference` 输出 `local_reference_ready`，summary 为 `artifacts/harness/20260430T043459Z-ai-judge-runtime-ops-pack.summary.md`；`ai_judge_stage_closure_evidence.sh` 输出 `pass`，summary 为 `artifacts/harness/20260430T043505Z-ai-judge-stage-closure-evidence.summary.md`；`harness_docs_lint.sh` 通过。
5. 证据口径：`p41_control_plane_status=env_blocked`、`p41_panel_shadow_candidate_status=env_blocked`，未宣称真实环境 pass。

---

### 8.9 `ai-judge-p42-stage-closure-execute`

**目标**

P42 主体完成后按 stage closure 规则归档，避免活动计划长期膨胀。

**实施步骤**

1. 执行 stage closure evidence。
2. 将完成模块写入 `completed.md`。
3. 将真实 LLM executor、真实环境 pass、生产对象存储或未进入本轮的操作桥接写入 `todo.md`。
4. 归档当前计划到 `docs/dev_plan/archive/`。
5. 重置 `当前开发计划.md`。

**DoD**

1. `completed.md` 只记录 P42 主体完成快照。
2. `todo.md` 只记录明确后置债务。
3. 活动计划归档后能作为 P43 输入。

---

## 9. 风险与边界

| 风险 | 处理方式 |
| --- | --- |
| 用户把辅助建议误认为官方裁决 | UI、DTO、contract 均强制 `advisoryOnly=true`；文案避免“裁判认为” |
| advisory 输出泄漏 official verdict fields | AI sanitizer + chat proxy guard + frontend resolver 三层 fail-closed |
| runtime disabled 被误当错误 | 约定 `not_ready` 是 200 body 状态，前端显示空态 |
| 新增 proxy 放大热点文件 | P42 单独设置 hotspot split pack，新增 helper/domain/component |
| 真实 provider 不可用 | 本轮不依赖真实 provider；真实启用作为后置 |
| real-env pass 口径混淆 | 继续保留 `local_reference_ready` / `env_blocked` 分层 |

---

## 10. 本轮不做事项

1. 不启用 NPC Coach / Room QA 真实 LLM 生产执行器。
2. 不让用户直接连接 `ai_judge_service`。
3. 不让 assistant 写入 `verdict_ledger`、`judge_trace`、`fairness_report` 或 review queue。
4. 不将 topic memory、用户画像、历史胜率、消费能力写入 official verdict plane。
5. 不推进 Identity Proof、Constitution Registry、Reason Passport、第三方 review network 或 on-chain anchor。
6. 不把 `local_reference_ready` 写成 real-env `pass`。

---

## 11. 下一轮启动建议

1. 准备 `ai-judge-p42-stage-closure-execute` 的本地参考证据刷新、完成快照与后置债务归档。
2. 阶段收口时只把真实 LLM executor、真实样本、真实 provider/callback、生产对象存储和 real-env pass 写成后置环境债务。
3. 本地参考证据已刷新；阶段收口前继续保持 `local_reference_ready` / `env_blocked` 口径。
4. 真实 LLM executor、真实样本、真实 provider/callback、生产对象存储和 real-env pass 继续等待环境窗口。

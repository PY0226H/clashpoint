# EchoIsle Architecture Map

更新时间：2026-05-04
状态：当前主线轻量代码地图（AI Judge 当前有效主线为 Official Verdict Plane；虚拟裁判 NPC 下一阶段正在开发；NPC Coach / Room QA 已暂停）

---

## 1. 目的

这份文档不是完整架构设计书，而是给人和 agent 使用的轻量代码地图。

它主要回答四个问题：

1. 仓库当前主线有哪些子系统
2. 每个子系统大致负责什么
3. 遇到某类需求时，第一眼应该去哪里看代码
4. 哪些目录是运行主线，哪些目录更偏测试、脚本、文档或辅助资产

使用原则：

1. 本文件只给“第一跳入口”，不要把它当实现细节索引。
2. 找到相关入口后，再按代码里的 `mod`、router、exports 或测试继续下钻。
3. 如果你要看工作规则，优先读 `AGENTS.md` 与 `docs/harness/`。

---

## 2. 仓库主线总览

当前 EchoIsle 先按 7 个区域理解：

1. `chat/`
   - Rust 后端 workspace
   - 主 API、通知服务、分析服务、AI SDK、Bot/RAG 辅助服务、模拟器、迁移与后端专项脚本

2. `ai_judge_service/`
   - Python FastAPI AI 裁判服务
   - 裁判 dispatch、回调、RAG、trace、registry、trust、fairness、panel runtime、review、replay 与内部 ops 读路径

3. `npc_service/`
   - Python FastAPI 虚拟裁判 NPC 服务
   - `llm_executor_v1` 主执行路径、`rule_executor_v1` fallback、OpenAI-compatible provider、候选动作 guard、LLM canary / 熔断 / 成本观测与 chat 内部回调 client

4. `frontend/`
   - React + TypeScript + Tauri monorepo
   - Web/Desktop 应用壳与共享页面、domain、SDK、UI、tokens、config

5. `scripts/` 与 `skills/`
   - 仓库级脚本与 Codex lifecycle skill
   - harness、quality、release、PRD guard、test guard、plan sync 等入口

6. `docs/`
   - PRD、harness、架构、开发计划、阶段证据、讲解与学习材料

7. `e2e/`、`protos/`、`fixtures/`、`swiftide-pgvector/`、`superset/`
   - 端到端测试、协议/schema、配置 fixture、RAG 辅助库、本地 BI 配置

---

## 3. 从需求反查代码

### 3.1 鉴权 / 登录 / Session / 手机绑定

优先看：

1. [auth.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/auth.rs)
2. [user.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/user.rs)
3. [lib.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/lib.rs)
4. [auth-sdk index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/auth-sdk/src/index.ts)
5. [LoginPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/LoginPage.tsx)
6. [PhoneBindPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/PhoneBindPage.tsx)

### 3.2 Debate Lobby / Room / 消息 / WS

优先看：

1. [debate.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate.rs)
2. [debate_room.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_room.rs)
3. [notify ws.rs](/Users/panyihang/Documents/EchoIsle/chat/notify_server/src/ws.rs)
4. [debate-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/debate-domain/src/index.ts)
5. [realtime-sdk index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/realtime-sdk/src/index.ts)
6. [DebateRoomPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/DebateRoomPage.tsx)

### 3.2.1 虚拟裁判 NPC（公开房间娱乐角色）

虚拟裁判 NPC 是房间内公开可见的娱乐导向角色，不是赛后官方 AI 裁判团，也不替代正式裁决报告。当前 MVP 已完成 chat 侧 action spine、notify replay 合同、Debate Room 前端展示壳、独立 `npc_service/`、LLM executor router、rule fallback、本地 guard 与 full smoke；下一阶段已完成 `npc_service` Kafka/event-bus consumer 切换、观战实时可见、Ops 控制面、公开呼叫、近期行为、私有反馈、LLM canary、成本 / 延迟指标和熔断，webhook 默认仅作为 local-dev 入口。

优先看：

1. [debate_npc.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_npc.rs)
2. [debate/npc.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/debate/npc.rs)
3. [event_bus.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/event_bus.rs)
4. [notify notif.rs](/Users/panyihang/Documents/EchoIsle/chat/notify_server/src/notif.rs)
5. [notify ws.rs](/Users/panyihang/Documents/EchoIsle/chat/notify_server/src/ws.rs)
6. [realtime-sdk index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/realtime-sdk/src/index.ts)
7. [debate-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/debate-domain/src/index.ts)
8. [npc_service main.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/main.py)
9. [npc_service app_factory.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/app_factory.py)
10. [npc_service executors.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/executors.py)
11. [npc_service llm_runtime.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/llm_runtime.py)
12. [npc_service guard.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/guard.py)
13. [npc_service event_processor.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/event_processor.py)
14. [npc_service event_consumer.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/event_consumer.py)
15. [npc_service chat_client.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/chat_client.py)
16. [DebateNpcPanel.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/components/DebateNpcPanel.tsx)
17. [DebateNpcModel.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/components/DebateNpcModel.ts)
18. [NPC action migration](/Users/panyihang/Documents/EchoIsle/chat/migrations/20260503090000_debate_npc_action_spine.sql)
19. [NPC ops control migration](/Users/panyihang/Documents/EchoIsle/chat/migrations/20260504100000_debate_npc_ops_control_plane.sql)
20. [NPC public interaction migration](/Users/panyihang/Documents/EchoIsle/chat/migrations/20260504110000_debate_npc_public_call_history_feedback.sql)
21. [OpsConsolePage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/OpsConsolePage.tsx)
22. [ops-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/ops-domain/src/index.ts)
23. [虚拟裁判NPC_开发计划.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/虚拟裁判NPC_开发计划.md)

### 3.3 AI 裁判 / 报告 / 申诉 / 平局投票

当前有效主线是官方 `Judge App` / `Official Verdict Plane`。查 AI 裁判、报告、公验、challenge、复核或平局投票时，优先看下面这些入口。

Rust 官方主线优先看：

1. [debate_judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_judge.rs)
2. [ai_internal.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/ai_internal.rs)
3. [judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge.rs)
4. [judge_dispatch.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge_dispatch.rs)
5. [runtime_workers.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/application/runtime_workers.rs)

Python 官方主线优先看：

1. [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py)
2. [judge_command_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_command_routes.py)
3. [judge_dispatch_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_dispatch_runtime.py)
4. [judge_mainline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_mainline.py)
5. [callback_client.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/callback_client.py)

AI advisory / NPC Coach / Room QA 当前是暂停历史资产：

1. 不作为当前开发入口。
2. 不接真实 LLM executor、ready-state、成本/延迟 guard 或 Ops evidence。
3. 不删除历史实现；恢复前必须先冻结独立 PRD 和模块设计。

如只需理解历史实现或排查暂停边界，再看：

1. [debate_judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_judge.rs)
2. [request_report_query.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/request_report_query.rs)
3. [assistant_advisory_proxy.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/assistant_advisory_proxy.rs)
4. [debate-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/debate-domain/src/index.ts)
5. [DebateAssistantPanel.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/components/DebateAssistantPanel.tsx)
6. [route_group_assistant.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_assistant.py)
7. [assistant_agent_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_agent_routes.py)
8. [assistant_advisory_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_advisory_contract.py)
9. [assistant_advisory_prompt.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_advisory_prompt.py)
10. [assistant_advisory_output.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_advisory_output.py)
11. [bootstrap_ops_panel_replay_payload_helpers.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/bootstrap_ops_panel_replay_payload_helpers.py)
12. [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py)

### 3.4 AI Ops / Registry / Trust / Fairness / Review / Replay

Rust Ops 优先看：

1. [debate_ops.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_ops.rs)
2. [debate_ops/calibration_decision.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_ops/calibration_decision.rs)
3. [judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge.rs)
4. [runtime_readiness_ops_projection.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/runtime_readiness_ops_projection.rs)
5. [calibration_decision_ops_proxy.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/calibration_decision_ops_proxy.rs)
6. [rbac.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/rbac.rs)
7. [ops_observability.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/ops_observability.rs)
8. [kafka_dlq.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/kafka_dlq.rs)
9. [ops-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/ops-domain/src/index.ts)
10. [ops-domain runtimeReadiness.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/ops-domain/src/runtimeReadiness.ts)
11. [OpsCalibrationDecisionActions.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/components/OpsCalibrationDecisionActions.tsx)
12. [OpsCalibrationDecisionActionsModel.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/components/OpsCalibrationDecisionActionsModel.ts)
13. [OpsConsolePage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/OpsConsolePage.tsx)

Python AI Ops 优先看：

1. [route_group_registry.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_registry.py)
2. [route_group_trust.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_trust.py)
3. [route_group_fairness.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_fairness.py)
4. [route_group_review.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_review.py)
5. [route_group_replay.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_replay.py)
6. [route_group_ops_read_model_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_ops_read_model_pack.py)
7. [route_group_panel_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_panel_runtime.py)
8. [panel_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/panel_runtime_routes.py)
9. [panel_runtime_profile_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/panel_runtime_profile_contract.py)
10. [registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py)
11. [release_readiness_projection.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/release_readiness_projection.py)
12. [runtime_readiness_public_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/runtime_readiness_public_contract.py)
13. [runtime_readiness_public_projection.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/runtime_readiness_public_projection.py)
14. [fairness_calibration_decision_log.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_calibration_decision_log.py)
15. [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py)
16. [artifact_store_healthcheck.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/scripts/artifact_store_healthcheck.py)

AI Judge real-env / runtime evidence 优先看：

1. [ai_judge_runtime_ops_pack.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_runtime_ops_pack.sh)
2. [ai_judge_real_env_window_closure.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_real_env_window_closure.sh)
3. [ai_judge_real_env_evidence_closure.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_real_env_evidence_closure.sh)
4. [ai_judge_stage_closure_evidence.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_stage_closure_evidence.sh)
5. [ai_judge_runtime_ops_pack.env](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_runtime_ops_pack.env)
6. [ai_judge_real_env_readiness_inputs_checklist.md](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_real_env_readiness_inputs_checklist.md)
7. [ai_judge_artifact_store_healthcheck.json](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_artifact_store_healthcheck.json)

注意：当前没有真实环境时，`local_reference_ready` / `env_blocked` 只能证明本地参考与阻塞门禁有效，不等于 real-env `pass`。

### 3.5 钱包 / IAP / 账本

优先看：

1. [payment.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/payment.rs)
2. [payment model.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/payment.rs)
3. [wallet-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/wallet-domain/src/index.ts)
4. [WalletPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/WalletPage.tsx)
5. [Tauri commands/mod.rs](/Users/panyihang/Documents/EchoIsle/frontend/apps/desktop/src-tauri/src/commands/mod.rs)

### 3.6 Analytics / 通知 / 文件 ticket

优先看：

1. [analytics_server lib.rs](/Users/panyihang/Documents/EchoIsle/chat/analytics_server/src/lib.rs)
2. [analytics_proxy.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/analytics_proxy.rs)
3. [notify_server lib.rs](/Users/panyihang/Documents/EchoIsle/chat/notify_server/src/lib.rs)
4. [notify sse.rs](/Users/panyihang/Documents/EchoIsle/chat/notify_server/src/sse.rs)
5. [ticket.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/ticket.rs)
6. [messages.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/messages.rs)

### 3.7 AI RAG / 检索 / Bot

优先看：

1. [rag_retriever.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/rag_retriever.py)
2. [runtime_rag.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/runtime_rag.py)
3. [lexical_retriever.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/lexical_retriever.py)
4. [reranker_engine.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/reranker_engine.py)
5. [bot_server notif.rs](/Users/panyihang/Documents/EchoIsle/chat/bot_server/src/notif.rs)
6. [bot_server indexer.rs](/Users/panyihang/Documents/EchoIsle/chat/bot_server/src/indexer.rs)

### 3.8 Codex / Harness / 质量门禁

优先看：

1. [AGENTS.md](/Users/panyihang/Documents/EchoIsle/AGENTS.md)
2. [task-flows/README.md](/Users/panyihang/Documents/EchoIsle/docs/harness/task-flows/README.md)
3. [product-goals.md](/Users/panyihang/Documents/EchoIsle/docs/harness/product-goals.md)
4. [quality-gates.md](/Users/panyihang/Documents/EchoIsle/docs/harness/quality-gates.md)
5. [runtime-verify.md](/Users/panyihang/Documents/EchoIsle/docs/harness/runtime-verify.md)
6. [scripts/harness](/Users/panyihang/Documents/EchoIsle/scripts/harness)
7. [scripts/quality](/Users/panyihang/Documents/EchoIsle/scripts/quality)

---

## 4. 后端代码地图

### 4.1 `chat/` Rust workspace

关键入口：

1. [chat/Cargo.toml](/Users/panyihang/Documents/EchoIsle/chat/Cargo.toml)
2. [chat_server/src/lib.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/lib.rs)
3. [chat_server/src/openapi.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/openapi.rs)

主要子项目：

1. `chat/chat_server`
   - 主 API 服务，业务 handler、model、middleware、Redis、Kafka/outbox、OpenAPI、后台 worker

2. `chat/chat_core`
   - 共享基础层，JWT、middleware、配置加载、公共错误、基础 DTO

3. `chat/notify_server`
   - SSE、WS、debate room WS、replay、syncRequired、access ticket 校验

4. `chat/analytics_server`
   - ClickHouse event ingest 与分析读 API

5. `chat/ai_sdk`
   - Rust AI adapter SDK，当前包含 OpenAI/Ollama adapter

6. `chat/bot_server`
   - Bot 消息监听与代码索引/RAG 辅助

7. `chat/chat_test`、`chat/simulator`、`chat/migrations`、`chat/scripts`
   - 测试、模拟器、数据库迁移、后端专项脚本

### 4.2 `chat_server` 下钻规则

先看 [lib.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/lib.rs)，再按目录跳：

1. `handlers/`
   - HTTP 入口

2. `models/`
   - DB 访问、DTO、分页、状态字段

3. `middlewares/`
   - chat、phone-bound、ticket、internal AI key 等访问控制

4. `application/`
   - 后台 worker 与请求保护

5. `event_bus.rs`、`redis_store.rs`、`openapi.rs`
   - 事件/outbox/Kafka、Redis/缓存/限流、公开 API 契约

---

## 5. AI 服务代码地图

### 5.1 `ai_judge_service/`

关键入口：

1. [main.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/main.py)
2. [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py)
3. [settings.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/settings.py)
4. [wiring.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/wiring.py)

按目录看：

1. `app/applications/`
   - FastAPI route group 与应用服务，是当前 AI 服务第一优先入口

2. `app/core/`
   - 裁判核心与 workflow 编排

3. `app/domain/`
   - agents、artifacts、facts、gateways、judge、trust、workflow 的模型与 ports

4. `app/infra/`
   - DB、repository、artifact store、gateway 实现

5. `app/*.py`
   - 根层保留运行时策略、RAG、OpenAI client、callback、trace store、专项 gate

6. `scripts/`
   - AI 服务本地 gate、证据导出与运维辅助 CLI；生产对象存储 readiness 先看 `artifact_store_healthcheck.py`

### 5.2 `npc_service/`

关键入口：

1. [main.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/main.py)
2. [app_factory.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/app_factory.py)
3. [settings.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/settings.py)
4. [models.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/models.py)

按职责看：

1. [executors.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/executors.py)
   - `llm_executor_v1` 主路径、`rule_executor_v1` fallback 与 decision run 元数据

2. [openai_provider.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/openai_provider.py)
   - OpenAI-compatible chat completions JSON adapter

3. [llm_runtime.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/llm_runtime.py)
   - LLM canary、成本 / token / 延迟观测、连续失败熔断和 runtime metrics snapshot

4. [guard.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/guard.py)
   - 禁止正式裁决字段、限制公开文本长度、校验 action 语义

5. [chat_client.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/chat_client.py)
   - 从 `chat` 拉取公开 context，并提交候选动作到 `chat` 内部 action sink；`chat` 仍是房间事实源

6. [event_processor.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/event_processor.py)
   - 处理 `DebateMessageCreated` trigger，串联 context fetch、executor router 与 candidate callback

7. [event_consumer.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/event_consumer.py)
   - 解码 Kafka/event-bus envelope，驱动 `NpcEventProcessor`，维护 commit/retry/DLQ 语义；webhook 默认仅作为 local-dev 入口

8. [tests](/Users/panyihang/Documents/EchoIsle/npc_service/tests)
   - 当前覆盖 executor router、LLM canary / fallback / 熔断 / 成本、guard、OpenAI adapter、chat client、event processor、event consumer 与 FastAPI 路由

### 5.3 最常用 AI 服务文件

1. 裁判主链：
   - [judge_command_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_command_routes.py)
   - [judge_dispatch_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_dispatch_runtime.py)
   - [judge_mainline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_mainline.py)
   - [judge_workflow_roles.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_workflow_roles.py)

2. 回放、治理与运维读路径：
   - [route_group_replay.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_replay.py)
   - [route_group_registry.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_registry.py)
   - [route_group_fairness.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_fairness.py)
   - [fairness_calibration_decision_log.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_calibration_decision_log.py)
   - [route_group_panel_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_panel_runtime.py)
   - [panel_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/panel_runtime_routes.py)
   - [panel_runtime_profile_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/panel_runtime_profile_contract.py)
   - [registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py)
   - [release_readiness_projection.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/release_readiness_projection.py)
   - [route_group_ops_read_model_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_ops_read_model_pack.py)
   - [runtime_readiness_public_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/runtime_readiness_public_contract.py)
   - [runtime_readiness_public_projection.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/runtime_readiness_public_projection.py)
   - [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py)
   - [artifact_store_healthcheck.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/scripts/artifact_store_healthcheck.py)
   - [facts repository.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/facts/repository.py)

3. 暂停历史资产（NPC Coach / Room QA / advisory）：
   - [route_group_assistant.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_assistant.py)
   - [assistant_agent_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_agent_routes.py)
   - [assistant_advisory_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_advisory_contract.py)
   - [assistant_advisory_prompt.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_advisory_prompt.py)
   - [assistant_advisory_output.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_advisory_output.py)
   - [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py)

   这些文件只用于理解历史实现或暂停边界；当前不要从这里继续新增 NPC Coach / Room QA 开发任务。

4. RAG 与模型：
   - [openai_judge_client.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/openai_judge_client.py)
   - [rag_retriever.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/rag_retriever.py)
   - [runtime_rag.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/runtime_rag.py)

---

## 6. 前端代码地图

### 6.1 `frontend/` monorepo

关键入口：

1. [frontend/package.json](/Users/panyihang/Documents/EchoIsle/frontend/package.json)
2. [frontend/playwright.config.ts](/Users/panyihang/Documents/EchoIsle/frontend/playwright.config.ts)
3. [AppRoot.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/AppRoot.tsx)

主要分层：

1. `frontend/apps/web`
   - Web 应用壳

2. `frontend/apps/desktop`
   - Desktop 应用壳

3. `frontend/apps/desktop/src-tauri`
   - Tauri Rust 壳、窗口、菜单、日志、配置、IAP native bridge

4. `frontend/packages/app-shell`
   - 双端共享路由、布局、页面

5. `frontend/packages/*`
   - 共享业务域、SDK、UI、tokens、config、testing、proto scaffold

### 6.2 前端最常用入口

1. 页面层：
   - [LoginPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/LoginPage.tsx)
   - [DebateLobbyPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/DebateLobbyPage.tsx)
   - [DebateRoomPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/DebateRoomPage.tsx)
   - [WalletPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/WalletPage.tsx)
   - [OpsConsolePage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/OpsConsolePage.tsx)

2. SDK / Domain：
   - [api-client index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/api-client/src/index.ts)
   - [auth-sdk index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/auth-sdk/src/index.ts)
   - [debate-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/debate-domain/src/index.ts)
   - [wallet-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/wallet-domain/src/index.ts)
   - [ops-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/ops-domain/src/index.ts)
   - [ops-domain runtimeReadiness.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/ops-domain/src/runtimeReadiness.ts)
   - [realtime-sdk index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/realtime-sdk/src/index.ts)

---

## 7. 辅助与非优先目录

这些目录常有用，但通常不是实现任务的第一入口：

1. `e2e/`
   - 独立 Playwright 端到端测试

2. `frontend/tests/`
   - 当前前端 smoke / e2e 测试入口之一

3. `protos/`
   - protobuf 与 ClickHouse schema

4. `fixtures/`
   - 本地配置 fixture 与少量测试素材

5. `swiftide-pgvector/`
   - Bot/RAG 相关 pgvector helper library

6. `superset/`
   - 本地 BI / 分析配置

7. `artifacts/`、`frontend/test-results/`、`e2e/test-results/`、`e2e/playwright-report/`
   - 执行证据、测试输出或生成产物

8. `scripts/harness/`
   - AI Judge runtime ops pack、stage closure evidence、real-env closure 等阶段证据脚本

9. `target/`、`node_modules/`、`dist/`、`.turbo/`、`__pycache__/`
   - 构建产物、依赖或缓存

10. `docs/explanation/`、`docs/interview/`、`docs/learning/`、`docs/resume/`
   - 复盘和沉淀材料，不适合当实现入口

---

## 8. Agent 使用建议

当 agent 进入新任务时，推荐按这个顺序压缩上下文：

1. 先看 [AGENTS.md](/Users/panyihang/Documents/EchoIsle/AGENTS.md)
2. 按任务类型读对应 `docs/harness/task-flows/*.md`
3. 再看本文件判断第一跳入口
4. 只打开相关入口文件，沿代码里的 router、exports、mod、tests 继续下钻
5. 涉及 API、DTO、错误码、状态字段或 WS payload 时，再同步检查后端 `openapi.rs` 与前端 domain / SDK

一句话原则：

先看地图，再进代码；这份文档只负责帮你少开文件、少花 token。

# EchoIsle Architecture Map

更新时间：2026-04-28
状态：当前主线轻量代码地图

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

当前 EchoIsle 先按 6 个区域理解：

1. `chat/`
   - Rust 后端 workspace
   - 主 API、通知服务、分析服务、AI SDK、Bot/RAG 辅助服务、模拟器、迁移与后端专项脚本

2. `ai_judge_service/`
   - Python FastAPI AI 裁判服务
   - 裁判 dispatch、回调、RAG、trace、registry、trust、fairness、review、replay 与内部 ops 读路径

3. `frontend/`
   - React + TypeScript + Tauri monorepo
   - Web/Desktop 应用壳与共享页面、domain、SDK、UI、tokens、config

4. `scripts/` 与 `skills/`
   - 仓库级脚本与 Codex lifecycle skill
   - harness、quality、release、PRD guard、test guard、plan sync 等入口

5. `docs/`
   - PRD、harness、架构、开发计划、阶段证据、讲解与学习材料

6. `e2e/`、`protos/`、`fixtures/`、`swiftide-pgvector/`、`superset/`
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

### 3.3 AI 裁判 / 报告 / 申诉 / 平局投票

Rust 侧优先看：

1. [debate_judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_judge.rs)
2. [ai_internal.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/ai_internal.rs)
3. [judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge.rs)
4. [judge_dispatch.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge_dispatch.rs)
5. [runtime_workers.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/application/runtime_workers.rs)

Python 侧优先看：

1. [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py)
2. [judge_command_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_command_routes.py)
3. [judge_dispatch_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_dispatch_runtime.py)
4. [judge_mainline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_mainline.py)
5. [callback_client.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/callback_client.py)

### 3.4 AI Ops / Registry / Trust / Fairness / Review / Replay

Rust Ops 优先看：

1. [debate_ops.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_ops.rs)
2. [judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge.rs)
3. [rbac.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/rbac.rs)
4. [ops_observability.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/ops_observability.rs)
5. [kafka_dlq.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/kafka_dlq.rs)
6. [ops-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/ops-domain/src/index.ts)
7. [OpsConsolePage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/OpsConsolePage.tsx)

Python AI Ops 优先看：

1. [route_group_registry.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_registry.py)
2. [route_group_trust.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_trust.py)
3. [route_group_fairness.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_fairness.py)
4. [route_group_review.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_review.py)
5. [route_group_replay.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_replay.py)
6. [route_group_ops_read_model_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_ops_read_model_pack.py)
7. [runtime_readiness_public_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/runtime_readiness_public_contract.py)

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

### 5.2 最常用 AI 服务文件

1. 裁判主链：
   - [judge_command_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_command_routes.py)
   - [judge_mainline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_mainline.py)

2. 回放、治理与运维读路径：
   - [route_group_replay.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_replay.py)
   - [route_group_registry.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_registry.py)
   - [route_group_ops_read_model_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_ops_read_model_pack.py)
   - [runtime_readiness_public_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/runtime_readiness_public_contract.py)

3. RAG 与模型：
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

8. `target/`、`node_modules/`、`dist/`、`.turbo/`、`__pycache__/`
   - 构建产物、依赖或缓存

9. `docs/explanation/`、`docs/interview/`、`docs/learning/`、`docs/resume/`
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

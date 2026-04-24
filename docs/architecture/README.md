# EchoIsle Architecture Map

更新时间：2026-04-06
状态：当前主线代码地图

---

## 1. 目的

这份文档不是完整架构设计书，而是给人和 agent 使用的轻量代码地图。

它主要回答四个问题：

1. 仓库当前主线有哪些子系统
2. 每个子系统大致负责什么
3. 遇到某类需求时，第一眼应该去哪里看代码
4. 哪些目录是运行主线，哪些目录更偏测试、脚本、文档或辅助资产

如果你要看规则，优先读 `AGENTS.md` 与 `docs/harness/`。
如果你要找代码，优先从本文件开始。

---

## 2. 仓库主线总览

当前 EchoIsle 可以先按 5 个区域理解：

1. `chat/`
   - Rust 后端工作区
   - 承载主 API、通知、分析、测试与共享基础设施

2. `ai_judge_service/`
   - Python AI 裁判服务
   - 承载裁判推理、RAG、回调、运行时策略与专项验证脚本

3. `frontend/`
   - React + TypeScript 前端 monorepo
   - 承载 Web、Desktop 与共享包

4. `scripts/`
   - 仓库级脚本
   - 其中 `scripts/harness/` 是当前 Codex/harness 入口层

5. `docs/`
   - PRD、架构、harness、开发计划、讲解、学习与验证证据

---

## 3. 从需求反查代码

### 3.1 鉴权 / 登录 / Session / 手机绑定

优先看：

1. [auth.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/auth.rs)
2. [lib.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/lib.rs)
3. [auth-sdk index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/auth-sdk/src/index.ts)
4. [LoginPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/LoginPage.tsx)
5. [PhoneBindPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/PhoneBindPage.tsx)

### 3.2 Debate Lobby / Room / 消息 / WS / 裁判流程

优先看：

1. [debate.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate.rs)
2. [debate_room.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_room.rs)
3. [debate_judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_judge.rs)
4. [DebateLobbyPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/DebateLobbyPage.tsx)
5. [DebateRoomPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/DebateRoomPage.tsx)
6. [realtime-sdk index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/realtime-sdk/src/index.ts)

### 3.3 钱包 / IAP / 账本

优先看：

1. [payment.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/payment.rs)
2. [WalletPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/WalletPage.tsx)
3. [wallet-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/wallet-domain/src/index.ts)

### 3.4 Ops / 观测 / 运维读路径

优先看：

1. [debate_ops.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_ops.rs)
2. [analytics_proxy.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/analytics_proxy.rs)
3. [OpsConsolePage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/OpsConsolePage.tsx)
4. [ops-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/ops-domain/src/index.ts)

### 3.5 AI 裁判 / RAG / 推理链路

优先看：

1. [main.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/main.py)
2. [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py)
3. [phase_pipeline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/phase_pipeline.py)
4. [openai_judge_client.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/openai_judge_client.py)
5. [rag_retriever.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/rag_retriever.py)
6. [runtime_policy.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/runtime_policy.py)

### 3.6 Codex / Harness / 开发流程编排

优先看：

1. [AGENTS.md](/Users/panyihang/Documents/EchoIsle/AGENTS.md)
2. [task-flows/README.md](/Users/panyihang/Documents/EchoIsle/docs/harness/task-flows/README.md)
3. [product-goals.md](/Users/panyihang/Documents/EchoIsle/docs/harness/product-goals.md)
4. [doc-governance.md](/Users/panyihang/Documents/EchoIsle/docs/harness/doc-governance.md)
5. [quality-gates.md](/Users/panyihang/Documents/EchoIsle/docs/harness/quality-gates.md)
6. [runtime-verify.md](/Users/panyihang/Documents/EchoIsle/docs/harness/runtime-verify.md)
7. [usage-tutorial.md](/Users/panyihang/Documents/EchoIsle/docs/harness/usage-tutorial.md)
8. [journey_verify.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/journey_verify.sh)

---

## 4. 后端代码地图

### 4.1 `chat/` Rust workspace

关键入口：

1. [chat/Cargo.toml](/Users/panyihang/Documents/EchoIsle/chat/Cargo.toml)
2. [chat_server/Cargo.toml](/Users/panyihang/Documents/EchoIsle/chat/chat_server/Cargo.toml)
3. [chat_server/src/lib.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/lib.rs)

主要子项目：

1. `chat/chat_server`
   - 主 API 服务
   - 大部分业务 handler、middleware、model、event bus 都在这里

2. `chat/chat_core`
   - 共享基础层
   - JWT、中间件、配置加载、公共错误与工具函数

3. `chat/notify_server`
   - 通知服务

4. `chat/analytics_server`
   - 分析服务

5. `chat/chat_test`
   - Rust 侧测试项目与辅助测试资源

6. `chat/migrations`
   - 数据库迁移

7. `chat/scripts`
   - 后端专项脚本

### 4.2 `chat_server` 内部优先理解方式

先看 [lib.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/lib.rs)，因为它同时告诉你：

1. 模块分层
2. router 组装方式
3. handler 对外暴露的 API 面
4. middleware 和 runtime worker 的挂接点

然后再按问题跳：

1. `handlers/`
   - HTTP 入口
2. `middlewares/`
   - 鉴权、ticket、chat/phone-bound 等访问控制
3. `models/`
   - 域模型与 DB 交互
4. `application/`
   - 编排与后台 worker
5. `event_bus/`
   - 事件总线、outbox、Kafka 相关

---

## 5. AI 服务代码地图

### 5.1 `ai_judge_service/`

关键入口：

1. [main.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/main.py)
2. [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py)
3. [wiring.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/wiring.py)
4. [settings.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/settings.py)

按职责看：

1. 推理与阶段编排：
   - [phase_pipeline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/phase_pipeline.py)
   - [style_mode.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/style_mode.py)
   - [token_budget.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/token_budget.py)

2. 模型调用与回调：
   - [openai_judge_client.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/openai_judge_client.py)
   - [callback_client.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/callback_client.py)

3. RAG 与检索：
   - [rag_retriever.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/rag_retriever.py)
   - [rag_profiles.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/rag_profiles.py)
   - [runtime_rag.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/runtime_rag.py)
   - [lexical_retriever.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/lexical_retriever.py)
   - [reranker_engine.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/reranker_engine.py)
   - [milvus_indexer.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/milvus_indexer.py)

4. 运行时策略与专项门禁：
   - [runtime_policy.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/runtime_policy.py)
   - [b3_consistency_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/b3_consistency_gate.py)
   - [m7_acceptance_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/m7_acceptance_gate.py)

---

## 6. 前端代码地图

### 6.1 `frontend/` monorepo

关键入口：

1. [frontend/package.json](/Users/panyihang/Documents/EchoIsle/frontend/package.json)
2. [frontend/playwright.config.ts](/Users/panyihang/Documents/EchoIsle/frontend/playwright.config.ts)

主要分层：

1. `frontend/apps/web`
   - Web 应用壳

2. `frontend/apps/desktop`
   - Desktop 应用壳

3. `frontend/apps/desktop/src-tauri`
   - Desktop 的 Rust/Tauri 壳

4. `frontend/packages/*`
   - 共享业务域、SDK、UI、tokens、config、testing

### 6.2 前端最常用入口

1. 应用路由与页面入口：
   - [AppRoot.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/AppRoot.tsx)

2. 页面层：
   - [HomePage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/HomePage.tsx)
   - [DebateLobbyPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/DebateLobbyPage.tsx)
   - [DebateRoomPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/DebateRoomPage.tsx)
   - [WalletPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/WalletPage.tsx)
   - [OpsConsolePage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/OpsConsolePage.tsx)

3. API 与认证 SDK：
   - [api-client index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/api-client/src/index.ts)
   - [auth-sdk index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/auth-sdk/src/index.ts)

4. 共享域包：
   - [debate-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/debate-domain/src/index.ts)
   - [wallet-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/wallet-domain/src/index.ts)
   - [ops-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/ops-domain/src/index.ts)
   - [realtime-sdk index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/realtime-sdk/src/index.ts)

---

## 7. 哪些目录不是第一优先级

这些目录不是没用，而是通常不应作为第一眼入口：

1. `docs/explanation/`
   - 适合复盘，不适合当代码入口

2. `docs/interview/`
   - 适合沉淀，不适合当实现入口

3. `artifacts/`
   - 适合看执行证据，不适合理解系统结构

4. `e2e/`
   - 是独立专项测试区，不是主业务实现入口

5. `swiftide-pgvector/`
   - 当前不是产品主线

---

## 8. Agent 使用建议

当 agent 进入新任务时，推荐按这个顺序压缩上下文：

1. 先看 [AGENTS.md](/Users/panyihang/Documents/EchoIsle/AGENTS.md)
2. 再看本文件判断该去哪一段代码
3. 然后只打开相关入口文件，不要一开始就扫整个仓库
4. 只有遇到跨服务边界或复杂链路时，再补读 PRD、harness 或专项架构文档

一句话原则：

先看地图，再进代码。

# 当前开发计划

关联 slot：`default`  
更新时间：2026-04-13  
当前主线：`AI_judge_service 平台化重构（Judge 优先，面向未来 NPC / Room QA 扩展）`  
当前状态：进行中

---

## 1. 计划定位

本计划只记录当前正在推进的一条主开发线，并维护总进度。

规则：

1. 当前产品尚未上线，默认一步到位，不保留兼容层、灰度路径、双写或旧新并行主链。
2. 每次只推进一个明确阶段；当前阶段完成后，再生成下一阶段计划。
3. 需要真实线上流量、真实压测样本、真实长期观测数据才能拍板的事项，统一延后，不阻塞当前架构与代码主线重建。

权威参考：

1. [在线辩论AI裁判平台完整PRD.md](/Users/panyihang/Documents/EchoIsle/docs/PRD/在线辩论AI裁判平台完整PRD.md)
2. [AI裁判完整PRD.md](/Users/panyihang/Documents/EchoIsle/docs/PRD/AI裁判完整PRD.md)
3. [AI_Judge_Service-架构与技术栈决策方案-2026-04-13.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/AI_Judge_Service-架构与技术栈决策方案-2026-04-13.md)

---

## 2. 已拍板前提

1. `ai_judge_service` 按“裁判优先的 Debate Agent Platform”方向重建，不再按单功能 prompt 服务继续堆叠。
2. 架构采用“模块化单体 + 两个运行单元（`agent-api / agent-worker`）”路线，不先拆成多个独立微服务。
3. 技术栈继续使用 `Python 3.11 + FastAPI + Pydantic v2`。
4. `PostgreSQL` 作为主事实源，`Redis` 只做加速与协调层。
5. 第一阶段工作流内核直接采用 `Postgres-backed Orchestrator`，不引入 `Celery / Dramatiq / RQ`，也不保留旧的内存/Redis workflow 兼容主链。
6. 第一阶段知识检索继续保留 `Milvus + BM25 + rerank` 主线，但统一收口到 `Knowledge Gateway` 后面，不做 `pgvector` 迁移。
7. 客户端永远通过 `chat_server` 使用 AI 能力，不直接连接 AI 服务。

---

## 3. 总进度

总阶段数：`6`  
已完成：`1`  
进行中：`5`  
未开始：`0`

### 已完成/未完成矩阵

| 阶段 | 目标 | 状态 | 说明 |
| --- | --- | --- | --- |
| `P0 决策与产品对齐` | 完成 PRD、产品摘要、Agent 设计、架构决策收口 | 已完成 | 文档主合同与架构路线已拍板 |
| `P1 平台骨架与持久化事实源落地` | 建立模块化单体骨架、PostgreSQL 主事实源与 workflow 底座 | 进行中 | 当前执行阶段 |
| `P2 Judge 主链迁移与领域收敛` | 将 phase/final 主链迁入新分层与领域对象 | 进行中 | 已启动 final 主链迁移，phase 主链迁移待继续 |
| `P3 复核 / 回放 / 审计 / Ops 收口` | 收敛 review/replay/audit/ops 主链 | 进行中 | replay/audit 应用层收敛与 runtime verify 闭环已启动 |
| `P4 NPC / Room QA 共享平台预留` | 预留 NPC 与问答 Agent 的共享底座和空壳应用 | 进行中 | Agent Runtime Shell 预留底座已落地 |
| `P5 真实环境校准与可验证扩展` | 基于真实数据完成压测、成本、公平 benchmark 与可信扩展校准 | 进行中 | 本地 prep 已完成，真实环境数据校准仍延后 |
| ai-judge-p1-platform-core | P1 | 进行中（phase 已完成） | 通过 module-turn-harness 统一当前模块级 hook 顺序；改动文件："docs/PRD/AI裁判完整PRD.md";"docs/PRD/在线辩论AI裁判平台完整PRD.md";"docs/dev_plan/AI_Judge_Service-企业级Agent服务设计方案-2026-04-13.md";"docs/dev_plan/AI_Judge_Service-公平性与架构优化方案-2026-04-13.md";"docs/dev_plan/AI_Judge_Service-架构与技术栈决策方案-2026-04-13.md";"docs/dev_plan/当前开发计划.md";artifacts/harness/20260413T094306Z-ai-judge-prd-rewrite.docs-lint.json;artifacts/harness/20260413T094306Z-ai-judge-prd-rewrite.docs-lint.md;artifacts/harness/20260413T094306Z-ai-judge-prd-rewrite.jsonl;artifacts/harness/20260413T094306Z-ai-judge-prd-rewrite.summary.json;artifacts/harness/20260413T094306Z-ai-judge-prd-rewrite.summary.md;artifacts/harness/20260413T094419Z-ai-judge-service-agent-redesign.docs-lint.json;artifacts/harness/20260413T094419Z-ai-judge-service-agent-redesign.docs-lint.md;artifacts/harness/20260413T094419Z-ai-judge-service-agent-redesign.jsonl;artifacts/harness/20260413T094419Z-ai-judge-service-agent-redesign.summary.json;artifacts/harness/20260413T094419Z-ai-judge-service-agent-redesign.summary.md;artifacts/harness/20260413T094621Z-ai-judge-service-agent-redesign.docs-lint.json;artifacts/harness/20260413T094621Z-ai-judge-service-agent-redesign.docs-lint.md;artifacts/harness/20260413T094621Z-ai-judge-service-agent-redesign.jsonl;artifacts/harness/20260413T094621Z-ai-judge-service-agent-redesign.summary.json;artifacts/harness/20260413T094621Z-ai-judge-service-agent-redesign.summary.md;artifacts/harness/20260413T094847Z-harness-product-goals.docs-lint.json;artifacts/harness/20260413T094847Z-harness-product-goals.docs-lint.md;artifacts/harness/20260413T094847Z-harness-product-goals.jsonl;artifacts/harness/20260413T094847Z-harness-product-goals.summary.json;artifacts/harness/20260413T094847Z-harness-product-goals.summary.md;artifacts/harness/20260413T095750Z-ai-judge-architecture-decisions.docs-lint.json;artifacts/harness/20260413T095750Z-ai-judge-architecture-decisions.docs-lint.md;artifacts/harness/20260413T095750Z-ai-judge-architecture-decisions.jsonl;artifacts/harness/20260413T095750Z-ai-judge-architecture-decisions.summary.json;artifacts/harness/20260413T095750Z-ai-judge-architecture-decisions.summary.md;artifacts/harness/20260413T100358Z-ai-judge-architecture-decisions.docs-lint.json;artifacts/harness/20260413T100358Z-ai-judge-architecture-decisions.docs-lint.md;artifacts/harness/20260413T100358Z-ai-judge-architecture-decisions.jsonl;artifacts/harness/20260413T100358Z-ai-judge-architecture-decisions.summary.json;artifacts/harness/20260413T100358Z-ai-judge-architecture-decisions.summary.md;artifacts/harness/20260413T101630Z-ai-judge-plan-bootstrap.docs-lint.json;artifacts/harness/20260413T101630Z-ai-judge-plan-bootstrap.docs-lint.md;artifacts/harness/20260413T101630Z-ai-judge-plan-bootstrap.jsonl;artifacts/harness/20260413T101630Z-ai-judge-plan-bootstrap.summary.json;artifacts/harness/20260413T101630Z-ai-judge-plan-bootstrap.summary.md;artifacts/harness/20260413T102049Z-ai-judge-plan-bootstrap.docs-lint.json;artifacts/harness/20260413T102049Z-ai-judge-plan-bootstrap.docs-lint.md;artifacts/harness/20260413T102049Z-ai-judge-plan-bootstrap.jsonl;artifacts/harness/20260413T102049Z-ai-judge-plan-bootstrap.summary.json;artifacts/harness/20260413T102049Z-ai-judge-plan-bootstrap.summary.md;artifacts/harness/20260413T102331Z-ai-judge-p1-platform-core.jsonl;docs/harness/product-goals.md |
| ai-judge-p1-db-entity-expansion | P1 | 进行中（phase 已完成） | 通过 module-turn-harness 统一当前模块级 hook 顺序；改动文件："docs/PRD/AI裁判完整PRD.md";"docs/PRD/在线辩论AI裁判平台完整PRD.md";"docs/dev_plan/AI_Judge_Service-企业级Agent服务设计方案-2026-04-13.md";"docs/dev_plan/AI_Judge_Service-公平性与架构优化方案-2026-04-13.md";"docs/dev_plan/AI_Judge_Service-架构与技术栈决策方案-2026-04-13.md";"docs/dev_plan/当前开发计划.md";ai_judge_service/alembic.ini;ai_judge_service/alembic/env.py;ai_judge_service/alembic/script.py.mako;ai_judge_service/alembic/versions/20260413_0001_workflow_core.py;ai_judge_service/app/api/__init__.py;ai_judge_service/app/applications/__init__.py;ai_judge_service/app/applications/workflow_runtime.py;ai_judge_service/app/core/__init__.py;ai_judge_service/app/core/workflow/__init__.py;ai_judge_service/app/core/workflow/errors.py;ai_judge_service/app/core/workflow/orchestrator.py;ai_judge_service/app/domain/__init__.py;ai_judge_service/app/domain/workflow/__init__.py;ai_judge_service/app/domain/workflow/models.py;ai_judge_service/app/domain/workflow/ports.py;ai_judge_service/app/infra/__init__.py;ai_judge_service/app/infra/db/__init__.py;ai_judge_service/app/infra/db/base.py;ai_judge_service/app/infra/db/models.py;ai_judge_service/app/infra/db/runtime.py;ai_judge_service/app/infra/workflow/__init__.py;ai_judge_service/app/infra/workflow/postgres_store.py;ai_judge_service/app/m7_acceptance_gate.py;ai_judge_service/app/settings.py;ai_judge_service/pyproject.toml;ai_judge_service/requirements.txt;ai_judge_service/tests/test_app_factory.py;ai_judge_service/tests/test_runtime_rag.py;ai_judge_service/tests/test_settings.py;ai_judge_service/tests/test_workflow_orchestrator.py;ai_judge_service/uv.lock;artifacts/harness/20260413T094306Z-ai-judge-prd-rewrite.docs-lint.json;artifacts/harness/20260413T094306Z-ai-judge-prd-rewrite.docs-lint.md;artifacts/harness/20260413T094306Z-ai-judge-prd-rewrite.jsonl;artifacts/harness/20260413T094306Z-ai-judge-prd-rewrite.summary.json;artifacts/harness/20260413T094306Z-ai-judge-prd-rewrite.summary.md;artifacts/harness/20260413T094419Z-ai-judge-service-agent-redesign.docs-lint.json;artifacts/harness/20260413T094419Z-ai-judge-service-agent-redesign.docs-lint.md;artifacts/harness/20260413T094419Z-ai-judge-service-agent-redesign.jsonl;artifacts/harness/20260413T094419Z-ai-judge-service-agent-redesign.summary.json;artifacts/harness/20260413T094419Z-ai-judge-service-agent-redesign.summary.md;artifacts/harness/20260413T094621Z-ai-judge-service-agent-redesign.docs-lint.json;artifacts/harness/20260413T094621Z-ai-judge-service-agent-redesign.docs-lint.md;artifacts/harness/20260413T094621Z-ai-judge-service-agent-redesign.jsonl;artifacts/harness/20260413T094621Z-ai-judge-service-agent-redesign.summary.json;artifacts/harness/20260413T094621Z-ai-judge-service-agent-redesign.summary.md;artifacts/harness/20260413T094847Z-harness-product-goals.docs-lint.json;artifacts/harness/20260413T094847Z-harness-product-goals.docs-lint.md;artifacts/harness/20260413T094847Z-harness-product-goals.jsonl;artifacts/harness/20260413T094847Z-harness-product-goals.summary.json;artifacts/harness/20260413T094847Z-harness-product-goals.summary.md;artifacts/harness/20260413T095750Z-ai-judge-architecture-decisions.docs-lint.json;artifacts/harness/20260413T095750Z-ai-judge-architecture-decisions.docs-lint.md;artifacts/harness/20260413T095750Z-ai-judge-architecture-decisions.jsonl;artifacts/harness/20260413T095750Z-ai-judge-architecture-decisions.summary.json;artifacts/harness/20260413T095750Z-ai-judge-architecture-decisions.summary.md;artifacts/harness/20260413T100358Z-ai-judge-architecture-decisions.docs-lint.json;artifacts/harness/20260413T100358Z-ai-judge-architecture-decisions.docs-lint.md;artifacts/harness/20260413T100358Z-ai-judge-architecture-decisions.jsonl;artifacts/harness/20260413T100358Z-ai-judge-architecture-decisions.summary.json;artifacts/harness/20260413T100358Z-ai-judge-architecture-decisions.summary.md;artifacts/harness/20260413T101630Z-ai-judge-plan-bootstrap.docs-lint.json;artifacts/harness/20260413T101630Z-ai-judge-plan-bootstrap.docs-lint.md;artifacts/harness/20260413T101630Z-ai-judge-plan-bootstrap.jsonl;artifacts/harness/20260413T101630Z-ai-judge-plan-bootstrap.summary.json;artifacts/harness/20260413T101630Z-ai-judge-plan-bootstrap.summary.md;artifacts/harness/20260413T102049Z-ai-judge-plan-bootstrap.docs-lint.json;artifacts/harness/20260413T102049Z-ai-judge-plan-bootstrap.docs-lint.md;artifacts/harness/20260413T102049Z-ai-judge-plan-bootstrap.jsonl;artifacts/harness/20260413T102049Z-ai-judge-plan-bootstrap.summary.json;artifacts/harness/20260413T102049Z-ai-judge-plan-bootstrap.summary.md;artifacts/harness/20260413T102331Z-ai-judge-p1-platform-core.jsonl;artifacts/harness/20260413T102331Z-ai-judge-p1-platform-core.summary.json;artifacts/harness/20260413T102331Z-ai-judge-p1-platform-core.summary.md;artifacts/harness/20260413T105123Z-ai-judge-p1-db-entity-expansion.jsonl;docs/harness/product-goals.md |
| ai-judge-p1-runtime-migration | P1 | 进行中（phase 已完成） | 通过 module-turn-harness 统一当前模块级 hook 顺序；改动文件：artifacts/harness/20260413T110320Z-ai-judge-p1-runtime-migration.jsonl |
| ai-judge-p1-trace-fact-bridge | P1 | 进行中（phase 已完成） | 通过 module-turn-harness 统一当前模块级 hook 顺序；改动文件：artifacts/harness/20260413T111617Z-ai-judge-p1-trace-fact-bridge.jsonl；ai_judge_service/app/app_factory.py；ai_judge_service/app/domain/facts/ports.py；ai_judge_service/app/infra/facts/repository.py；ai_judge_service/tests/test_app_factory.py；ai_judge_service/tests/test_fact_repository.py |
| ai-judge-p1-runtime-failure-coverage | P1 | 进行中（phase 已完成） | 通过 module-turn-harness 统一当前模块级 hook 顺序；改动文件：artifacts/harness/20260413T113237Z-ai-judge-p1-runtime-failure-coverage.jsonl；ai_judge_service/app/app_factory.py；ai_judge_service/tests/test_app_factory.py |
| ai-judge-p1-gateway-bootstrap | P1 | 进行中（phase 已完成） | 通过 module-turn-harness 统一当前模块级 hook 顺序；落地 LLM/Knowledge Gateway 并接入 phase/replay 主链 |
| ai-judge-p2-judge-mainline-migration | P2 | 进行中（phase 已完成） | final 报告构建与契约校验已迁入 `applications/domain`；`app_factory` 收敛为编排层，API 行为保持不变 |
| ai-judge-p2-phase-mainline-migration | P2 | 进行中（phase 已完成） | phase入口已迁入applications/judge_mainline，并补应用层委托测试；API行为保持不变 |
| ai-judge-p3-replay-audit-ops-convergence | P3 | 进行中（phase 已完成） | replay/audit序列化和summary已迁入applications/replay_audit_ops，app_factory改为委托调用 |
| ai-judge-p4-agent-runtime-shell | P4 | 进行中（phase 已完成） | 预留NPC/Room QA共享平台空壳：注册中心+执行入口已落地，后续可直接承接业务编排 |
| ai-judge-runtime-verify-closure | P3 | 进行中（phase 已完成） | runtime verify 不再仅占位输出；judge-ops 已可自动归集 ai_judge 证据并生成统一摘要 |
| ai-judge-p2p3p4-evidence-closure | P3/P4 | 进行中（phase 已完成） | P2/P3/P4跨模块证据收口能力已落地，可自动识别缺失模块并输出缺口清单 |
| ai-judge-p5-calibration-prep | P5 | 进行中（prep 已完成） | P5在本地阶段完成模板化与清单化，真实环境数据校准保持延后并可追踪 |
| ai-judge-evidence-gap-remediation | P3/P4 | 进行中（phase 已完成） | 新增ai_judge_evidence_gap_remediation脚本与测试；补齐4份backfilled summary后，evidence_closure结果已转为pass |
| ai-judge-stage-closure-draft | P0 | 进行中（phase 已完成） | 新增ai_judge_stage_closure_draft脚本与测试，已产出收口草案摘要并通过harness_docs_lint |
| ai-judge-p5-real-calibration-on-env | P5 | 进行中（env_blocked，待真实环境） | 新增ai_judge_p5_real_calibration_on_env脚本与测试；当前仓库执行结果为env_blocked并已产出证据 |

### 3.1 进度口径

1. 已完成：阶段目标、主交付物、验证证据都已闭环。
2. 进行中：阶段已开始，但仍有关键交付物未落地。
3. 未开始：阶段尚未进入实施。
4. 延后：受真实环境、真实数据或外部依赖限制，当前不执行。

---

## 4. 当前阶段计划

## 4.1 阶段名称

`P1 平台骨架与持久化事实源落地`

## 4.2 阶段目标

在不保留兼容主链的前提下，把当前 `ai_judge_service` 从“FastAPI + pipeline 逻辑堆叠”重构为：

1. 有明确 `Application / Domain / Core / Infra` 分层的模块化单体
2. 以 `PostgreSQL` 为主事实源的裁判平台骨架
3. 具备 `Postgres-backed Orchestrator` 雏形的 durable workflow 基础
4. 为后续 Judge 主链迁移、复核/回放/审计收口，以及未来 `NPC / Room QA` 扩展打地基

## 4.3 本阶段范围

### A. 代码结构重构

1. 在 `ai_judge_service/app/` 下建立新的目标目录骨架：
   - `api/`
   - `applications/`
   - `domain/`
   - `core/`
   - `infra/`
2. 现有入口继续由 `main.py` 承接，但内部依赖改为走新分层。
3. 明确 `api` 不写编排，`infra` 不写业务规则。

### B. 数据与持久化底座

1. 引入 `SQLAlchemy 2.0 + asyncpg + Alembic`。
2. 建立第一批主事实源表：
   - `judge_jobs`
   - `case_dossiers`
   - `dispatch_receipts`
   - `judge_job_events`
   - `verdict_ledgers`
   - `review_cases`
   - `audit_alerts`
   - `replay_records`
3. 建立 DB session / repository / migration 基础设施。

### C. 工作流与治理底座

1. 定义统一 `WorkflowPort`。
2. 落地第一版 `Postgres-backed Orchestrator`。
3. 将案件状态迁移为数据库驱动，而不是以内存或 Redis 为主。
4. 为 trace / replay / review / alert 统一事件历史模型。

### D. 共享平台能力抽象

1. 抽出 `LLM Gateway` 初版，统一模型调用入口。
2. 抽出 `Knowledge Gateway` 初版，统一 RAG / Milvus / lexical / rerank 访问入口。
3. 抽出 `Trace / Audit` 接口层，为后续 Ops 收口准备。
4. 保留当前已经正确的治理能力方向：failed callback、audit alert、error code、degradation。

### E. 现有功能迁移边界

1. phase/final 外部 HTTP 契约保持当前主合同语义，不新增兼容字段。
2. 内部实现允许一步到位改走新分层、新 repository、新 workflow。
3. 不保留旧 `trace_store` 作为默认主链实现；若测试需要，可保留最小测试桩，但不能继续作为生产默认路径。

## 4.4 本阶段明确不做

1. 不实现 `AI NPC` 业务功能。
2. 不实现 `Room QA Agent` 业务功能。
3. 不做 `pgvector` 迁移。
4. 不引入 `Temporal`。
5. 不做真实流量压测阈值冻结、真实成本阈值冻结、真实公平 benchmark 冻结。
6. 不做链上锚定、ZK proof 或外部公开验证接口。

## 4.5 验收标准

1. 服务目录分层完成，新增代码默认进入新结构，不再继续把主逻辑堆到 `app_factory.py / phase_pipeline.py / trace_store.py`。
2. PostgreSQL migration 可执行，第一批主事实源表可创建。
3. `WorkflowPort` 与 `Postgres-backed Orchestrator` 能驱动至少一条 judge job 的基本状态流转。
4. dispatch receipt、trace/event history、replay record、audit alert 至少有一条数据库主链读写。
5. `LLM Gateway` 与 `Knowledge Gateway` 初版落地，旧上层逻辑开始改经由统一网关访问。
6. 当前 phase/final 主接口仍可工作，且不新增兼容层或双轨逻辑。
7. 测试基线完成更新，至少覆盖：
   - migration / repository 基本读写
   - workflow state transition
   - receipt / replay / alert 主链
   - app factory 与主契约未被破坏

## 4.6 交付物

1. 新分层代码骨架
2. 数据库 migration 与 repository 基础设施
3. `WorkflowPort` 与 `Postgres-backed Orchestrator`
4. `LLM Gateway` / `Knowledge Gateway` 初版
5. 第一批数据库主链测试
6. 阶段说明与必要文档更新

---

## 5. 延后事项（不阻塞当前阶段）

以下事项依赖真实环境或真实数据，当前明确延后：

1. 真实线上压测数据驱动的容量规划
2. 真实请求延迟分布驱动的 SLA 阈值冻结
3. 真实用户语料驱动的公平 benchmark 冻结
4. 基于真实成本账单的缓存/模型路由优化
5. `Temporal` 是否优于自建 orchestrator 的真实运维评估
6. `Milvus` 与其他向量后端的真实规模对比评估

---

### 下一开发模块建议

1. ai-judge-stage-closure-execute
### 模块完成同步历史

当前阶段的同步记录：

- 2026-04-13：推进 `ai-judge-p1-platform-core`；执行 P1：平台骨架与持久化事实源落地，先完成分层骨架与 Postgres 工作流底座

- 2026-04-13：推进 `ai-judge-p1-db-entity-expansion`；继续执行 P1：扩展主事实源表与仓储，先落地 dispatch_receipts/replay_records/audit_alerts 数据主链

- 2026-04-13：推进 `ai-judge-p1-runtime-migration`；继续执行 P1：将 phase/final 主状态流转迁移到 WorkflowOrchestrator + PostgresWorkflowStore，落地运行态与完成态事件落库

- 2026-04-13：推进 `ai-judge-p1-trace-fact-bridge`；P1继续执行：将trace_store的receipt/replay/audit_alert读写桥接到JudgeFactRepository，减少内存主链依赖

- 2026-04-13：推进 `ai-judge-p1-runtime-failure-coverage`；P1继续执行：补齐 blindization 与 final_contract_blocked 等分支的 workflow 失败事件覆盖及测试

- 2026-04-13：推进 `ai-judge-p1-gateway-bootstrap`；P1继续执行：落地LLM Gateway与Knowledge Gateway初版，并接入phase/final首条读取链路
- 2026-04-13：推进 `ai-judge-p2-judge-mainline-migration`；将final主链组装与契约校验从app_factory迁入applications/domain并保持API行为不变
- 2026-04-13：推进 `ai-judge-p2-phase-mainline-migration`；将phase主链调用入口迁移到applications/judge_mainline并保持API行为不变
- 2026-04-13：推进 `ai-judge-p3-replay-audit-ops-convergence`；将replay/audit序列化与report组装迁入applications并保持接口行为不变
- 2026-04-13：推进 `ai-judge-p4-agent-runtime-shell`；P4继续执行：落地Agent Runtime Shell（judge/npc_coach/room_qa profile + 统一执行入口），并将运行时装配接入 app_factory，补齐测试与门禁验证
- 2026-04-13：推进 `ai-judge-runtime-verify-closure`；继续执行runtime verify：judge-ops profile接入ai_judge门禁摘要证据扫描，支持输出pass/evidence_missing，并修复summary数组序列化
- 2026-04-13：推进 `ai-judge-p2p3p4-evidence-closure`；新增ai_judge证据收口脚本（P2/P3/P4 required modules），支持统一JSON/Markdown摘要与evidence_missing判定，并补齐脚本回归测试
- 2026-04-13：推进 `ai-judge-p5-calibration-prep`；新增P5校准准备脚本与回归测试：生成并校验延迟/成本/公平/故障/可信五类模板，输出pending_real_data摘要
- 2026-04-13：推进 `ai-judge-evidence-gap-remediation`；新增证据缺口回填脚本并补齐P2/P3/P4历史模块summary闭环

- 2026-04-13：推进 `ai-judge-stage-closure-draft`；新增阶段收口草案脚本，自动提取completed/todo候选并输出结构化草案
- 2026-04-13：推进 `ai-judge-p5-real-calibration-on-env`；新增P5真实环境校准门禁脚本，环境未就绪时返回env_blocked，环境就绪且证据完整时通过
### 2026-04-13 | ai-judge-p5-real-calibration-on-env（执行增量-1）

1. 新增 `scripts/harness/ai_judge_p5_real_calibration_on_env.sh`：实现 P5 真实环境校准门禁执行脚本
2. 引入真实环境就绪标记 `ai_judge_p5_real_env.env`（`REAL_CALIBRATION_ENV_READY`），未就绪时统一输出 `env_blocked`
3. 在环境就绪分支下，要求五类轨道同时满足“基础校准键 + real 证据键（`REAL_ENV_EVIDENCE/CALIBRATED_AT/CALIBRATED_BY/DATASET_REF`）”才判定 `pass`
4. 新增 `scripts/harness/tests/test_ai_judge_p5_real_calibration_on_env.sh`，覆盖 `env_blocked/pass/pending_real_data` 三条主链
5. 更新 `docs/harness/30-runtime-verify.md`，将 on-env 校准脚本纳入 runtime verify 可执行入口
6. 当前仓库执行结果：`bash scripts/harness/ai_judge_p5_real_calibration_on_env.sh --root /Users/panyihang/Documents/EchoIsle` 返回 `env_blocked`（符合“无真实环境时不假通过”约束），并产出门禁摘要工件
7. 验证通过：`bash scripts/harness/tests/test_ai_judge_p5_real_calibration_on_env.sh`，`bash scripts/harness/tests/test_ai_judge_calibration_prep.sh`，`bash scripts/quality/harness_docs_lint.sh --root /Users/panyihang/Documents/EchoIsle --json-out /tmp/harness_docs_lint_p5_real_on_env.json --md-out /tmp/harness_docs_lint_p5_real_on_env.md`，`bash skills/post-module-test-guard/scripts/test_change_guard.sh`，`bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode full`

### 2026-04-13 | ai-judge-stage-closure-draft（执行增量-1）

1. 新增 `scripts/harness/ai_judge_stage_closure_draft.sh`：从当前活动计划自动提取 AI judge 模块的 `completed/todo` 候选项，输出结构化草案
2. 草案输出遵循长期文档表头约束：`completed` 侧输出 `模块/结论/代码证据/验证结论/归档来源/关联待办`，`todo` 侧输出 `债务项/来源模块/债务类型/当前不做原因/触发时机/DoD/验证方式`
3. `todo` 候选自动吸收“延后事项”与 `on-env` 下一模块建议，确保真实环境依赖项不会在阶段收口时漏记
4. 新增 `scripts/harness/tests/test_ai_judge_stage_closure_draft.sh`，覆盖候选提取数量、`on-env` 债务映射、Markdown/JSON 结构输出
5. `docs/harness/task-flows/stage-closure.md` 增加草案模式指引：允许先生成草案再决定是否正式写入 `completed.md/todo.md`
6. 验证通过：`bash scripts/harness/tests/test_ai_judge_stage_closure_draft.sh`，`bash scripts/harness/ai_judge_stage_closure_draft.sh --root /Users/panyihang/Documents/EchoIsle`，`bash scripts/quality/harness_docs_lint.sh --root /Users/panyihang/Documents/EchoIsle --json-out /tmp/harness_docs_lint_stage_closure.json --md-out /tmp/harness_docs_lint_stage_closure.md`，`bash skills/post-module-test-guard/scripts/test_change_guard.sh`，`bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode full`

### 2026-04-13 | ai-judge-evidence-gap-remediation（执行增量-1）

1. 新增 `scripts/harness/ai_judge_evidence_gap_remediation.sh`：针对 P2/P3/P4 缺失模块自动回填标准化 `summary.json/.md` 证据
2. 回填摘要默认从 `docs/dev_plan/当前开发计划.md` 的模块同步历史提取，并在回填产物中显式标记 `backfilled: true` 与 `source: plan_history`
3. 新增 `scripts/harness/tests/test_ai_judge_evidence_gap_remediation.sh`，覆盖“已存在证据跳过 / 缺口回填 / 缺少历史摘要回退文案”三类主分支
4. `scripts/harness/journey_verify.sh` 的 `judge-ops` 提示链路已加入 remediation 命令指引（先补齐再 closure）
5. 运行态证据闭环结果：执行 `ai_judge_evidence_gap_remediation.sh` 后自动补齐 4 份历史模块 summary，`ai_judge_evidence_closure.sh` 结果由 `evidence_missing` 转为 `pass`
6. 验证通过：`bash scripts/harness/tests/test_ai_judge_evidence_gap_remediation.sh`，`bash scripts/harness/tests/test_ai_judge_evidence_closure.sh`，`bash scripts/harness/tests/test_journey_verify.sh`，`bash scripts/harness/ai_judge_evidence_gap_remediation.sh --root /Users/panyihang/Documents/EchoIsle`，`bash scripts/harness/ai_judge_evidence_closure.sh --root /Users/panyihang/Documents/EchoIsle`，`bash skills/post-module-test-guard/scripts/test_change_guard.sh`，`bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode full`

### 2026-04-13 | ai-judge-p5-calibration-prep（执行增量-1）

1. 新增 `scripts/harness/ai_judge_calibration_prep.sh`：为 P5 校准提供本地模板化准备脚本，覆盖延迟/成本/公平/故障演练/可信证明五类轨道
2. 脚本支持“缺真实样本时输出 `pending_real_data`”，避免本地阶段误判为 `pass`
3. 默认会在 `docs/loadtest/evidence/` 生成模板文件，形成后续真实环境填数的统一入口
4. 新增 `scripts/harness/tests/test_ai_judge_calibration_prep.sh`，覆盖“空目录模板生成 + 全量 validated 通过”两条主链
5. 更新 `docs/harness/30-runtime-verify.md`，将 calibration prep 纳入当前 runtime verify 证据入口
6. 验证通过：`bash scripts/harness/tests/test_ai_judge_calibration_prep.sh`，`bash scripts/harness/ai_judge_calibration_prep.sh --root /Users/panyihang/Documents/EchoIsle`

### 2026-04-13 | ai-judge-p2p3p4-evidence-closure（执行增量-1）

1. 新增 `scripts/harness/ai_judge_evidence_closure.sh`：统一聚合 P2/P3/P4 必要模块证据并输出 JSON/Markdown 摘要
2. 默认 required modules 固定为 `ai-judge-p2-judge-mainline-migration`、`ai-judge-p2-phase-mainline-migration`、`ai-judge-p3-replay-audit-ops-convergence`、`ai-judge-p4-agent-runtime-shell`、`ai-judge-runtime-verify-closure`
3. 收口结果支持明确 `pass/evidence_missing`，并在摘要中列出 `missing_modules` 缺口清单
4. `journey_verify.sh` 的 `judge-ops` 证据提示链路同步增加 `ai_judge_evidence_closure.sh` 引导入口
5. 新增 `scripts/harness/tests/test_ai_judge_evidence_closure.sh`，覆盖“证据齐全 pass / 缺失模块 evidence_missing”两条主分支
6. 更新 `docs/harness/30-runtime-verify.md`，将 ai_judge 证据收口脚本纳入当前运行态验证入口说明
7. 验证通过：`bash scripts/harness/tests/test_ai_judge_evidence_closure.sh`，`bash scripts/harness/tests/test_journey_verify.sh`，`bash scripts/harness/ai_judge_evidence_closure.sh --root /Users/panyihang/Documents/EchoIsle`，`bash skills/post-module-test-guard/scripts/test_change_guard.sh`，`bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode full`

### 2026-04-13 | ai-judge-runtime-verify-closure（执行增量-1）

1. `scripts/harness/journey_verify.sh` 增强 `judge-ops` profile：新增 ai_judge 模块门禁摘要自动扫描（`artifacts/harness/*ai-judge-*.summary.{json,md}`）
2. `judge-ops` profile 从固定 `evidence_missing` 升级为动态判定：有证据返回 `pass`，无证据返回 `evidence_missing`
3. 修复 `journey_verify` JSON 数组序列化边界：`source_refs/evidence_paths` 正确按分号拆分，避免被写成单字符串
4. 扩展 `scripts/harness/tests/test_journey_verify.sh`：新增 `judge-ops` 证据命中场景回归，验证输出状态与证据字段
5. 同步更新 `docs/harness/30-runtime-verify.md` 当前事实口径，明确 `judge-ops` 已接入证据扫描闭环
6. 验证通过：`bash scripts/harness/tests/test_journey_verify.sh`，`bash scripts/harness/journey_verify.sh --profile judge-ops --emit-json /tmp/ai_judge_judge_ops_runtime.json --emit-md /tmp/ai_judge_judge_ops_runtime.md`，`bash skills/post-module-test-guard/scripts/test_change_guard.sh`，`bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode full`

### 2026-04-13 | ai-judge-p4-agent-runtime-shell（执行增量-1）

1. 新增 `app/domain/agents` 领域层：定义 `AgentProfile/AgentExecutionRequest/AgentExecutionResult` 与 `AgentExecutorPort/AgentRegistryPort`
2. 新增 `app/applications/agent_runtime.py`：落地 `StaticAgentRegistry + AgentRuntime`，预注册 `judge/npc_coach/room_qa` 三类 Agent
3. `app_factory` 运行时装配新增 `agent_runtime`，并在 `applications/__init__.py` 导出构建入口，形成统一应用层装配边界
4. 新增 `tests/test_agent_runtime.py`，并扩展 `tests/test_app_factory.py`，覆盖 profile 注册、预留 Agent 返回语义与 runtime 注入断言
5. 验证通过：`../scripts/py -m ruff check app/app_factory.py app/applications app/domain/agents tests/test_agent_runtime.py tests/test_app_factory.py`，`../scripts/py -m pytest -q tests/test_agent_runtime.py tests/test_app_factory.py`，`../scripts/py -m pytest -q`，`bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode full`

### 2026-04-13 | ai-judge-p3-replay-audit-ops-convergence（执行增量-1）

1. 新增 `app/applications/replay_audit_ops.py`，承载 replay report payload/summary 组装与 alert/outbox/receipt 序列化逻辑
2. `applications/__init__.py` 导出 replay/audit 相关函数，形成可复用应用层接口
3. `app_factory` 中 `_build_replay_report_payload/_build_replay_report_summary/_serialize_*` 改为应用层委托调用，减少路由层业务拼装代码
4. 新增 `tests/test_replay_audit_ops.py`，覆盖 replay payload/summary 与 alert/outbox/receipt 序列化关键字段映射
5. 验证通过：`../scripts/py -m ruff check app/app_factory.py app/applications tests/test_replay_audit_ops.py`，`../scripts/py -m pytest -q tests/test_replay_audit_ops.py tests/test_app_factory.py`，`../scripts/py -m pytest -q`，`bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode full`

### 2026-04-13 | ai-judge-p2-phase-mainline-migration（执行增量-1）

1. 在 `app/applications/judge_mainline.py` 新增 phase 主链入口，统一由应用层代理 `phase_pipeline` 调用并注入 GatewayRuntime
2. `app_factory` 中 phase dispatch 与 replay-phase 两条链路改为调用 `applications.build_phase_report_payload`，减少路由层对 pipeline 细节耦合
3. 扩展 `applications/__init__.py` 导出 phase 主链入口，形成与 final 主链对称的应用层编排边界
4. 扩展 `tests/test_judge_mainline.py`，新增应用层 phase 委托测试，断言 llm/knowledge gateway 注入与调用参数正确
5. 验证通过：`python-venv-guard`，`../scripts/py -m ruff check app/app_factory.py app/applications app/domain/judge tests/test_judge_mainline.py`，`../scripts/py -m pytest -q tests/test_judge_mainline.py tests/test_app_factory.py tests/test_phase_pipeline.py`，`../scripts/py -m pytest -q`，`bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode full`

### 2026-04-13 | ai-judge-p2-judge-mainline-migration（执行增量-1）

1. 新增 `app/domain/judge/final_report.py`，承载 final 报告聚合主逻辑与契约校验，形成明确领域入口
2. 新增 `app/applications/judge_mainline.py` 并导出到 `applications/__init__.py`，将 final 主链能力收口到应用层
3. `app_factory` 删除大段 final 组装/校验细节，改为轻量编排调用 `applications`，保持 phase/final/replay 对外行为不变
4. 新增 `tests/test_judge_mainline.py`，覆盖 final 聚合正常场景、缺 phase 场景与契约缺失场景
5. 验证通过：`../scripts/py -m ruff check app/app_factory.py app/applications app/domain/judge tests/test_judge_mainline.py`，`../scripts/py -m pytest -q tests/test_judge_mainline.py tests/test_app_factory.py`，`../scripts/py -m pytest -q`

### 2026-04-13 | ai-judge-p1-runtime-failure-coverage（执行增量-1）

1. blindization 拒绝链路补齐 workflow 生命周期：新增 `register -> running -> failed` 事件，失败事件带 `input_not_blinded` 与 `sensitiveHits`
2. blindization 场景下 failed callback 失败分支新增 workflow `mark_failed`，错误码按 dispatch 维度落 `phase_failed_callback_failed/final_failed_callback_failed`
3. 新增 contract blocked 失败链路测试：验证 `final_contract_blocked` 分支 workflow 状态为 failed，且 failed callback 与 alert 同步主链生效
4. 扩展 `test_app_factory.py` 覆盖 blindization 成功/失败两条 failed callback 分支的 workflow 错误码与状态断言
5. 验证通过：`../scripts/py -m ruff check app tests` 与 `../scripts/py -m pytest -q`

### 2026-04-13 | ai-judge-p1-trace-fact-bridge（执行增量-1）

1. `app_factory` 增加 facts 桥接 helper：dispatch receipt 写入改为 `trace_store + JudgeFactRepository` 双写，读取优先 facts 回读
2. `POST /internal/judge/jobs/{job_id}/replay` 新增 replay 记录落库，`GET /internal/judge/jobs/{job_id}/trace` 回放历史优先读取 facts
3. final contract 阻断产生的 alert、以及 ack/resolve 状态迁移，均同步写入 facts；`alert_id` 在 trace 与 facts 间保持一致
4. 扩展 `JudgeFactRepository.upsert_audit_alert` 支持显式 `alert_id`，避免桥接过程出现 alert 主键漂移
5. 新增/更新测试：覆盖 receipt 回读 fallback、replay 落库、alert ack 同步、显式 alert_id upsert；验证通过 `../scripts/py -m pytest -q`

### 2026-04-13 | ai-judge-p1-runtime-migration（执行增量-1）

1. `app_factory` 已接入 `WorkflowRuntime`，运行态加载即具备 `workflow orchestrator + postgres store` 能力
2. phase/final dispatch 主链新增 workflow 事件：`register -> running -> completed/failed`
3. callback 失败、contract blocked 等失败路径补充 workflow `mark_failed` 落库
4. `test_app_factory.py` 增加 workflow 状态断言，验证 phase/final 成功与 phase 失败路径状态正确
5. 验证通过：`ruff check app tests` 与 `ai_judge_service` 全量 `pytest -q`

### 2026-04-13 | ai-judge-p1-db-entity-expansion（执行增量-1）

1. 扩展主事实源 ORM：新增 `dispatch_receipts`、`replay_records`、`audit_alerts`
2. 新增 Alembic 迁移 `20260413_0002_fact_source_expansion`，与 `0001` 串联升级
3. 新增 `domain.facts` 与 `infra.facts.JudgeFactRepository`，收敛 receipt/replay/alert 仓储读写
4. 补充仓储测试 `test_fact_repository.py`，覆盖 upsert/list/transition 关键路径
5. 验证通过：`ai_judge_service` 全量 `pytest -q`；`alembic upgrade head` 可创建扩展表

### 2026-04-13 | ai-judge-p1-platform-core（执行增量-1）

1. 新增分层骨架：`app/api`、`app/applications`、`app/core`、`app/domain`、`app/infra`
2. 新增 workflow 主链基础：`WorkflowPort`、`WorkflowOrchestrator`、`PostgresWorkflowStore`
3. 新增 SQLAlchemy async 数据底座与 Alembic：`judge_jobs`、`judge_job_events` 首批表
4. 扩展 `Settings`（DB 配置）并同步修复相关测试构造器
5. 验证通过：`ai_judge_service` 全量 `pytest -q`；Alembic `upgrade head` 可创建 workflow 核心表

### 2026-04-13 | ai-judge-plan-bootstrap

1. 将当前开发主线切换为 `AI_judge_service 平台化重构`
2. 修复 `当前开发计划.md` 缺少一级标题与 `default slot` 声明的问题
3. 写入第一版开发计划，并记录总进度与阶段划分

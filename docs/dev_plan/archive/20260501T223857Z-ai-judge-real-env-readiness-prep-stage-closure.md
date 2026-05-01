# 当前开发计划

关联 slot：`default`
更新时间：2026-05-01
当前主线：`AI_judge_service 官方 Judge App / Official Verdict Plane 维护与真实环境补证`
当前状态：已暂停 `NPC Coach` / `Room QA` 相关的一切开发内容；不再继续 P43 assistant executor、prompt/output、LLM Gateway、chat/frontend ready-state 或 Ops evidence 开发；当前没有真实环境，已新增 real-env readiness 输入模板与清单，对象存储本地 healthcheck evidence 与 preflight 仍保持阻塞口径

---

## 暂停声明（2026-05-01）

1. 根据最新产品决策，`NPC Coach` 与 `Room QA` 当前不再作为待开发功能推进。
2. 暂停范围包括：AI runtime 注册与 executor、assistant advisory contract、prompt / output schema、AI 内部路由、chat proxy、frontend read model / UI、Ops readiness、local canary、stage closure 与上线准备。
3. 已完成的 P43 Batch-A / Batch-B 仅作为历史开发事实记录，不再作为下一步开发依据。
4. 下一步开发不得继续推进 `ai-judge-p43-assistant-*` 模块；除非后续先冻结新的独立 PRD 和模块设计。
5. 当前计划的有效主线回到官方 AI Judge 裁判链、真实环境补证、生产对象存储验证和既有公平性 / trust / review 闭环维护。

## 0. 输入与决策依据

本轮计划基于以下材料生成：

1. 当前工作区代码事实（以代码为准，文档只作导航）。
2. [AI_Judge_Service-架构与技术栈决策方案-2026-04-13.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/AI_Judge_Service-架构与技术栈决策方案-2026-04-13.md)。
3. [AI_Judge_Service-企业级Agent服务设计方案-2026-04-13.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/AI_Judge_Service-企业级Agent服务设计方案-2026-04-13.md)。
4. [AI_Judge_Service-企业级Agent方案-章节完成度映射-2026-04-13.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/AI_Judge_Service-企业级Agent方案-章节完成度映射-2026-04-13.md)。
5. P42 阶段收口归档与证据：
   - [20260430T111133Z-ai-judge-stage-closure-execute.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260430T111133Z-ai-judge-stage-closure-execute.md)
   - [completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md) B46
   - [todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md) C45
   - [ai_judge_stage_closure_evidence.md](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_stage_closure_evidence.md)
6. PRD 对齐：
   - [product-goals.md](/Users/panyihang/Documents/EchoIsle/docs/harness/product-goals.md)
   - [在线辩论AI裁判平台完整PRD.md](/Users/panyihang/Documents/EchoIsle/docs/PRD/在线辩论AI裁判平台完整PRD.md)
   - `pre-module-prd-goal-guard` 已按高风险 AI Judge / cross-service 范围读取摘要与权威 PRD。

---

## 1. 当前代码事实快照

| 维度 | 当前代码事实 | 当前判断 |
| --- | --- | --- |
| P42 收口 | `completed.md` B46 已记录 P42 Interactive Guidance Plane 收口；`todo.md` C45 已记录真实环境与真实 LLM assistant executor 后置债；活动计划已归档到 `docs/dev_plan/archive/20260430T111133Z-ai-judge-stage-closure-execute.md` | `NPC Coach` / `Room QA` 已按最新产品决策暂停，P43 assistant readiness 不再作为下一步开发入口 |
| 真实环境 | 当前没有真实环境；`ai_judge_stage_closure_evidence.md` 显示 `runtime_ops_pack_status=local_reference_ready`，release readiness artifact 仍是 `env_blocked`，P41 control plane 与 panel shadow candidate 仍是 `env_blocked`；新增 [ai_judge_real_env_readiness_inputs.env.example](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_real_env_readiness_inputs.env.example) 与 [ai_judge_real_env_readiness_inputs_checklist.md](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_real_env_readiness_inputs_checklist.md) | 不执行或宣称 real-env pass；后续只在真实环境就绪后按模板填值、补证、preflight |
| 对象存储证据 | [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py) 已有对象存储 healthcheck；[artifact_store_healthcheck.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/scripts/artifact_store_healthcheck.py) 已新增脱敏 evidence CLI；[ai_judge_artifact_store_healthcheck.json](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_artifact_store_healthcheck.json) 已刷新为 `status=local_reference`、`productionReady=false`；[ai_judge_real_env_window_closure.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_real_env_window_closure.sh) 已能读取该 evidence 并自动推导 `PRODUCTION_ARTIFACT_STORE_READY` | 本地默认仍是 `local_reference`；`--preflight-only` 当前为 `env_blocked`，真实对象存储窗口执行通过后才能作为 real-env readiness 输入 |
| AI assistant runtime | [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py) 注册 `judge`、`npc_coach`、`room_qa`；`npc_coach` / `room_qa` 已支持 `disabled`、`placeholder`、`llm_canary` 三种显式 mode；`llm_canary` 在 executor 未接好或 provider/budget 不完整时返回 `assistant_executor_not_configured`，不回退 placeholder | 相关开发已暂停；不得继续接真实 executor 或扩展 assistant runtime |
| AI advisory contract | [assistant_advisory_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_advisory_contract.py) 已冻结 `assistant_advisory_contract_v1`、顶层 key、Room Context Snapshot、Stage Summary、advisory-only boundary、forbidden official output fail-closed；not_ready 已允许 `agent_not_enabled` 与 `assistant_executor_not_configured` | 相关开发已暂停；不再新增官方裁决外的 advisory 字段或合同 |
| AI prompt/output schema | [assistant_advisory_prompt.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_advisory_prompt.py) 已冻结 NPC Coach / Room QA prompt bundle；[assistant_advisory_output.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_advisory_output.py) 已冻结 `assistant_llm_output_contract_v1` 与安全字段 `safeGuidanceSummary`、`suggestedNextQuestions`、`contextCaveats`、`nextStepChecklist`、`sourceUsePolicy` | 相关开发已暂停；不再作为 executor 接入依据 |
| AI route | [assistant_agent_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_agent_routes.py) 已构建 shared context、knowledge gateway trace snapshot、policy isolation 与 response validator；带 `llmOutputContractVersion` 的 public output 会触发专用 schema 校验 | 相关开发已暂停；不继续扩展 AI 内部 route |
| LLM Gateway | [DefaultLlmGateway](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/gateways/default.py) 已封装 `call_openai_json` 与 gateway metadata；[GatewayLlmPolicy](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/gateways/ports.py) 已包含 provider/model/timeout/retry/usage/fallback policy | 不再接入 assistant executor；官方裁判主链仍按既有 gateway 边界维护 |
| settings | [settings.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/settings.py) 已新增 `AI_JUDGE_ASSISTANT_ADVISORY_EXECUTOR_MODE=disabled|placeholder|llm_canary`、assistant 专属 model/API key/timeout/retry/prompt tokens/output tokens/daily budget 与 policy version；生产环境禁止 placeholder，`llm_canary` 需要 OpenAI provider/key、非 local artifact store 与显式预算 | 相关开发已暂停；不再推进 assistant 专属配置到真实运行 |
| chat proxy | [assistant_advisory_proxy.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/assistant_advisory_proxy.rs) 已提供 AI internal key、timeout、case/session binding、Room Context / Stage Summary 二次合同校验、forbidden official/private field fail-closed；not_ready 已同步接受 `assistant_executor_not_configured` | 相关开发已暂停；不继续同步 OpenAPI、Rust validator 或 frontend ready-state |
| frontend read model | [debate-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/debate-domain/src/index.ts) 与 [DebateAssistantPanel.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/components/DebateAssistantPanel.tsx) 已能消费 `ok` / `not_ready` / `proxy_error` / `contract_violation` | 相关开发已暂停；不继续推进 Debate Assistant UI 或真实 `ok` 消费验证 |
| 热点文件 | 当前 `app_factory.py` 约 2346 行，`agent_runtime.py` 约 476 行，`assistant_agent_routes.py` 约 367 行，`assistant_advisory_contract.py` 约 468 行，`debate_judge.rs` 约 1589 行，`debate-domain/src/index.ts` 约 1602 行 | assistant 相关开发已暂停；后续若执行代码移除，应同步收缩这些热点文件与代码地图 |

---

## 2. 本轮主线定位

原 P43 目标是推进 `NPC Coach` / `Room QA` 的真实 assistant executor readiness。该方向已根据 2026-05-01 产品决策暂停。

当前有效主线调整为：

1. 不继续推进 `NPC Coach` / `Room QA` 的 executor、prompt、schema、route、chat proxy、frontend read model、Ops readiness 或 canary。
2. 不把已完成的 P43 Batch-A / Batch-B 作为继续开发依据。
3. 官方 `Judge App` / `Official Verdict Plane` 仍是 AI Judge 当前唯一有效开发主线。
4. 真实环境 pass、生产对象存储 roundtrip、真实样本 fairness benchmark、trust / review / ops 证据补齐仍按既有阻塞项管理。
5. 若未来重新启用用户助手或房间问答，必须先冻结独立 PRD 和模块设计，再重新生成开发计划。

一句话：

`P43 assistant readiness 已暂停；当前计划回到官方 AI Judge 主链维护与真实环境补证。`

---

## 3. 架构方案一致性校验

| 检查项 | P43 结论 |
| --- | --- |
| Official Verdict Plane 隔离 | 继续保持 Judge App 8 Agent 官方裁决主链为唯一有效 AI Judge 产品主线 |
| Interactive Guidance Plane 定位 | `NPC Coach` / `Room QA` 已暂停，不再作为当前开发面推进 |
| 统一门面 | 客户端仍只通过 `chat_server`，不直连 `ai_judge_service` |
| LLM Gateway | 不继续为 assistant executor 接入 `DefaultLlmGateway` / `LlmGatewayPort`；官方裁判主链仍按既有 gateway 边界维护 |
| Prompt / Policy Registry | 暂停 `NPC Coach` / `Room QA` 独立 advisory policy 与 prompt version 的后续开发 |
| 成本与延迟 | 暂停低延迟 assistant executor 的成本、延迟、重试与 no-secret guard 开发 |
| 真实环境 | 真实 provider/callback/对象存储/服务窗口未就绪时仍保持 `env_blocked`，不把 local canary 记为 real-env pass |
| 产品边界 | 当前不推进赛中陪聊、用户助手、房间问答、代打建议或无限制建议能力 |

---

### 已完成/未完成矩阵

| 阶段 | 目标 | 状态 | 说明 |
| --- | --- | --- | --- |
| `ai-judge-p43-plan-bootstrap-current-state` | 基于当前代码、两份方案、P42 收口与 PRD guard 生成 P43 详细计划 | 已完成（文档） | 当前文件即本模块产物；映射文档同步为 P43 已进入计划 |
| `ai-judge-p43-assistant-executor-config-policy-pack` | 冻结真实 assistant executor 配置、运行模式、生产校验与 policy 版本 | 已完成（后续暂停） | 已完成内容仅作历史事实记录，不再作为继续开发入口 |
| `ai-judge-p43-assistant-prompt-output-contract-pack` | 定义 NPC Coach / Room QA prompt bundle 与安全输出 schema | 已完成（后续暂停） | 已完成内容仅作历史事实记录，不再作为继续开发入口 |
| `ai-judge-p43-assistant-llm-gateway-executor-pack` | 新增 `_AssistantLlmAdvisoryExecutor` 并接入 `LlmGatewayPort` | 阻塞（已暂停） | 不执行 |
| `ai-judge-p43-assistant-safety-cost-latency-guard-pack` | 补齐真实 executor 的成本、延迟、重试、超时与 no-secret guard | 阻塞（已暂停） | 不执行 |
| `ai-judge-p43-chat-client-ready-state-contract-pack` | 验证 chat/frontend 对真实 `ok` advisory output 的消费合同 | 阻塞（已暂停） | 不执行 |
| `ai-judge-p43-assistant-runtime-readiness-ops-pack` | 将 assistant executor readiness 纳入 runtime ops / stage evidence | 阻塞（已暂停） | 不执行 |
| `ai-judge-p43-route-hotspot-split-pack` | 控制 P43 新增 executor/prompt/schema/ops 逻辑热点 | 阻塞（已暂停） | 不执行 |
| `ai-judge-p43-local-canary-regression-pack` | 刷新 P43 本地 canary 与合同回归证据 | 阻塞（已暂停） | 不执行 |
| `ai-judge-p43-stage-closure-execute` | P43 阶段收口 | 阻塞（已暂停） | 不执行 assistant 阶段收口；后续如需收口应围绕官方 Judge 主线重新定义 |
| `ai-judge-real-env-pass-window-execute-on-env` | 真实环境 pass 补证 | 阻塞 | 等待 `REAL_CALIBRATION_ENV_READY=true`、真实样本、真实 provider/callback、生产对象存储与真实服务窗口 |
| `ai-judge-artifact-store-healthcheck-evidence-cli` | 新增生产对象存储 healthcheck evidence CLI，输出脱敏 JSON 与 real-env ready 建议 | 已完成 | 新增 [artifact_store_healthcheck.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/scripts/artifact_store_healthcheck.py)，复用已有对象存储 write/head/read roundtrip；真实环境仍需在生产对象存储窗口执行 |
| `ai-judge-real-env-artifact-evidence-bridge` | artifact_store_healthcheck evidence 接入 real-env readiness | 已完成 | 新增 evidence JSON 输入、默认证据文件发现、证据存在时以 evidence 为准、ready/blocker 输出与专项回归 |
| `ai-judge-real-env-readiness-preflight` | real-env readiness 输入预检 | 已完成 | 新增 `--preflight-only` 与 ready/blocked 专项回归，防止真实窗口前缺键或 fake ready |
| `ai-judge-real-env-preflight-evidence-required` | real-env preflight evidence 必填 | 已完成 | `preflight-only` 下新增 `production_artifact_store_evidence_not_provided` blocker 与专项回归 |
| `ai-judge-real-env-artifact-healthcheck-run` | 执行对象存储 healthcheck evidence 与 real-env preflight | 已完成（本地阻塞证据） | 已刷新 [ai_judge_artifact_store_healthcheck.json](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_artifact_store_healthcheck.json)，当前 `provider=local`、`status=local_reference`、`productionReady=false`；`--preflight-only` 输出 `env_blocked`，blocker 包含真实环境 marker、真实样本、provider、callback、生产对象存储与目标阈值未 ready |
| `ai-judge-real-env-readiness-input-freeze` | 在无真实环境时冻结 real-env 输入模板与检查清单 | 已完成（本地准备） | 新增 [ai_judge_real_env_readiness_inputs.env.example](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_real_env_readiness_inputs.env.example) 与 [ai_judge_real_env_readiness_inputs_checklist.md](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_real_env_readiness_inputs_checklist.md)，默认所有 ready 值保持 `false`，明确禁止把 `local_reference`、mock provider/callback 或手工 ready 当作 real-env pass |

### 下一开发模块建议

1. 在真实环境开放前，不继续执行 real-env pass；保留当前 `env_blocked` 作为正确状态。
2. 等真实对象存储、真实样本、provider、callback 与目标阈值具备后，按 [ai_judge_real_env_readiness_inputs_checklist.md](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_real_env_readiness_inputs_checklist.md) 填值并重跑 `artifact_store_healthcheck.py --enable-roundtrip --fail-on-not-ready`。
3. 全部输入有证据后，重跑 `ai_judge_real_env_window_closure.sh --preflight-only`，直到状态从 `env_blocked` 变为 `preflight_ready`；`NPC Coach` / `Room QA` 保持暂停。

### 模块完成同步历史

- 2026-04-30：完成 `ai-judge-p42-stage-closure-execute`；P42 主体完成快照写入 `completed.md` B46，真实环境与真实 LLM assistant executor 债务写入 `todo.md` C45，活动计划归档并重置。
- 2026-04-30：生成 `ai-judge-p43-plan-bootstrap-current-state`；下一轮主线定位为真实 LLM assistant executor readiness，先冻结配置/策略/输出合同，再接入 LLM Gateway 与本地 canary。
- 2026-04-30：完成 `ai-judge-p43-assistant-executor-config-policy-pack`；新增 assistant executor mode/settings/production guard/runtime tags，覆盖默认 disabled、legacy placeholder、llm_canary not-ready 与 production guard 测试。
- 2026-04-30：完成 `ai-judge-p43-assistant-prompt-output-contract-pack`；新增 NPC Coach / Room QA prompt bundle、`assistant_llm_output_contract_v1`、public output schema validator、AI/chat not-ready code 同步与 forbidden output fail-closed 测试。
- 2026-05-01：根据最新产品决策暂停 `NPC Coach` / `Room QA` 相关一切开发；P43 assistant 后续 batch 不再执行，当前有效主线回到官方 Judge App / Official Verdict Plane 与真实环境补证。
- 2026-05-01：推进 `ai-judge-artifact-store-healthcheck-evidence-cli`；新增 artifact_store_healthcheck evidence CLI，复用现有对象存储 healthcheck，输出脱敏 JSON 与 PRODUCTION_ARTIFACT_STORE_READY 建议值，NPC Coach / Room QA 范围保持暂停未改动。
- 2026-05-01：推进 `ai-judge-real-env-artifact-evidence-bridge`；real-env window 已可读取 artifact_store_healthcheck evidence，并在 `productionReady=true` 时自动推导 `PRODUCTION_ARTIFACT_STORE_READY=true`；证据存在时以 evidence 为准，blocked/missing/invalid 保留具体 blocker，不推进 `NPC Coach` / `Room QA`。
- 2026-05-01：推进 `ai-judge-real-env-readiness-preflight`；real-env window closure 已支持 `--preflight-only`，可只校验真实样本 manifest、provider、callback、benchmark/fairness/runtime ops targets 与对象存储 healthcheck evidence，不执行 P5/runtime ops；`NPC Coach` / `Room QA` 保持暂停。
- 2026-05-01：推进 `ai-judge-real-env-preflight-evidence-required`；real-env preflight 已要求对象存储 healthcheck evidence；即使手工 `PRODUCTION_ARTIFACT_STORE_READY=true`，缺少 evidence 也会 `env_blocked`，避免 fake ready；`NPC Coach` / `Room QA` 保持暂停。
- 2026-05-01：推进 `ai-judge-real-env-artifact-healthcheck-run`；已按当前本地配置刷新对象存储 healthcheck evidence，结果为 `local_reference` / `productionReady=false`，并用 `--preflight-only` 验证 real-env window 仍输出 `env_blocked`；该结果只证明门禁正确阻断，不代表真实对象存储或 real-env pass。
- 2026-05-01：推进 `ai-judge-real-env-readiness-input-freeze`；确认当前没有真实环境，因此新增 real-env readiness 输入模板与检查清单，默认全部 ready 值保持 `false`，后续真实窗口开放后再按证据填值、preflight 与 pass。

---

## 7. Batch 计划

| Batch | 主题 | 目标 | 状态 |
| --- | --- | --- | --- |
| Batch-A | `executor-config-policy` | 冻结真实 executor mode、settings、生产校验、policy/prompt version 与默认 disabled 语义 | 已完成（后续暂停） |
| Batch-B | `prompt-output-contract` | 为 NPC Coach / Room QA 建立 prompt builder、结构化输出 schema 与 forbidden output guard | 已完成（后续暂停） |
| Batch-C | `llm-gateway-executor` | 新增真实 assistant executor，通过 `LlmGatewayPort` 调用 provider，并用 fake gateway 做本地 canary | 阻塞（已暂停） |
| Batch-D | `safety-cost-latency` | 补齐超时、重试、成本预算、usage metadata、no-secret 与 fail-closed 错误语义 | 阻塞（已暂停） |
| Batch-E | `cross-layer-ready-state` | 验证 chat/frontend 对真实 `ok` advisory output 的消费合同与 UI 呈现 | 阻塞（已暂停） |
| Batch-F | `ops-evidence-regression` | 将 assistant readiness 纳入 ops/evidence，刷新本地回归并阶段收口 | 阻塞（已暂停） |

---

## 8. 详细开发计划

> 暂停说明：本章 8.1 起的 `ai-judge-p43-assistant-*` 详细计划仅保留为历史记录。根据 2026-05-01 产品决策，`NPC Coach` / `Room QA` 相关开发全部暂停，以下内容不得继续作为执行清单使用。

### 8.1 `ai-judge-p43-assistant-executor-config-policy-pack`

**目标**

把真实 assistant executor 的启用条件从 P42 的 placeholder 开关中拆出来，形成清晰、安全、可审计的运行模式。

**当前代码入口**

1. [settings.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/settings.py)
2. [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py)
3. [test_settings.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/tests/test_settings.py)
4. [test_agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/tests/test_agent_runtime.py)

**实施步骤**

1. 新增真实 assistant executor 运行模式配置，建议命名：
   - `AI_JUDGE_ASSISTANT_ADVISORY_EXECUTOR_MODE=disabled|placeholder|llm_canary`
   - 默认 `disabled`
   - `placeholder` 仅本地/测试允许
   - `llm_canary` 允许真实 LLM executor 进入受控 canary
2. 新增 assistant 专属模型与预算配置，避免直接复用官方裁决参数：
   - `AI_JUDGE_ASSISTANT_OPENAI_MODEL`
   - `AI_JUDGE_ASSISTANT_TIMEOUT_SECONDS`
   - `AI_JUDGE_ASSISTANT_MAX_RETRIES`
   - `AI_JUDGE_ASSISTANT_MAX_PROMPT_TOKENS`
   - `AI_JUDGE_ASSISTANT_MAX_OUTPUT_TOKENS`
   - `AI_JUDGE_ASSISTANT_DAILY_COST_BUDGET_CENTS` 或等价预算字段
3. 保留 `AI_JUDGE_ASSISTANT_ADVISORY_PLACEHOLDER_ENABLED` 的测试意义，但在计划或代码注释里写清它是本地旧占位入口，真实 executor 不复用它作为生产开关。
4. 为生产环境补前置校验：
   - `placeholder` 在 production 禁止
   - `llm_canary` 在 production 需要 provider、API key、非 local artifact store 或明确 canary evidence 配置
   - provider missing 时不回退 placeholder，直接 `not_ready` 或 `assistant_executor_not_configured`
5. 在 `AgentProfile.tags` 中区分：
   - `disabled`
   - `deterministic_placeholder`
   - `llm_canary`
   - `advisory_only`
   - `no_verdict_write`
6. 更新 settings 与 runtime tests，覆盖默认 disabled、local placeholder、llm_canary、production 禁止 placeholder、production 缺 provider fail-fast。

**DoD**

1. `npc_coach` / `room_qa` 不再只有 placeholder enabled/disabled 两态。
2. 真实 executor 的启用条件、模型、超时、重试、预算都有显式配置入口。
3. provider 缺失时不会静默 fallback 到 placeholder。
4. 生产环境不会允许 placeholder 模式。

**执行结果（2026-04-30）**

1. 已在 [settings.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/settings.py) 新增 `AI_JUDGE_ASSISTANT_ADVISORY_EXECUTOR_MODE=disabled|placeholder|llm_canary`，并补齐 assistant 专属 policy/model/API key/timeout/retry/prompt tokens/output tokens/daily budget 配置。
2. 已保留 `AI_JUDGE_ASSISTANT_ADVISORY_PLACEHOLDER_ENABLED` 作为 P42 本地 deterministic placeholder 旧入口；真实 LLM 必须显式使用 `llm_canary` mode。
3. 已补生产前置校验：production 禁止 placeholder；production `llm_canary` 需要 OpenAI provider/key、非 local artifact store 与显式 daily budget。
4. 已在 [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py) 增加 `disabled` / `deterministic_placeholder` / `llm_canary` / `executor_configured` / `executor_not_configured` tags；`llm_canary` 在 executor 尚未接入或配置不全时返回 `assistant_executor_not_configured`，不会 fallback 到 placeholder。

**建议验证**

1. `ai_judge_service/.venv/bin/python -m pytest -q ai_judge_service/tests/test_settings.py ai_judge_service/tests/test_agent_runtime.py`
2. `ai_judge_service/.venv/bin/python -m ruff check ai_judge_service/app ai_judge_service/tests`

---

### 8.2 `ai-judge-p43-assistant-prompt-output-contract-pack`

**目标**

为 NPC Coach / Room QA 的真实 LLM 输出定义专用 prompt bundle 和结构化输出 schema，让真实模型只能产生安全的辅助建议。

**当前代码入口**

1. [assistant_advisory_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_advisory_contract.py)
2. [assistant_agent_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_agent_routes.py)
3. [domain/gateways/ports.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/gateways/ports.py)
4. [test_assistant_agent_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/tests/test_assistant_agent_routes.py)

**实施步骤**

1. 新增独立 helper 文件，建议：
   - `ai_judge_service/app/applications/assistant_advisory_prompt.py`
   - `ai_judge_service/app/applications/assistant_advisory_output.py`
2. 定义 `assistant_llm_output_contract_v1`，允许字段建议：
   - `safeGuidanceSummary`
   - `suggestedNextQuestions`
   - `contextCaveats`
   - `nextStepChecklist`
   - `sourceUsePolicy`
3. 明确禁止字段：
   - `winner`
   - `verdictReason`
   - `proScore` / `conScore`
   - `dimensionScores`
   - `fairnessGate`
   - `trustAttestation`
   - `rawPrompt`
   - `rawTrace`
   - `providerConfig`
   - `officialVerdictAuthority`
   - `writesVerdictLedger`
4. 为 NPC Coach prompt 固定策略：
   - 只能帮助用户组织公开论点、补证据、找未回应争点
   - 不能预测胜负
   - 不能指导规避规则、操控裁判或攻击对方身份
5. 为 Room QA prompt 固定策略：
   - 只解释房间阶段、公开上下文、阶段摘要状态
   - 可以说“当前上下文不足”
   - 不能提前暴露官方裁决、内部审计或最终胜负判断
6. 输出 validator 先验证 raw output，再 sanitize，最后交给 `assistant_advisory_contract_v1` 外层 validator。
7. 测试覆盖：
   - 合法 NPC 输出
   - 合法 Room QA 输出
   - 输出含 winner fail-closed
   - 输出含 score / verdictReason fail-closed
   - 空输出 / 非 object / 超长文本 fail-closed

**DoD**

1. 真实 LLM executor 有明确 prompt builder 和 output schema。
2. 输出 schema 不污染现有 `assistant_advisory_contract_v1` 顶层合同。
3. raw output 越权时 fail-closed，而不是只靠前端隐藏。

**执行结果（2026-04-30）**

1. 已新增 [assistant_advisory_prompt.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_advisory_prompt.py)，冻结 NPC Coach / Room QA 的 advisory-only prompt bundle、任务边界、输出 schema 描述与禁止字段。
2. 已新增 [assistant_advisory_output.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_advisory_output.py)，冻结 `assistant_llm_output_contract_v1`，真实模型原始输出只允许 `safeGuidanceSummary`、`suggestedNextQuestions`、`contextCaveats`、`nextStepChecklist`、`sourceUsePolicy`。
3. 已在 [assistant_agent_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_agent_routes.py) 接入带 `llmOutputContractVersion` 的 public output 校验，先验证 raw output / LLM public schema，再 sanitize，最后交给 `assistant_advisory_contract_v1` 外层合同。
4. 已同步 [assistant_advisory_proxy.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/assistant_advisory_proxy.rs) 的 not-ready error code 白名单，让 `assistant_executor_not_configured` 通过 chat 代理合同，不误判为 `assistant_advisory_contract_violation`。

**建议验证**

1. `ai_judge_service/.venv/bin/python -m pytest -q ai_judge_service/tests/test_assistant_agent_routes.py ai_judge_service/tests/test_agent_runtime.py`
2. `ai_judge_service/.venv/bin/python -m ruff check ai_judge_service/app/applications ai_judge_service/tests`

---

### 8.3 `ai-judge-p43-assistant-llm-gateway-executor-pack`

**目标**

新增真实 assistant executor，使 NPC Coach / Room QA 可以通过统一 `LlmGatewayPort` 获取结构化 advisory 输出，同时保留本地 fake gateway canary。

**当前代码入口**

1. [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py)
2. [infra/gateways/default.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/gateways/default.py)
3. [domain/gateways/ports.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/gateways/ports.py)
4. [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py)
5. [test_agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/tests/test_agent_runtime.py)
6. [test_app_factory_assistant_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/tests/test_app_factory_assistant_routes.py)

**实施步骤**

1. 从 `agent_runtime.py` 拆出 assistant executor helper，建议：
   - `assistant_advisory_executor.py`
2. 新增 `_AssistantLlmAdvisoryExecutor` 或公开类 `AssistantLlmAdvisoryExecutor`：
   - 接收 `kind`
   - 接收 `settings`
   - 接收 `llm_gateway`
   - 接收 prompt/output contract helpers
3. `build_agent_runtime` 增加可注入 gateway 参数，避免测试 monkeypatch 私有字段：
   - `build_agent_runtime(settings=settings, llm_gateway=...)`
   - 默认仍用现有 runtime wiring 的 gateway
4. 当 mode 为 `llm_canary`：
   - build prompt
   - 调用 `llm_gateway.call_json`
   - 验证 structured output
   - 返回 `AgentExecutionResult(status="ok", output=...)`
5. 当 provider/API key/模式不满足：
   - 返回 `status="not_ready"`
   - `error_code="assistant_executor_not_configured"` 或明确等价码
6. 当 provider 超时、结构化输出失败、合同越权：
   - 返回 `status="error"` 或在 route 层转换为 `assistant_advisory_contract_violation`
   - 不回退 placeholder
7. 新增 fake LLM gateway 测试：
   - NPC Coach 返回合法 ready advisory
   - Room QA 返回合法 ready advisory
   - fake gateway 返回 forbidden key 时 fail-closed
   - fake gateway timeout/exception 时 fail-closed

**DoD**

1. 真实 executor 不直接调用 `call_openai_json`，只依赖 `LlmGatewayPort`。
2. NPC Coach / Room QA 在 `llm_canary` 下能产生 `ok` advisory output。
3. 出错时 fail-closed，且不会污染官方裁决链。
4. 测试不依赖真实 OpenAI 网络。

**建议验证**

1. `ai_judge_service/.venv/bin/python -m pytest -q ai_judge_service/tests/test_agent_runtime.py ai_judge_service/tests/test_app_factory_assistant_routes.py`
2. `ai_judge_service/.venv/bin/python -m ruff check ai_judge_service/app ai_judge_service/tests`

---

### 8.4 `ai-judge-p43-assistant-safety-cost-latency-guard-pack`

**目标**

把真实 assistant executor 的安全、成本与延迟边界做成可验证的运行合同，避免低延迟交互平面变成不可控模型调用口。

**当前代码入口**

1. [runtime_errors.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/runtime_errors.py)
2. [runtime_policy.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/runtime_policy.py)
3. [settings.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/settings.py)
4. [assistant_advisory_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_advisory_contract.py)
5. [assistant_advisory_proxy.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/assistant_advisory_proxy.rs)

**实施步骤**

1. 定义 assistant executor 内部错误码：
   - `assistant_executor_not_configured`
   - `assistant_executor_timeout`
   - `assistant_executor_budget_exceeded`
   - `assistant_executor_bad_structured_output`
   - `assistant_executor_contract_violation`
2. 建立预算 guard：
   - 每次调用估算 prompt/output token 或 usage
   - 超预算 fail-closed
   - 本地阶段可以使用 fake usage，但字段结构先稳定
3. 建立 latency guard：
   - 使用 assistant 专属 timeout
   - timeout 后不重试到 placeholder
   - 输出 `not_ready` 或安全错误状态
4. 建立 no-secret guard：
   - raw output、gateway metadata、error message 均不能包含 provider config、API key、internal key
   - chat 侧 validator 继续二次防线
5. 记录内部 metadata，公开响应只保留安全状态：
   - 内部可记录 `model`, `usage`, `latencyMs`, `policyVersion`
   - 公开 `output` 不暴露 provider config 或 raw prompt
6. 测试覆盖：
   - budget exceeded
   - timeout
   - gateway exception
   - secret-like key / provider config 泄露
   - status reason 映射稳定

**DoD**

1. 真实 executor 的失败模式是产品可解释、可回归的。
2. 成本/延迟 guard 不依赖真实环境也能被 fake gateway 测试。
3. 公开响应不泄露 provider、secret、raw prompt 或内部 trace。

**建议验证**

1. `ai_judge_service/.venv/bin/python -m pytest -q ai_judge_service/tests/test_agent_runtime.py ai_judge_service/tests/test_assistant_agent_routes.py`
2. `cargo test -p chat-server request_room_qa_answer_should_return_proxy_error_when_ai_output_leaks_verdict -- --nocapture`

---

### 8.5 `ai-judge-p43-chat-client-ready-state-contract-pack`

**目标**

在不改变用户侧入口的前提下，验证 chat/frontend 已能消费真实 executor 的 `ok` advisory output。

**当前代码入口**

1. [assistant_advisory_proxy.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/assistant_advisory_proxy.rs)
2. [request_report_query.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/request_report_query.rs)
3. [openapi.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/openapi.rs)
4. [debate-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/debate-domain/src/index.ts)
5. [DebateAssistantPanel.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/components/DebateAssistantPanel.tsx)

**实施步骤**

1. 如果 AI output schema 只新增 `output` 内部安全字段，优先保持 chat/frontend 契约不变。
2. 如果需要新增公开状态字段，必须同轮更新：
   - Rust DTO
   - Rust validator
   - OpenAPI schema
   - debate-domain type / guard
   - DebateAssistantPanel view model
3. 增加 chat mock AI server 测试：
   - `ok` + real executor shaped output
   - forbidden official field -> `proxy_error`
   - provider config / secret -> `proxy_error`
4. 增加 frontend 测试：
   - ready advisory text and items
   - context caveats
   - no official verdict wording
   - contract violation error state
5. 保持普通 Debate Room 的 UI 文案只表达“辅助建议，不是官方裁决”。

**DoD**

1. chat proxy 不需要知道 LLM 细节，只验证 public advisory contract。
2. frontend 对真实 `ok` 输出展示为辅助建议，不展示胜负、评分、置信度或裁决理由。
3. OpenAPI 与 domain types 同步。

**建议验证**

1. `cargo test -p chat-server request_npc_coach_advice_should_proxy_ready_placeholder_contract -- --nocapture`
2. `pnpm --dir frontend --filter @echoisle/debate-domain test`
3. `pnpm --dir frontend --filter @echoisle/app-shell test DebateAssistantPanel`
4. `pnpm --dir frontend typecheck`

---

### 8.6 `ai-judge-p43-assistant-runtime-readiness-ops-pack`

**目标**

让 Ops / evidence 能看见 assistant executor readiness，但不把它误判为官方裁决 release readiness 或真实环境 pass。

**当前代码入口**

1. [runtime_readiness_public_projection.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/runtime_readiness_public_projection.py)
2. [route_group_ops_read_model_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_ops_read_model_pack.py)
3. [runtime_readiness_ops_projection.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/runtime_readiness_ops_projection.rs)
4. [runtimeReadiness.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/ops-domain/src/runtimeReadiness.ts)
5. [scripts/harness/ai_judge_runtime_ops_pack.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_runtime_ops_pack.sh)
6. [scripts/harness/ai_judge_stage_closure_evidence.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_stage_closure_evidence.sh)

**实施步骤**

1. 在 AI runtime ops pack 中新增 assistant plane readiness 摘要：
   - `assistantRuntimeMode`
   - `npcCoachStatus`
   - `roomQaStatus`
   - `contractVersion`
   - `executorMode`
   - `canaryStatus`
   - `productionReady=false`
2. 在 chat/frontend Ops read model 只展示安全摘要，不暴露 provider config。
3. stage closure evidence 增加 P43 assistant readiness 维度：
   - `assistant_executor_status=disabled|placeholder_local|llm_canary_ready|env_blocked`
   - `assistant_contract_status=ready`
   - `assistant_real_env_status=env_blocked`
4. 如果真实 provider 不可用，证据必须清楚写 `local_canary_ready` 或 `env_blocked`，不得写 `pass`。
5. 测试覆盖 projection sanitizer，确保 provider config / raw prompt / secret 不进入 Ops UI。

**DoD**

1. P43 readiness 证据能解释 assistant executor 到哪一步。
2. Ops 可见状态不等于 production release gate 通过。
3. 真实环境仍阻塞时，stage closure evidence 不误报 pass。

**建议验证**

1. `ai_judge_service/.venv/bin/python -m pytest -q ai_judge_service/tests/test_runtime_readiness_public_projection.py ai_judge_service/tests/test_route_group_ops_read_model_pack.py`
2. `cargo test -p chat-server runtime_readiness -- --nocapture`
3. `pnpm --dir frontend --filter @echoisle/ops-domain test`
4. `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --evidence-dir docs/loadtest/evidence --allow-local-reference`

---

### 8.7 `ai-judge-p43-route-hotspot-split-pack`

**目标**

控制 P43 新增逻辑的文件体积和模块边界，避免把 executor、prompt、schema、ops projection 都继续塞进热点文件。

**当前热点**

1. [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) 约 2346 行。
2. [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py) 约 476 行。
3. [assistant_advisory_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_advisory_contract.py) 约 468 行。
4. [debate-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/debate-domain/src/index.ts) 约 1602 行。

**实施步骤**

1. 新增 AI helper 文件，而不是扩张 `agent_runtime.py`：
   - `assistant_advisory_executor.py`
   - `assistant_advisory_prompt.py`
   - `assistant_advisory_output.py`
2. `agent_runtime.py` 只保留 registry/profile 装配和 executor 选择。
3. 如果 frontend 新增较多 view model，考虑拆到 `assistantAdvisory.ts` 或测试 helper，不继续膨胀 `debate-domain/src/index.ts`。
4. `app_factory.py` 只做 wiring，不写 executor 逻辑。
5. 更新 `docs/architecture/README.md` 的必要性判断：
   - 如果新增了第一跳入口或主模块边界，更新 AI advisory 第一跳地图。
   - 如果只是内部 helper 拆分，不强制更新。

**DoD**

1. P43 新增核心逻辑有独立 helper 文件。
2. `agent_runtime.py` 和 `app_factory.py` 不成为真实 executor 的逻辑堆积点。
3. 若第一跳入口变化，代码地图同步更新。

**建议验证**

1. `wc -l` 对比热点文件。
2. `rg -n "AssistantLlmAdvisoryExecutor|assistant_llm_output_contract" ai_judge_service/app ai_judge_service/tests`

---

### 8.8 `ai-judge-p43-local-canary-regression-pack`

**目标**

刷新 P43 本地参考证据，证明真实 assistant executor readiness 可以本地验证，同时仍明确真实环境阻塞。

**建议验证组合**

1. AI：
   - `ai_judge_service/.venv/bin/python -m pytest -q ai_judge_service/tests/test_settings.py ai_judge_service/tests/test_agent_runtime.py ai_judge_service/tests/test_assistant_agent_routes.py ai_judge_service/tests/test_app_factory_assistant_routes.py`
   - `ai_judge_service/.venv/bin/python -m ruff check ai_judge_service/app ai_judge_service/tests`
2. chat：
   - `cargo fmt --all -- --check`
   - `cargo test -p chat-server request_npc_coach_advice_should_proxy_not_ready_advisory_contract -- --nocapture`
   - `cargo test -p chat-server request_npc_coach_advice_should_proxy_ready_placeholder_contract -- --nocapture`
   - `cargo test -p chat-server request_room_qa_answer_should_return_proxy_error_when_ai_output_leaks_verdict -- --nocapture`
   - 新增真实 executor shaped `ok` 输出测试后同步运行
3. frontend：
   - `pnpm --dir frontend --filter @echoisle/debate-domain test`
   - `pnpm --dir frontend --filter @echoisle/app-shell test DebateAssistantPanel`
   - `pnpm --dir frontend typecheck`
   - `pnpm --dir frontend lint`
4. harness：
   - `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --evidence-dir docs/loadtest/evidence --allow-local-reference`
   - `bash scripts/harness/ai_judge_stage_closure_evidence.sh --root /Users/panyihang/Documents/EchoIsle`
   - `bash scripts/quality/harness_docs_lint.sh --root /Users/panyihang/Documents/EchoIsle`

**DoD**

1. 本地 canary 证明 `llm_canary` 合同可通。
2. forbidden official output、provider config 泄露、timeout、budget exceeded 都有负向测试。
3. evidence 口径清楚区分 `local_canary_ready`、`local_reference_ready` 与 `env_blocked`。

---

### 8.9 `ai-judge-p43-stage-closure-execute`

**目标**

完成 P43 阶段收口，把真实 assistant executor readiness 的主体成果沉淀到长期文档。

**实施步骤**

1. 执行阶段收口 evidence。
2. 将 P43 主体完成快照写入 [completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md)。
3. 将真实环境 pass、生产 provider/callback、生产对象存储、真实成本/延迟阈值冻结等仍阻塞项写入 [todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md)。
4. 归档当前活动计划到 [docs/dev_plan/archive](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive)。
5. 重置 [当前开发计划.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md)。

**DoD**

1. `completed.md` 只记录 P43 主体完成快照，不复制活动计划全文。
2. `todo.md` 只记录明确后置债务。
3. 当前计划归档、长期文档、stage closure evidence 三者一致。

---

## 9. 风险与边界

1. **真实环境风险**：没有真实 provider/callback/对象存储窗口时，不跑 real-env pass，不写 production-ready。
2. **产品定位风险**：NPC Coach / Room QA 不应变成赛中陪聊或代打建议；默认只提供受控辅助建议。
3. **裁决污染风险**：任何输出含胜负、评分、裁决理由、fairness gate、trust attestation 都必须 fail-closed。
4. **成本失控风险**：真实 executor 需要预算、timeout、max retries 与 usage accounting，不能只接 provider。
5. **跨层契约风险**：AI 输出 schema 变动必须同步 chat validator、OpenAPI、frontend domain guard 与测试。
6. **热点膨胀风险**：P43 的 executor/prompt/schema 必须拆 helper，不能继续把逻辑塞进 `agent_runtime.py` 或 `app_factory.py`。

---

## 10. 本轮不做

1. 不执行真实环境 pass。
2. 不把 placeholder 开成生产 fallback。
3. 不让用户端直连 AI 服务。
4. 不写 `verdict_ledger`、`judge_trace`、`fairness_report` 或 review queue。
5. 不引入 LangChain/LangGraph 作为主架构依赖。
6. 不进入 Protocol Expansion Layer：Identity Proof、Constitution Registry、Reason Passport、第三方 review network、on-chain anchor 均后置。

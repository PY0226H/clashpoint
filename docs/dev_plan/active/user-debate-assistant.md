# 当前开发计划：用户辩论助手 MVP

更新时间：2026-05-06
任务类型：dev / new feature
当前状态：执行中
活动 slot：`user-debate-assistant`

---

## 1. 计划目标

基于用户辩论助手 PRD 与 MVP 切片探索，落地首个可用闭环：

> 会员参赛用户在 Debate Room 打开私人辩论助手，基于当前房间公开上下文提问，AI 通过 LLM executor 返回私有、可操作、非官方裁决的总结或发言建议。

本阶段不是完整长期助手体系，目标是先把“会员私有助手 + 真实公开 transcript context + LLM 输出 + 双层合同校验 + 前端可用面板”跑通，并清理旧 `npc_coach` / `room_qa` 产品语义。

---

## 2. 上游依据

开发前优先阅读：

1. [用户辩论助手完整PRD.md](/Users/panyihang/Documents/EchoIsle/docs/PRD/用户辩论助手完整PRD.md)
2. [用户辩论助手_MVP切片与技术探索.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/用户辩论助手/用户辩论助手_MVP切片与技术探索.md)
3. [product-goals.md](/Users/panyihang/Documents/EchoIsle/docs/harness/product-goals.md)
4. [dev.md](/Users/panyihang/Documents/EchoIsle/docs/harness/task-flows/dev.md)
5. [docs/architecture/README.md](/Users/panyihang/Documents/EchoIsle/docs/architecture/README.md)

代码开发回合开始前必须运行 `pre-module-prd-goal-guard`。本计划本身是活动计划文档，不替代 PRD 或系统设计。

---

## 3. 已确认决策

1. MVP 采用方案 A：迁移现有 assistant advisory 资产到用户辩论助手主线。
2. 不新建独立助手服务。
3. 不让前端直连 `ai_judge_service`。
4. 不复用虚拟裁判 NPC 的公开房间事件链路。
5. 产品与代码主语义统一为 `debate_assistant`，不继续产品化 `npc_coach` / `room_qa`。
6. MVP 主执行器采用 LLM executor。
7. deterministic 逻辑只负责 transcript context 构建、测试 fixture、诊断和失败状态，不生成伪助手回答。
8. 首阶段只支持会员参赛用户；会员观战用户进入后续切片。
9. 产品未发布，默认硬切旧接口、DTO、agent kind 与前端文案；若测试或多调用方必须短期兼容，必须写明移除条件。

---

## 4. 当前代码事实

### 4.1 前端

1. [DebateAssistantPanel.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/components/DebateAssistantPanel.tsx) 已存在旧助手面板。
2. 当前 UI 是两个旧工具：`NPC Coach` 与 `Room QA`。
3. 面板调用 `requestNpcCoachAdvice` / `requestRoomQaAnswer`，来自 [frontend/packages/debate-domain/src/index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/debate-domain/src/index.ts)。
4. [DebateRoomPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/DebateRoomPage.tsx) 当前总是渲染 `DebateAssistantPanel`，并传入从公开验证 / challenge 视图推导的 `assistantCaseId`。
5. `messagesQuery.data` 已提供 `viewerRole`、`viewerSide`、`canSendMessage`，可复用作参赛 / 观战 UI 判断。
6. 当前没有会员锁定态、额度展示、快捷问题体系、私有对话历史或草稿优化专用交互。

### 4.2 前端 domain

1. [frontend/packages/debate-domain/src/index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/debate-domain/src/index.ts) 当前合同版本是 `assistant_advisory_contract_v1`。
2. 当前 agent kind 是 `npc_coach` / `room_qa`。
3. 前端已实现 advisory-only fail closed：
   - `advisoryOnly === true`
   - `officialVerdictAuthority === false`
   - `writesVerdictLedger === false`
   - `writesJudgeTrace === false`
4. 前端已拒绝 `winner`、`proScore`、`conScore`、`verdictLedger`、`judgeTrace` 等正式裁决字段。
5. 当前 `AssistantRoomContextSnapshot` 仍偏裁决 receipt / workflow 快照，不是实时 transcript context。

### 4.3 chat 后端

1. [chat/chat_server/src/handlers/debate_judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_judge.rs) 已有旧 route：
   - `POST /api/debate/sessions/{id}/assistant/npc-coach/advice`
   - `POST /api/debate/sessions/{id}/assistant/room-qa/answer`
2. 旧助手 route 已接入用户和 IP 限流，scope 为 `judge_assistant_advisory`。
3. [assistant_advisory_proxy.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/assistant_advisory_proxy.rs) 已有 chat 侧二次合同校验和 forbidden official fields guard。
4. [request_report_query.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/request_report_query.rs) 当前要求用户存在于 `session_participants`，非参赛用户返回 `judge_assistant_advisory_forbidden`。
5. 当前 proxy 只向 AI service 发送 `query` / `question` / `side` / `caseId`，没有发送实时 transcript context。
6. [message_pin.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/debate/message_pin.rs) 已有公开消息列表逻辑，可作为 transcript context 查询参考。
7. 数据库已有 `debate_topics`、`debate_sessions`、`session_participants`、`session_messages`。
8. 数据库已有 IAP / wallet 表，但未发现会员权益、订阅状态或助手额度正式模型。

### 4.4 ai_judge_service

1. [route_group_assistant.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_assistant.py) 已注册旧 internal route：
   - `/internal/judge/apps/npc-coach/sessions/{session_id}/advice`
   - `/internal/judge/apps/room-qa/sessions/{session_id}/answer`
2. [assistant_agent_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_agent_routes.py) 已能生成 advisory context 和响应合同。
3. [assistant_advisory_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_advisory_contract.py) 已有 advisory-only 合同与 forbidden official fields guard。
4. [assistant_advisory_output.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_advisory_output.py) 已有 LLM public output schema，但仍绑定 `npc_coach` / `room_qa`。
5. [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py) 当前 `llm_canary` 是 reserved executor，会返回 not_ready，不会真实调用 LLM。
6. [openai_judge_client.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/openai_judge_client.py) 已有 `call_openai_json`，可作为助手 LLM executor 的基础调用能力。
7. [build_shared_room_context_for_runtime](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/bootstrap_ops_panel_replay_payload_helpers.py) 偏 AI 裁判 dispatch receipt / workflow context，不是用户助手需要的实时 transcript context；且内部会读到 winner hint / report payload 类信息，不能作为助手主上下文继续扩展。

---

## 5. MVP 范围

### 5.1 本阶段必须做

1. 新增 `debate_assistant` 主语义合同和 route。
2. 前端房间面板产品化为“辩论助手”。
3. 非会员参赛用户看到锁定态和权益说明。
4. 会员参赛用户能发起助手请求。
5. chat 侧做权威会员 gate、参赛权限 gate、额度 gate、限流和合同二次校验。
6. chat 侧构建 `AssistantRoomTranscriptContext`，只包含公开可见房间数据。
7. ai_judge_service 用 LLM executor 基于 transcript context 生成结构化 advisory-only 输出。
8. 输出不得进入公开房间消息流，不自动写入输入框，不提供一键代发。
9. 输出不得预测最终胜负、暴露正式裁决内部字段或使用会员身份污染裁判标准。
10. 覆盖前端、chat、ai_judge_service 与端到端 smoke。

### 5.2 本阶段不做

1. 会员观战用户助手。
2. 主动连续监听和自动弹窗提醒。
3. 自动代发、一键代发、自动填充公开输入框。
4. 队伍共享助手或公开教练席。
5. 长期个人能力画像、跨场训练计划。
6. 复杂会员等级体系。
7. 完整赛后学习档案。
8. 让助手影响房间状态、暂停辩论或触发 NPC 效果。

---

## 6. 目标合同草案

系统设计阶段可微调字段名，但主语义应固定为 `debate_assistant`。

### 6.1 chat 用户侧接口

1. `GET /api/debate/sessions/{id}/assistant/debate-assistant/status`
   - 返回参赛权限、会员权益状态、额度状态、可用 intent、锁定态文案。
   - 不扣额度。
   - 非会员参赛用户返回 `available=false`，用于前端锁定态。

2. `POST /api/debate/sessions/{id}/assistant/debate-assistant/query`
   - body 包含 `intent`、`question`、可选 `draft`、可选 `side`、可选 `traceId`、可选 `caseId`。
   - `intent` 首版支持：
     - `room_summary`
     - `opponent_summary`
     - `unanswered_points`
     - `speech_structure`
     - `draft_polish`
   - 返回 `DebateAssistantOutput`。

### 6.2 chat 到 AI service internal 接口

1. `POST /internal/judge/apps/debate-assistant/sessions/{session_id}/query`
2. 请求体必须包含：
   - `trace_id`
   - `intent`
   - `question`
   - `draft`
   - `side`
   - `caseId`
   - `roomTranscriptContext`
3. AI service 不主动拉 chat 数据；它只消费 chat 给出的最小公开上下文。

### 6.3 输出合同

建议新版本：

1. `version = debate_assistant_contract_v1`
2. `agentKind = debate_assistant`
3. `advisoryOnly = true`
4. `capabilityBoundary` 必须继续声明：
   - `officialVerdictAuthority = false`
   - `writesVerdictLedger = false`
   - `writesJudgeTrace = false`
   - `canTriggerOfficialJudgeRoles = false`
5. `output` 建议包含：
   - `answerSummary`
   - `keyPoints`
   - `suggestedActions`
   - `contextCaveats`
   - `boundaryNotice`
   - `sourceUsePolicy`
6. 合同必须 fail closed 拒绝：
   - 正式胜负、正式评分、裁判 trace、内部 prompt、provider config、用户隐私、钱包余额、会员身份对裁判的任何影响表达。

---

## 7. 数据模型草案

### 7.1 会员权益

当前代码未发现会员 / 订阅 / entitlement 正式模型。本阶段建议新增最小权益模型：

1. `user_entitlements`
   - `user_id`
   - `feature_key`
   - `status`
   - `source`
   - `starts_at`
   - `expires_at`
   - `created_at`
   - `updated_at`
2. `feature_key = debate_assistant`
3. `status` 首版可收敛为 `active / revoked`。
4. MVP 可以用 fixture / ops seed 授权会员，不接复杂购买链路。
5. 后续会员订阅系统成型后再收敛为统一 membership 模块。

### 7.2 使用额度

建议首版按“每场”扣减：

1. `debate_assistant_session_usage`
   - `user_id`
   - `session_id`
   - `used_count`
   - `quota_limit`
   - `updated_at`
   - `created_at`
2. 默认 quota 可先配置为每场 20 次。
3. chat 在请求 AI service 前做 quota 预检。
4. 建议扣减策略：AI service 成功返回且 chat 合同校验通过后确认扣减；AI 不可用、超时或合同失败不扣减。
5. 如果实现需要预占防并发，必须在事务里提供失败返还或过期释放机制。

---

## 8. 开发切片

### S0：系统设计确认

目标：把本计划落成系统设计，再开始跨层代码改造。

任务：

1. 运行 `pre-module-prd-goal-guard`。
2. 新增 `docs/module_design/用户辩论助手/用户辩论助手_系统设计.md`。
3. 明确 `debate_assistant_contract_v1` 的请求、响应、错误码与 intent。
4. 明确旧 `npc_coach` / `room_qa` 硬切清理边界。
5. 明确会员权益、额度扣减、AI 失败是否扣减额度的最终方案。
6. 明确 transcript 最近消息窗口，建议默认最近 60 条公开消息。
7. 明确 LLM provider/model/timeout/retry/budget/canary 方案。
8. 预判是否需要更新 `docs/architecture/README.md`。

验收：

1. 系统设计覆盖前端、chat、ai_judge_service、DB、OpenAPI、测试矩阵。
2. 不再把“是否选方案 A”或“是否用 LLM executor”列为待决问题。
3. 若保留任何短期兼容层，写明移除条件。

### S1：跨层合同与命名硬切

目标：建立 `debate_assistant` 主合同骨架，消除用户可见旧语义。

任务：

1. 前端 domain 新增 `RequestDebateAssistantInput`、`DebateAssistantOutput`、`DebateAssistantStatusOutput`。
2. 前端 domain 新增 `requestDebateAssistantStatus` 与 `requestDebateAssistant`。
3. chat 新增用户侧 status/query route。
4. chat 新增 `DebateAssistant*` DTO、OpenAPI schema、config path。
5. ai_judge_service 新增 `AGENT_KIND_DEBATE_ASSISTANT` 与 internal route。
6. 合同版本升级到 `debate_assistant_contract_v1`。
7. 旧 `npc_coach` / `room_qa` route、DTO、测试与前端调用按硬切策略迁移或删除。

主要文件：

1. `frontend/packages/debate-domain/src/index.ts`
2. `frontend/packages/debate-domain/src/index.test.ts`
3. `chat/chat_server/src/handlers/debate_judge.rs`
4. `chat/chat_server/src/models/judge/types.rs`
5. `chat/chat_server/src/models/judge/assistant_advisory_proxy.rs`
6. `chat/chat_server/src/models/judge/request_report_query.rs`
7. `chat/chat_server/src/config.rs`
8. `chat/chat_server/src/lib.rs`
9. `chat/chat_server/src/openapi.rs`
10. `ai_judge_service/app/domain/agents/models.py`
11. `ai_judge_service/app/applications/route_group_assistant.py`
12. `ai_judge_service/app/applications/assistant_agent_routes.py`
13. `ai_judge_service/app/applications/assistant_advisory_contract.py`
14. `ai_judge_service/app/applications/assistant_advisory_output.py`

验收：

1. 新 API 不再暴露 `NPC Coach` / `Room QA` 产品文案。
2. 新合同继续 fail closed 拒绝正式裁决字段。
3. 旧调用方全部迁到 `debate_assistant`。
4. OpenAPI 包含新 route 和新 DTO。

### S2：会员权益与额度 gate

目标：chat 成为权威权限边界，前端只负责展示。

任务：

1. 新增权益与额度 migration。
2. 新增 entitlement 查询方法。
3. 新增 quota 查询、扣减和快照方法。
4. `GET status` 返回会员锁定态、剩余额度、恢复/升级提示。
5. `POST query` 在调用 AI service 前执行：
   - session exists
   - participant check
   - entitlement check
   - quota check
   - request rate limit
6. 错误码建议：
   - `debate_assistant_forbidden`
   - `debate_assistant_membership_required`
   - `debate_assistant_quota_exhausted`
   - `debate_assistant_contract_violation`
   - `debate_assistant_proxy_failed`

验收：

1. 非参赛用户不能请求。
2. 非会员参赛用户能查 status 看到锁定态，但不能 query。
3. 会员额度耗尽时 query 返回稳定错误。
4. AI 失败或合同失败不误扣额度。
5. 任何 gate 都不读取或输出钱包余额、手机号、邮箱。

### S3：AssistantRoomTranscriptContext

目标：让助手回答基于真实公开房间上下文，而不是裁决 receipt 或模板。

任务：

1. chat 侧新增 `AssistantRoomTranscriptContext` 构建器。
2. 查询 `debate_sessions` + `debate_topics` 获取：
   - session id
   - status
   - topic title / description / category
   - pro/con stance
   - participant counts
3. 查询当前用户在 `session_participants` 的 side。
4. 查询最近 N 条 `session_messages`，建议 N=60，按时间升序给 AI。
5. 可包含公开可见的裁决阶段状态，但不得包含内部 score、trace、prompt、审计字段。
6. 明确不包含：
   - 手机号、邮箱
   - 钱包余额、消费能力
   - 历史声誉、历史胜率
   - 其他用户私密信息
   - `winner`、`proScore`、`conScore`、`judgeTrace`
7. context 生成过程必须可单元测试、可回放。

验收：

1. context 能支撑 `room_summary`、`opponent_summary`、`unanswered_points`、`speech_structure`、`draft_polish`。
2. context 字段白名单测试覆盖隐私与正式裁决字段。
3. 长对局先只使用最近 N 条，不做长期摘要。
4. context 构建失败时返回稳定错误，不调用 LLM。

### S4：chat proxy 与二次合同校验

目标：chat 代理 AI service，并继续作为终端用户安全边界。

任务：

1. 新增 `fetch_ai_judge_debate_assistant_payload`。
2. 请求 AI service 时携带 `roomTranscriptContext`。
3. 新增 `validate_debate_assistant_payload`。
4. 复用并升级 forbidden official fields guard。
5. 校验 `agentKind == debate_assistant`、`version == debate_assistant_contract_v1`、`sessionId`、`caseId`。
6. 合同失败返回稳定 proxy error，不向前端泄漏 AI 原始响应。
7. quota 成功扣减只发生在合同通过后。

验收：

1. AI service 返回 forbidden field 时被 chat fail closed。
2. AI service 超时 / 5xx / bad JSON 返回稳定错误。
3. 成功输出不进入公开消息表，也不触发任何房间事件。
4. 旧 `assistant_advisory_proxy` 中可复用逻辑完成重命名或拆分，不留下长期旧语义。

### S5：ai_judge_service LLM executor

目标：实现真正的 `debate_assistant` LLM executor。

任务：

1. 新增或重构 `DebateAssistantExecutor`。
2. 使用 `call_openai_json` 或等价 LLM gateway 调用。
3. 将现有 `llm_canary` reserved 行为替换为真实 LLM executor，或硬切为 `llm` mode。
4. 构建 prompt：
   - 私人辅助，不代表官方裁决
   - 只能基于 `roomTranscriptContext`
   - 不预测最终胜负
   - 不输出正式评分、置信度、trace、内部 prompt
   - 不自动代发
   - 信息不足必须说明不确定
5. 输出 schema 与 `debate_assistant_contract_v1` 对齐。
6. 设置 timeout、retry、max prompt tokens、max output tokens、daily budget。
7. LLM 不可用时返回 `not_ready` / `assistant_executor_not_configured`，不生成 deterministic 伪回答。

验收：

1. 每个 intent 至少有一个结构化输出测试。
2. fake LLM gateway 可注入，用于稳定测试。
3. 输出包含 boundary notice 与 uncertainty / caveats。
4. 输出带 forbidden official fields 时被 AI service fail closed。
5. LLM 未配置时返回 not_ready，不扣额度。

### S6：前端产品化助手面板

目标：把旧开发期面板改成用户可用的会员辩论助手。

任务：

1. `DebateAssistantPanel` UI 改为单一“辩论助手”面板。
2. 移除用户可见 `NPC Coach` / `Room QA` 文案。
3. 加入快捷问题：
   - 总结当前争点
   - 对方刚才说了什么
   - 我方还没回应什么
   - 给我一个发言结构
   - 帮我优化这段草稿
4. 加入非会员锁定态和权益说明。
5. 加入额度展示。
6. 加入草稿输入模式，但不自动写入公开消息输入框。
7. 输出展示：
   - 简短结论
   - 要点列表
   - 行动建议
   - 不确定性提示
   - “私人辅助，不是官方裁决”边界声明
8. 面板关闭 / 收起不影响消息流、输入框、NPC 面板和裁决报告。

验收：

1. 非会员态不发起 query POST。
2. 会员态快捷问题能发起 query。
3. 草稿优化不会自动发送公开消息。
4. 输出不渲染 Winner / Score / Judge Trace 等正式裁决语义。
5. Mobile / desktop 布局不遮挡发言区。

### S7：端到端闭环与运行态 smoke

目标：完成 Debate Room 内一次完整助手请求。

任务：

1. 准备会员参赛用户 fixture。
2. 准备非会员参赛用户 fixture。
3. 准备至少一场 running session 和最近消息。
4. 启动 chat 与 ai_judge_service。
5. 验证会员用户获取 `room_summary`。
6. 验证会员用户获取 `speech_structure`。
7. 验证非会员看到锁定态。
8. 验证助手失败不影响房间消息发送。
9. 验证 Judge / Draw / NPC 主流程不受影响。

验收：

1. 端到端请求成功返回私有助手结果。
2. 公开 `session_messages` 不新增助手内容。
3. quota 成功扣减。
4. 非会员不扣 quota。
5. 合同失败路径可观测且 fail closed。

### S8：清理、文档与代码地图

目标：收束旧语义并留下可维护入口。

任务：

1. 删除或迁移旧 `npc_coach` / `room_qa` 用户侧产品文案。
2. 清理旧测试名和旧 fixture，保留必要合同 guard 测试。
3. 更新 `docs/architecture/README.md`，因为本次会新增第一跳定位入口：
   - 前端辩论助手面板
   - chat assistant route / gate / context builder
   - ai_judge_service debate assistant LLM executor
4. 更新本活动计划执行状态。
5. 输出 commit message 推荐。

验收：

1. 代码地图包含用户辩论助手首跳入口。
2. 文档不再把 `npc_coach` / `room_qa` 当作当前产品主线。
3. 活动计划能支持阶段收口进入 `completed.md` / `todo.md`。

---

## 9. 测试矩阵

### 9.1 前端

目标测试：

1. `frontend/packages/debate-domain/src/index.test.ts`
   - status API 解析。
   - query API 请求体 trim / intent 校验。
   - `debate_assistant_contract_v1` fail closed。
   - forbidden official fields fail closed。

2. `frontend/packages/app-shell/src/components/DebateAssistantPanel.test.tsx`
   - 非会员锁定态。
   - 会员快捷问题。
   - quota exhausted 展示。
   - LLM not_ready / proxy_error 展示。
   - 草稿优化不自动发送。

建议命令：

```bash
cd frontend && pnpm --filter @echoisle/debate-domain test
cd frontend && pnpm --filter @echoisle/app-shell test
```

### 9.2 chat

目标测试：

1. handler route：
   - status 非会员锁定态。
   - query 非会员拒绝。
   - query 额度耗尽拒绝。
   - query 非参赛用户拒绝。
   - query 限流保持。

2. model / domain：
   - entitlement active / revoked。
   - quota check / deduct。
   - transcript context 只含公开字段。
   - transcript 最近 N 条排序正确。
   - AI proxy 失败返回稳定错误。
   - AI payload 泄漏正式字段时 fail closed。

建议命令：

```bash
cd chat && cargo test -p chat-server debate_assistant
cd chat && cargo test -p chat-server request_judge_report_query
```

### 9.3 ai_judge_service

注意 Python 命令必须使用项目 venv：

```bash
/Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/python -m pytest ai_judge_service/tests/test_debate_assistant_*.py
```

目标测试：

1. route 注册：
   - `debate_assistant` internal route 存在。
   - internal key 缺失拒绝。

2. context / prompt：
   - prompt 包含私人辅助和非官方裁决边界。
   - prompt 不包含手机号、邮箱、钱包余额、会员身份对裁决影响字段。

3. LLM executor：
   - fake LLM 返回结构化成功输出。
   - fake LLM 输出 forbidden fields 时 fail closed。
   - LLM 未配置返回 not_ready。
   - 超时返回稳定错误。

4. contract：
   - `debate_assistant_contract_v1` exact keys。
   - `advisoryOnly` / forbidden write targets / official authority 校验。

### 9.4 运行态 smoke

建议在代码完成后按实际脚本选择：

```bash
pnpm e2e:smoke:web
pnpm e2e:smoke:desktop
```

若真实 LLM 凭据不可用，必须至少跑：

1. fake LLM contract smoke。
2. LLM not_ready smoke。
3. 非会员锁定态 smoke。
4. 助手失败不影响发言 smoke。

---

## 10. 风险与处理

1. 会员模型缺失  
   处理：先落最小 `user_entitlements`，不要把 wallet 余额当会员权益。

2. 旧 `npc_coach` / `room_qa` 调用方多  
   处理：优先同回合硬切；若必须短期兼容，注释写明移除条件和目标切片。

3. transcript context 过长导致 LLM 成本和延迟不可控  
   处理：首版最近 60 条 + 字符截断 + prompt token 上限。

4. LLM 幻觉或输出正式裁决语义  
   处理：prompt 边界 + AI service 合同校验 + chat 二次校验 + 前端 fail closed。

5. quota 并发扣减不一致  
   处理：chat 使用事务和行级锁，合同成功后确认扣减；失败不扣。

6. 助手与 NPC / AI Judge 混淆  
   处理：产品文案、route、agent kind、样式和合同都使用 `debate_assistant`，明确“私人辅助，不是官方裁决”。

---

## 11. DoD

本阶段完成定义：

1. 会员参赛用户可以在 Debate Room 内打开辩论助手并获得 LLM 生成的私有建议。
2. 非会员参赛用户只能看到锁定态和权益说明，不能调用 query。
3. 助手至少支持 `room_summary`、`opponent_summary`、`unanswered_points`、`speech_structure`、`draft_polish`。
4. chat 构建并传递真实公开 transcript context。
5. AI service 使用真实 LLM executor 主路径，不以 deterministic template 冒充助手回答。
6. 输出不进入公开房间消息流，不自动发送，不自动填充发言输入框。
7. 双层合同校验能阻断正式裁决字段、内部 trace、隐私字段和 provider 配置泄漏。
8. 会员 gate、额度 gate、参赛权限 gate 均有测试。
9. 前端、chat、ai_judge_service 的核心测试通过。
10. 至少完成一条运行态 smoke 证据。
11. 若新增或移动第一跳入口，已更新 `docs/architecture/README.md`。

---

## 12. 当前执行状态

| 切片 | 状态 | 说明 |
|---|---|---|
| S0 系统设计确认 | 已完成 | 已新增 `docs/module_design/用户辩论助手/用户辩论助手_系统设计.md`；`pre-module-prd-goal-guard` 已运行，并手动回读用户辩论助手 PRD |
| S1 跨层合同与命名硬切 | 已完成 | 已新增 `debate_assistant` 用户侧 route / DTO / OpenAPI / 前端 SDK / AI internal route |
| S2 会员权益与额度 gate | 已完成 | 已新增最小 `user_entitlements` 与 `debate_assistant_session_usage`，query 成功合同通过后扣减 |
| S3 Transcript Context | 已完成 | chat 构建最近 60 条公开消息上下文，带隐私/正式裁决 redaction 标记 |
| S4 chat proxy 与二次合同校验 | 已完成 | chat 代理 AI service，校验合同、agent kind、context、forbidden fields，AI 失败/合同失败不扣额度 |
| S5 AI service LLM executor | 已完成 | `llm` mode 下启用 `debate_assistant` LLM executor；未配置时返回 `not_ready`，不生成 deterministic 伪回答 |
| S6 前端产品化助手面板 | 已完成 | Debate Room 面板已切为单一“辩论助手”，包含会员锁定态、额度、快捷问题、草稿优化和私有回复展示 |
| S7 端到端闭环与 smoke | 待执行 | 需要启动 chat / ai_judge_service 与会员 fixture 做真实运行态 smoke |
| S8 清理、文档与代码地图 | 进行中 | 已更新架构代码地图；旧 `npc_coach` / `room_qa` 历史测试资产暂保留 |

### 12.1 本轮已运行验证

1. `cd chat && cargo test -p chat-server debate_assistant -- --nocapture`
2. `cd chat && cargo fmt --all`
3. `cd chat && cargo check -p chat-server`
4. `cd ai_judge_service && /Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/python -m unittest tests.test_agent_runtime tests.test_app_factory_assistant_routes -v`
5. `cd frontend && pnpm --filter @echoisle/debate-domain test`
6. `cd frontend && pnpm --filter @echoisle/app-shell test`
7. `cd frontend && pnpm --filter @echoisle/debate-domain typecheck`
8. `cd frontend && pnpm --filter @echoisle/app-shell typecheck`
9. `cd frontend && pnpm --filter @echoisle/debate-domain lint`
10. `cd frontend && pnpm --filter @echoisle/app-shell lint`
11. `git diff --check`

# 虚拟裁判 NPC 下一阶段开发计划

更新时间：2026-05-04
文档状态：active 开发计划，P2-H 已完成
当前主线：`virtual-judge-npc-real-env-and-pause-suggestion`

关联 PRD：[虚拟裁判NPC完整PRD.md](/Users/panyihang/Documents/EchoIsle/docs/PRD/虚拟裁判NPC完整PRD.md)
关联系统设计：[虚拟裁判NPC_系统设计.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_系统设计.md)
关联暂停设计：[虚拟裁判NPC_暂停恢复状态机设计.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_暂停恢复状态机设计.md)
关联运行态证据：[虚拟裁判NPC_运行态Smoke与观测基线.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_运行态Smoke与观测基线.md)
关联真实环境 readiness：[虚拟裁判NPC_Beta真实环境Readiness输入清单.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_Beta真实环境Readiness输入清单.md)
关联 dashboard 查询包：[虚拟裁判NPC_CanaryDashboard查询与告警基线.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_CanaryDashboard查询与告警基线.md)
关联暂停建议合同：[虚拟裁判NPC_pause_suggestion合同冻结.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_pause_suggestion合同冻结.md)
上一阶段归档：[20260504T122329Z-virtual-judge-npc-beta-readiness-stage-closure.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/虚拟裁判/20260504T122329Z-virtual-judge-npc-beta-readiness-stage-closure.md)
完成快照：[completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md) B51
后置待办：[todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md) C47

---

## 1. 计划定位

本计划承接虚拟裁判 NPC Beta Readiness / Productization 阶段收口后的下一阶段。

上一阶段已经完成：

1. `npc_service` 生产默认输入切到 Kafka/event-bus consumer，local webhook 仅作为本地调试入口。
2. 观战用户可通过 Debate Room WS 实时 / replay 看到 NPC action，并保持只读权限。
3. Ops 控制面支持 NPC 房间开关、风格、能力位和人工接管。
4. 用户公开呼叫、近期行为和私有反馈已进入 `chat` 事实源。
5. `llm_executor_v1` 主路径具备 canary、成本 / 延迟 metrics、熔断、`no_action` 和 `rule_executor_v1` fallback。
6. 前端 NPC 动态形象、动作强度、低动效和移动端体验已完成首版。
7. 暂停 / 恢复强动作已完成状态机设计门禁，结论是先做 `pause_suggestion`，不直接做强暂停。
8. 仓内运行态 smoke 与观测基线已建立，但不宣称真实 OpenAI / Kafka 部署 / dashboard 聚合已通过。

下一阶段目标不是继续扩 MVP 外围功能，而是收敛两个真实剩余问题：

1. **真实 Beta / staging 验证**：把仓内证据推进到真实 canary、Kafka topic、dashboard 查询和故障演练证据。
2. **`pause_suggestion` 最小闭环**：让 NPC 可以公开建议暂停评估，但不改变房间状态、不禁用输入、不冻结倒计时。

## 2. 当前代码事实快照

| 领域 | 当前事实 | 下一阶段影响 |
| --- | --- | --- |
| action 类型 | `chat` 已接受 `speak/praise/effect/state_changed/pause_suggestion`，见 [npc.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/debate/npc.rs) 的 `normalize_action_type` | 下一阶段由 `npc_service` 生成合法 `pause_suggestion` 候选，`chat` 不把它映射为房间暂停态 |
| pause 能力位 | `DebateNpcRoomConfig.allow_pause` 已映射到 `pause_suggestion` candidate，并接入 `pause_review` public call 门禁 | `allow_pause=true` 仅授权暂停建议，不授权 `soft_pause/hard_pause/resume` |
| 公开呼叫 | `pause_review` 已是合法 public call type；`chat` 门禁允许只开启 `allow_pause` 的房间创建该公开呼叫 | 下一阶段让 `npc_service` 把 `pause_review` 与 `pause_suggestion` 最小闭环对齐 |
| `npc_service` action schema | [models.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/models.py) 的 `NpcActionType` 已支持 `pause_suggestion` | 下一阶段重点同步前端 action union 和端到端 smoke |
| 前端 action union | [debate-domain](/Users/panyihang/Documents/EchoIsle/frontend/packages/debate-domain/src/index.ts)、[realtime-sdk](/Users/panyihang/Documents/EchoIsle/frontend/packages/realtime-sdk/src/index.ts)、[DebateNpcModel.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/components/DebateNpcModel.ts) 仍只识别四类 action | 需要新增 suggestion 类型的文案、样式、replay hydration 与 smoke |
| 实时与 replay | `DebateNpcActionCreated` 已有 replay key `npc_action:<action_uid>`，观战 WS 测试已覆盖 | `pause_suggestion` 默认复用现有 NPC action 事件，不新增房间状态事件 |
| 观测 | `npc_service` runtime metrics、`chat` candidate handler 日志、notify WS metrics 和 P3-I evidence 已存在 | 下一阶段重点补真实 dashboard 查询 / 告警演练，而不是再堆本地 mock 证据 |
| 正式裁决隔离 | `chat` candidate guard 已拒绝官方裁决字段；PRD 明确 NPC 永不替代 AI 裁判团报告 | `pause_suggestion` 文案和 payload 也必须继续禁止胜负判断、评分、裁决字段 |

## 3. 冻结边界

本阶段继续遵守以下不可突破边界：

1. 虚拟裁判 NPC 永远不替代 AI 裁判团生成正式裁决报告。
2. 虚拟裁判 NPC 永远不作为最终胜负官方判定来源。
3. 用户不能私聊虚拟裁判 NPC。
4. NPC 不代替用户发言，不自动参赛，不站队。
5. NPC 不写 `verdict_ledger`、`judge_trace`、review queue 或正式裁决字段。
6. NPC 赞赏或暂停建议不构成官方评分、阵营优势或正式裁决依据。
7. `llm_executor_v1` 是体验主路径；`rule_executor_v1` 只作为 LLM 未配置、不可用、熔断或输出违规时的 fallback。
8. `chat` 继续作为房间事实源；`npc_service` 只生成候选动作；`notify_server` 只广播 `chat` 已确认事件。
9. `pause_suggestion` 不改变房间状态；本阶段不实现 `soft_pause/hard_pause/resume`。
10. 不恢复旧 `NPC Coach` / `Room QA` 作为虚拟裁判 NPC 主链路。
11. 不把本地 mock Web smoke、rule-only fallback 或未接真实 provider 的证据宣称为真实环境通过。

## 4. 阶段目标

### 4.1 产品目标

1. 让运营能判断虚拟裁判 NPC 是否具备进入 Beta / staging canary 的证据条件。
2. 让 NPC 的“暂停能力”先以公开建议的形式出现，符合 PRD 中“可解释、公开、娱乐导向、不中断主流程”的体验原则。
3. 让用户看到暂停建议时清楚知道：这是 NPC 现场建议，不是官方裁决，不是已经暂停。
4. 让 `pause_review` 公开呼叫有更自然的闭环，而不是只收到普通提示。

### 4.2 工程目标

1. 固化真实环境 canary 输入、执行步骤、观测字段、失败判定和回滚动作。
2. 补齐 dashboard / 日志查询基线，让 fallback、callback 拒绝、DLQ、熔断、成本和延迟可被追踪。
3. 将 `pause_suggestion` 作为低风险 action type 贯通 `chat`、`npc_service`、`notify_server` replay、前端模型和 smoke。
4. 保持 `pause_suggestion` 与强暂停状态机解耦，为未来 `soft_pause` 审批态留下清晰边界。

## 5. 执行矩阵

### 已完成/未完成矩阵

| 模块 | 目标 | 状态 | 说明 |
| --- | --- | --- | --- |
| P0-A. `virtual-judge-npc-next-stage-plan-current-state` | 基于 PRD、module_design 和当前代码事实生成下一阶段计划 | 已完成 | 本文档即该模块输出，已绑定 default slot |
| P1-B. `virtual-judge-npc-real-env-readiness-pack` | 生成真实 Beta / staging canary 输入清单、运行步骤、回滚和 evidence 模板 | 已完成 | 已输出真实环境 readiness 输入清单；不包含真实 secret，不宣称真实环境已通过 |
| P1-C. `virtual-judge-npc-dashboard-query-pack` | 固化 NPC canary dashboard / 日志查询 / 告警演练基线 | 已完成 | 已输出查询与告警基线；不把字段存在误写成 dashboard 已接入 |
| P1-D. `virtual-judge-npc-real-env-canary-run` | 在真实环境执行 NPC canary 并归档证据 | 待执行 | 条件模块；仅在 Beta / staging provider、Kafka、服务编排、dashboard 可用时执行；否则输出 env_blocked |
| P2-E. `virtual-judge-npc-pause-suggestion-contract-freeze` | 冻结 `pause_suggestion` 合同、文案、权限、展示和非目标 | 已完成 | 已冻结产品与技术合同；默认复用 `DebateNpcActionCreated`，不新增房间状态事件 |
| P2-F. `virtual-judge-npc-pause-suggestion-chat-spine` | `chat` 支持 `pause_suggestion` candidate、能力位、OpenAPI 和测试 | 已完成 | 已新增 DB check 迁移、chat guard、public call 门禁和 targeted tests；`allow_pause` 只控制建议，不允许强暂停 |
| P2-G. `virtual-judge-npc-pause-suggestion-npc-service-executor` | `npc_service` LLM / rule / guard 支持生成暂停建议 | 已完成 | 已支持 LLM 合法建议、强暂停 guard 隔离、rule fallback 建议、`allow_pause=false` 降级和 targeted tests |
| P2-H. `virtual-judge-npc-pause-suggestion-frontend-ux` | 前端展示暂停建议卡片、action feed、replay hydration 与反馈 | 已完成 | 已完成前端 union、parser、NPC feed / panel、replay hydration 测试和 targeted smoke |
| P3-I. `virtual-judge-npc-pause-suggestion-smoke-and-guard` | 完成 pause suggestion 端到端 smoke、负向边界和正式裁决隔离验证 | 待执行 | 覆盖观战 replay、allow_pause=false、LLM 违规输出隔离 |
| P4-J. `virtual-judge-npc-real-env-pause-stage-closure` | 阶段收口，回写 completed/todo 并归档计划 | 待执行 | 只在主体切片完成后执行 |

## 6. 下一开发模块建议

1. 默认下一步执行 P3-I `virtual-judge-npc-pause-suggestion-smoke-and-guard`，补齐跨层 smoke、负向边界和正式裁决隔离验证。
2. P3-I 完成后执行 P4-J `virtual-judge-npc-real-env-pause-stage-closure`。
3. P1-D 必须等真实 Beta / staging 环境具备后再执行；没有环境时只允许产出 `env_blocked`，不得写成 pass。

## 7. 模块详情

### P0-A. `virtual-judge-npc-next-stage-plan-current-state`

目标：

1. 结合 PRD、系统设计、暂停状态机设计、运行态 smoke 基线、B51 完成快照和 C47 后置债，生成下一阶段开发计划。
2. 明确本阶段聚焦真实 canary/dashboard 与 `pause_suggestion`，而不是继续扩展泛化 NPC 能力。
3. 用户确认执行后，将 default slot 绑定到本主线并同步 [当前开发计划.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md)。

验收标准：

1. 本文档包含执行矩阵、下一模块建议、每个切片 DoD、验证策略和冻结边界。
2. 文档明确 `pause_suggestion` 不改变房间状态。
3. 文档明确真实环境证据不能由本地 mock 替代。

### P1-B. `virtual-judge-npc-real-env-readiness-pack`

目标：

1. 明确真实 Beta / staging canary 需要哪些输入和前置条件。
2. 输出 canary 执行清单、回滚动作和 evidence 模板。
3. 不提交任何真实密钥、真实用户隐私或不可公开环境信息。

执行范围：

1. `docs/module_design/虚拟裁判NPC` 真实环境 readiness 文档。
2. `npc_service` canary env 字段核对。
3. Kafka/event-bus topic 与 consumer group 核对清单。
4. chat/notify/frontend/npc_service 服务启动顺序与 healthcheck 清单。

建议步骤：

1. 基于 [虚拟裁判NPC_LLM_Canary运行手册.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_LLM_Canary运行手册.md) 列出真实 canary 必填输入。
2. 明确 `NPC_OPENAI_API_KEY`、`NPC_SERVICE_LLM_CANARY_SESSION_IDS`、成本上限、Kafka brokers、topic、group id、chat callback base URL 等字段。
3. 定义 canary 房间选择规则：测试房间、低风险真实场次、明确退出机制。
4. 定义回滚：关闭 `NPC_SERVICE_LLM_CANARY_ENABLED`、清空 canary session、关闭房间 NPC config、恢复 rule fallback。
5. 输出 `pass / env_blocked / fail` 三态判定口径。

验收标准：

1. 有一份可直接带入 Beta / staging 的 readiness 输入模板。
2. 模板不包含真实 secret。
3. 能说明真实环境缺哪个输入时应输出 `env_blocked`。
4. 回滚动作可由运营或工程按步骤执行。

完成结果：

1. 已新增 [虚拟裁判NPC_Beta真实环境Readiness输入清单.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_Beta真实环境Readiness输入清单.md)。
2. 文档覆盖环境窗口、`npc_service` env、LLM provider、Kafka/event-bus、chat / notify / frontend、观测证据、preflight、canary 步骤、判定口径、回滚步骤和 evidence 模板。
3. 明确 `pass / env_blocked / fail / rollback_required` 四态口径，不把本地 mock 或 rule-only smoke 作为真实环境通过。
4. 未提交真实 secret、真实用户隐私或不可公开环境信息。

### P1-C. `virtual-judge-npc-dashboard-query-pack`

目标：

1. 将 P3-I 已有观测字段整理成 dashboard / 日志查询包。
2. 确保真实 canary 时能回答“为什么 fallback / 为什么拒绝 / 哪个 callback 失败 / 是否熔断 / 成本多少”。

执行范围：

1. `npc_service` `/healthz` 与 `/api/internal/npc/runtime/metrics` 查询说明。
2. `chat` candidate handler 结构化日志字段。
3. notify WS live/replay/lag/send_failed 指标。
4. Kafka consumer offset、retry、DLQ 文件或平台查询。

建议步骤：

1. 建立指标字典：decision status、executor、fallback reason、provider error、latency、tokens、cost、circuit、DLQ、callback status。
2. 为每个指标标注来源层、查询入口、告警建议和排障动作。
3. 如果当前只能通过日志查询而不是 dashboard 查看，明确 dashboard 接入前的临时证据口径。
4. 补充一次故障演练脚本或手工步骤：LLM rate limit、provider unavailable、chat candidate rejected、npc_service stop。

验收标准：

1. canary 执行者能按文档查到每个关键字段。
2. fallback、rejected、replayed、failed、DLQ、circuit open 均有查询方式。
3. 不把“字段存在”误写成“dashboard 已接入”，除非确有导出或截图证据。

完成结果：

1. 已新增 [虚拟裁判NPC_CanaryDashboard查询与告警基线.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_CanaryDashboard查询与告警基线.md)。
2. 文档覆盖 `npc_service` `/healthz`、runtime metrics、decision run、chat candidate 日志、`debate_npc_actions` SQL、`event_outbox` SQL、Kafka consumer group、`npc_service` DLQ、chat `kafka_dlq_events`、`notify_runtime_signals`、Debate Room WS 和前端 live / replay trace。
3. 文档明确 dashboard 未接入时的临时证据口径；若 HTTP、日志、SQL、Kafka、DLQ 或前端 trace 任一入口缺失，P1-D 不得判定 `pass`。
4. 文档补充 P0/P1/P2 告警分级，以及 provider unavailable、canary session not allowed、circuit open、cost exceeded、candidate rejected、forbidden official field、callback failure、notify replay gap 等故障演练清单。

### P1-D. `virtual-judge-npc-real-env-canary-run`

目标：

1. 在真实 Beta / staging 环境执行虚拟裁判 NPC canary。
2. 形成真实 provider、真实 Kafka、真实服务编排和 dashboard / 日志证据。

执行范围：

1. Beta / staging 环境配置。
2. 指定 canary session。
3. chat/notify/frontend/npc_service 联动 smoke。
4. canary evidence 文档。

建议步骤：

1. 完成 P1-B readiness 输入填写。
2. 启动真实环境服务并确认 health。
3. 指定 canary session 开启真实 LLM。
4. 参赛用户发送公开发言，确认 NPC action 可见。
5. 观战用户进入，确认实时可见和 replay。
6. 模拟 LLM 失败或关闭 canary，确认 rule fallback / 静默和主链不阻塞。
7. 归档 provider 响应、成本/延迟、Kafka offset、callback 结果、dashboard 查询证据。

验收标准：

1. 真实环境 canary 通过，或明确输出 `env_blocked` / `fail`。
2. 不能用本地 mock smoke 替代真实环境 pass。
3. `npc_service` 停止不影响用户发言、置顶、Judge / Draw。
4. 正式 AI 裁判团链路与 NPC 链路仍清晰隔离。

### P2-E. `virtual-judge-npc-pause-suggestion-contract-freeze`

目标：

1. 冻结 `pause_suggestion` 的产品合同和技术合同。
2. 明确它是公开建议，不是暂停事实。

建议合同：

1. `actionType = pause_suggestion`
2. 通过 `DebateNpcActionCreated` 进入现有 NPC action feed。
3. 必须有 `publicText` 和 `reasonCode`。
4. `npcStatus` 可使用 `speaking` 或后续新增轻量状态，但首版不要求新增全局房间状态。
5. `allow_pause=false` 时，`chat` 必须拒绝或静默该候选。
6. `llm_executor_v1` 不能输出 `soft_pause`、`hard_pause`、`resume`、`pause_debate`、`resume_debate`。

验收标准：

1. 合同文档明确前后端字段、文案、权限、replay 和非目标。
2. 产品文案明确“建议暂停评估”，不说“已暂停”。
3. 合同不引入房间倒计时冻结、输入禁用或状态遮罩。

完成结果：

1. 已新增 [虚拟裁判NPC_pause_suggestion合同冻结.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_pause_suggestion合同冻结.md)。
2. 合同冻结 `actionType = pause_suggestion`，要求 `publicText` 和 `reasonCode`，并明确首版不新增 `requiresApproval/pauseId/pauseState/pauseVersion/expiresAt/approvalRequestId`。
3. 合同明确 `pause_suggestion` 复用 `DebateNpcActionCreated` 与 replay key `npc_action:<action_uid>`，不新增房间暂停状态事件，不写暂停 projection，不改变 `debate_sessions.status`。
4. 合同明确 `allowPause=true` 只允许提交暂停建议，不允许 LLM 或 NPC 执行 `soft_pause/hard_pause/resume`。
5. 合同明确前端只展示建议卡片，不显示暂停横幅，不禁用输入，不冻结倒计时。
6. 合同列出 P2-F/P2-G/P2-H 跨层改动清单与负向测试边界。

### P2-F. `virtual-judge-npc-pause-suggestion-chat-spine`

目标：

1. 让 `chat` 接收、校验、落库和广播 `pause_suggestion`。
2. 保持 `chat` 二次 guard 是最终边界。

执行范围：

1. `chat/chat_server/src/models/debate/npc.rs`
2. `chat/chat_server/src/models/debate.rs`
3. `chat/chat_server/src/openapi.rs`
4. NPC action targeted tests。

建议步骤：

1. 将 `pause_suggestion` 加入 action type normalizer。
2. 将 `pause_suggestion` 映射到 `allow_pause` capability。
3. 要求 `publicText` 必填，限制字段长度和 forbidden official fields。
4. 保持 rate limit、action_uid 幂等和 target/source message 校验。
5. OpenAPI schema 同步。
6. 补测试：`allow_pause=false` 拒绝、`allow_pause=true` 接收、重复 action_uid replay、官方裁决字段拒绝、不会写房间暂停状态。

验收标准：

1. `pause_suggestion` 可作为普通 NPC action 落库并产生 `DebateNpcActionCreated`。
2. `allow_pause=false` 时不能绕过。
3. 不新增 `soft_paused/hard_paused` 房间状态。
4. 正式发言、置顶、Judge / Draw 不受影响。

完成结果：

1. `chat` 已将 `pause_suggestion` 加入 action type normalizer，并要求 `publicText` 与 `reasonCode`。
2. `pause_suggestion` 已映射到 `DebateNpcRoomConfig.allow_pause`；`allow_pause=false` 时 candidate 会在 chat 边界被拒绝。
3. 已新增 `debate_npc_actions` DB check 迁移，允许 `pause_suggestion` 落库。
4. `pause_review` public call 门禁已支持只开启 `allow_pause` 的房间，但仍不改变房间状态。
5. OpenAPI schema 已检查：当前 candidate DTO 的 `actionType` 是字符串 schema，没有手写 enum 需要同步；路由与 DTO 仍由现有 schema 自动导出。
6. 已补 targeted tests 覆盖创建、action_uid replay、能力位拒绝、缺少 reason 拒绝、官方裁决字段拒绝、公开呼叫门禁和 `debate_sessions.status` 不变。
7. 本切片没有新增 `soft_pause/hard_pause/resume`，也没有写入正式裁决字段。

### P2-G. `virtual-judge-npc-pause-suggestion-npc-service-executor`

目标：

1. 让 `npc_service` 能在公开呼叫或房间节奏异常时生成 `pause_suggestion` 候选。
2. 继续让 LLM 只生成候选，不直接写房间事实。

执行范围：

1. `npc_service/app/models.py`
2. `npc_service/app/executors.py`
3. `npc_service/app/guard.py`
4. `npc_service/tests`

建议步骤：

1. 将 `pause_suggestion` 加入 `NpcActionType`。
2. 更新 LLM tool / prompt policy，允许 `pause_suggestion`，禁止 `soft_pause/hard_pause/resume`。
3. `pause_review` public call 在 `allow_pause=true` 时可产生 `pause_suggestion`，否则返回普通提醒或静默。
4. `rule_executor_v1` 只在明确公开呼叫或强规则原因时低频生成建议。
5. metrics / decisionRun 保留 reasonCode、fallbackReason、guardReason。
6. 补测试：LLM 合法建议、LLM 强动作违规隔离、rule fallback 建议、allow_pause=false 静默或被 chat 拒绝。

验收标准：

1. `llm_executor_v1` 可以生成合法 `pause_suggestion`。
2. LLM 输出强暂停 / 恢复字段会被 guard 拒绝或 fallback。
3. `rule_executor_v1` 只作为 fallback，不抢主路径。
4. `npc_service` 不直接调用任何暂停状态 API。

完成结果：

1. `npc_service` 已将 `pause_suggestion` 加入 `NpcActionType` 与 guard allowed action。
2. `llm_executor_v1` 通过 OpenAI-compatible prompt 明确允许 `pause_suggestion`，并禁止 `soft_pause/hard_pause/resume/pause_debate/resume_debate`。
3. guard 已拒绝强暂停动作、官方裁决字段、缺少 `reasonCode`、`allowPause=false`、`targetMessageId/targetUserId/targetSide` 和 `effectKind` 等不符合暂停建议合同的输出。
4. `rule_executor_v1` 在 `pause_review + allowPause=true` 时生成 `pause_suggestion`；`allowPause=false` 时降级为普通公开提醒，若公开提醒能力也关闭则静默。
5. 事件控制面门禁已允许只开启 `allowPause` 的房间进入 router，由后续 executor 生成暂停建议候选。
6. 已补 targeted tests 覆盖 LLM 合法暂停建议、强暂停违规 fallback、rule fallback 暂停建议、`allowPause=false` 降级、public call 门禁和 prompt policy。
7. 本切片没有新增任何暂停状态 API，也没有直接调用 chat 暂停状态机或写正式裁决字段。

### P2-H. `virtual-judge-npc-pause-suggestion-frontend-ux`

目标：

1. 让用户和观战者能清楚看到暂停建议。
2. 不让用户误以为房间已暂停。

执行范围：

1. `frontend/packages/debate-domain/src/index.ts`
2. `frontend/packages/realtime-sdk/src/index.ts`
3. `frontend/packages/app-shell/src/components/DebateNpcModel.ts`
4. `frontend/packages/app-shell/src/components/DebateNpcPanel.tsx`
5. `frontend/tests/e2e/auth-smoke.spec.ts`

建议步骤：

1. 扩展 action union 和 runtime parser。
2. `pause_suggestion` 在 feed 中展示为“Pause suggestion / 建议暂停评估”。
3. NPC 面板可展示建议卡片，但不显示全局暂停横幅。
4. 输入框、发言按钮、置顶、Judge / Draw 不因 suggestion 禁用。
5. 观战 replay hydration 能恢复建议卡片。
6. 反馈按钮继续可用于该 action。

验收标准：

1. 参赛用户和观战用户都能看到 `pause_suggestion`。
2. 页面文案不出现“已暂停”或强暂停暗示。
3. 用户仍能继续发言。
4. 移动端布局不遮挡输入区和倒计时。

完成结果：

1. `frontend/packages/debate-domain` 和 `frontend/packages/realtime-sdk` 已将 `pause_suggestion` 纳入可见 action union 与 runtime parser。
2. `DebateNpcModel` 已将 `pause_suggestion` 归一为公开发言态，并支持 replay history hydration。
3. `DebateNpcPanel` 已展示 `Pause suggestion` feed 卡片、建议态样式和反馈按钮；未新增全局暂停遮罩、未显示“已暂停”、未改变正式裁决展示。
4. `auth-smoke` mock 已覆盖历史建议卡片，并断言发言输入、Send、Pin 60s 和 Request AI Judge 不因建议态禁用。
5. 已运行 domain / realtime / app-shell targeted tests、相关包 typecheck、targeted Playwright smoke 和 `git diff --check`。

### P3-I. `virtual-judge-npc-pause-suggestion-smoke-and-guard`

目标：

1. 建立 `pause_suggestion` 的端到端 smoke。
2. 验证负向边界和正式裁决隔离。

建议验证：

1. `cargo test -p chat-server npc_action`
2. `cargo test -p notify-server debate_npc_action`
3. `npc_service` targeted pytest：pause suggestion / forbidden strong action / fallback。
4. 前端 domain / app-shell tests。
5. Playwright targeted smoke：公开呼叫 Pause -> NPC 建议卡片 -> 用户仍可发言 -> 观战 replay 可见。
6. `pnpm --dir frontend e2e:smoke:web`
7. `git diff --check`

验收标准：

1. `pause_suggestion` 从 public call 到 action feed 的闭环可复现。
2. `allow_pause=false` 时闭环被阻断。
3. `soft_pause/hard_pause/resume` 不被 LLM 或 API 绕过。
4. NPC 不可用或被拒绝时不影响房间主链。
5. 证据文档记录本地 smoke 和真实环境状态，不混淆 pass 口径。

### P4-J. `virtual-judge-npc-real-env-pause-stage-closure`

目标：

1. 汇总本阶段主体成果。
2. 回写 [completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md)。
3. 将明确延后项写入 [todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md)。
4. 归档本开发计划。

验收标准：

1. completed/todo 只记录结构化完成快照和延后技术债，不复制活动计划全文。
2. 真实环境 canary / dashboard / pause suggestion 的完成状态清晰。
3. harness docs lint 通过。

## 8. 验证总策略

本阶段按风险分层验证：

1. `chat` 改动：优先覆盖 action type、`allow_pause` capability、幂等、限频、forbidden official fields、不会写暂停状态。
2. `npc_service` 改动：优先覆盖 LLM 合法建议、强动作违规隔离、rule fallback、public call `pause_review`、chat callback。
3. `notify_server` 改动：优先确认 `DebateNpcActionCreated` replay key、观战可见和内部字段剥离不回归。
4. 前端改动：优先覆盖 action parser、NPC feed、建议卡片、观战态、移动端不遮挡和用户继续发言。
5. 真实环境：只在 Beta / staging 输入齐备时执行；缺环境时必须输出 `env_blocked`。
6. 文档同步：如果代码结构、主入口或第一跳定位变化，检查 [docs/architecture/README.md](/Users/panyihang/Documents/EchoIsle/docs/architecture/README.md) 是否需要更新。

## 9. 当前待决问题

1. 真实 Beta / staging 环境是否已经具备 OpenAI-compatible provider、Kafka topic、服务编排和查询权限；若不具备，P1-D 应输出 `env_blocked`。
2. 是否需要在后续单独补 Grafana / Datadog / Loki / Kibana / CloudWatch 可导入面板模板；P1-C 当前只冻结字段与查询口径。
3. P2-F 已完成；OpenAPI 字符串 schema 已检查，chat targeted tests 已覆盖。
4. `pause_suggestion` 前端已按 P2-E 默认只展示 `publicText`，不向用户展示 reasonCode。
5. `soft_pause` 是否必须由运营 / 管理员批准。当前设计建议是必须批准，本阶段不实现。

## 10. 同步历史

### 模块完成同步历史

- 2026-05-04：虚拟裁判 NPC Beta Readiness / Productization 阶段已完成 P4-J 收口；完成快照写入 [completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md) B51，后置债收敛到 [todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md) C47。
- 2026-05-04：基于 PRD、module_design 和当前代码事实生成下一阶段 `virtual-judge-npc-real-env-and-pause-suggestion` 开发计划；P0-A 已完成，下一步建议执行 P1-B 或 P2-E。
- 2026-05-04：用户确认开始执行本计划；default slot 已绑定本主线。
- 2026-05-04：完成 P1-B `virtual-judge-npc-real-env-readiness-pack`，新增真实 Beta / staging readiness 输入清单、执行步骤、回滚和 evidence 模板；下一步默认推进 P1-C。
- 2026-05-04：完成 P1-C `virtual-judge-npc-dashboard-query-pack`，新增 canary dashboard / 日志查询 / 告警演练基线；下一步按真实环境可用性选择 P1-D 或 P2-E。
- 2026-05-04：完成 P2-E `virtual-judge-npc-pause-suggestion-contract-freeze`，新增 `pause_suggestion` 产品与技术合同冻结文档；下一步默认推进 P2-F。
- 2026-05-04：完成 P2-F `virtual-judge-npc-pause-suggestion-chat-spine`，`chat` 支持 `pause_suggestion` candidate、`allow_pause` 能力位、DB check 迁移和 targeted tests；下一步默认推进 P2-G。
- 2026-05-04：完成 P2-G `virtual-judge-npc-pause-suggestion-npc-service-executor`，`npc_service` 支持 LLM / rule 生成暂停建议，并在 guard 层隔离强暂停动作；下一步默认推进 P2-H。
- 2026-05-04：完成 P2-H `virtual-judge-npc-pause-suggestion-frontend-ux`，前端支持暂停建议卡片、replay hydration、反馈和 targeted smoke；下一步默认推进 P3-I。

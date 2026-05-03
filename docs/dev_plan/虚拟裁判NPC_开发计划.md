# 虚拟裁判 NPC 开发计划

更新时间：2026-05-03  
文档状态：active 计划草案  
关联 PRD：[虚拟裁判NPC完整PRD.md](/Users/panyihang/Documents/EchoIsle/docs/PRD/虚拟裁判NPC完整PRD.md)  
关联设计：[虚拟裁判NPC_系统设计.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_系统设计.md)  
关联探索：[虚拟裁判NPC_MVP切片与技术探索.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_MVP切片与技术探索.md)  
当前主线：`virtual-judge-npc-llm-agent-loop-mvp`

---

## 1. 计划定位

本计划把已经定档的虚拟裁判 NPC PRD、MVP 切片与系统设计拆成可执行开发任务。

冻结决策：

1. 架构采用方案 C：新增独立 `npc_service/`。
2. 虚拟裁判 NPC 的主执行路径是 `llm_executor_v1`。
3. `rule_executor_v1` 只作为 LLM 不可用、熔断或本地未配置 provider 时的 fallback。
4. `chat` 是房间事实源，负责校验、落库、幂等、限频与广播。
5. `notify_server` 只推送 `chat` 已确认的 `DebateNpcActionCreated`。
6. 前端只消费稳定房间事件，不关心候选动作来自 LLM 还是 rule fallback。
7. 虚拟裁判 NPC 永远不替代 AI 裁判团生成正式裁决报告，不提供用户私聊。

本计划不做：

1. 不恢复旧 `NPC Coach` / `Room QA`。
2. 不开发用户辩论助手。
3. 不做暂停 / 恢复辩论状态机。
4. 不让 NPC 写入 `verdict_ledger`、`judge_trace`、review queue 或正式裁决字段。
5. 不把 rule executor 作为最终体验主路线。

## 2. 当前代码事实快照

| 领域 | 当前事实 | 计划影响 |
| --- | --- | --- |
| Debate Room 前端 | [DebateRoomPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/DebateRoomPage.tsx) 是当前房间主入口，已有消息、置顶、Judge / Draw、WS 重连等逻辑 | 需要新增 NPC 展示壳、action feed、动效层和 reducer，避免继续撑大页面 |
| 前端实时协议 | [realtime-sdk/src/index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/realtime-sdk/src/index.ts) 使用通用 `roomEvent` 承载 `eventName + payload` | 可新增 `DebateNpcActionCreated` payload 类型，不需要重做 WS 协议 |
| notify WS | [ws.rs](/Users/panyihang/Documents/EchoIsle/chat/notify_server/src/ws.rs) 支持 `lastAckSeq`、replay、ack、syncRequired | NPC action 必须进入可 replay 房间事件，断线重连不能丢失或重复 |
| notify event mapping | [notif.rs](/Users/panyihang/Documents/EchoIsle/chat/notify_server/src/notif.rs) 的 `AppEvent` 决定 debate event 识别、session id 与 dedupe key | 需要新增 `DebateNpcActionCreated` 映射和 dedupe 规则 |
| 用户发言主链路 | [debate_room.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_room.rs) 与 [message_pin.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/debate/message_pin.rs) 承载发言、置顶、消息落库 | NPC 决策必须异步，不能阻塞用户发言事务 |
| DomainEvent | [event_bus.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/event_bus.rs) 已有 `DebateMessageCreated` / `DebateMessagePinned`，P1-A 已新增 `DebateNpcActionCreated` 事件骨架，P1-B 已接入 notify replay 合同 | P2-E 再把 `DebateMessageCreated` 作为 NPC 首个触发输入 |
| AI advisory 历史资产 | 当前 `npc_coach` / `room_qa` 是用户辅助咨询，不是公开房间 NPC | 只复用安全隔离思想，不作为本模块开发入口 |

## 3. 完成度与执行矩阵

| 模块 | 目标 | 状态 | 说明 |
| --- | --- | --- | --- |
| P0-A. `virtual-judge-npc-planning-current-state` | 生成开发计划并切换 active 主线 | 已完成 | 本文档与 [当前开发计划.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md) 完成同步后即完成 |
| P1-A. `virtual-judge-npc-chat-action-spine` | 建立 chat 侧 NPC action 数据模型、内部 API 与 guard | 已完成 | 已新增 action/config 表、内部 candidate 接收接口、guard、限频、幂等重放、outbox 事件与 targeted tests |
| P1-B. `virtual-judge-npc-notify-replay-contract` | 打通 `DebateNpcActionCreated` outbox、notify WS、replay 和 dedupe | 已完成 | 已新增 notify Kafka topic / AppEvent 映射、稳定 dedupe key、前端 payload 类型与可见字段 guard |
| P1-C. `virtual-judge-npc-frontend-shell` | 前端新增 NPC 动态展示壳、action feed 与轻量动效 | 待执行 | 先用 mock / fixture 事件驱动 UI，不等待 LLM |
| P2-D. `virtual-judge-npc-service-skeleton-executor-router` | 新增 `npc_service/`、LLM provider adapter、executor router、rule fallback | 待执行 | `llm_executor_v1` 为主路径，rule 只兜底 |
| P2-E. `virtual-judge-npc-event-consumption-loop` | 消费 `DebateMessageCreated`，拉取 context，提交 candidate | 待执行 | 从用户发言到 NPC action 的服务间闭环 |
| P3-F. `virtual-judge-npc-e2e-smoke-and-fallback-hardening` | 端到端 smoke、LLM fallback、限频、幂等、隔离验证 | 待执行 | 证明 NPC 不影响发言、置顶、Judge / Draw |
| P4-G. `virtual-judge-npc-stage-closure` | 阶段收口与长期文档同步 | 待执行 | 根据实际完成情况写 completed/todo，不复制活动计划原文 |

## 4. 开发切片详情

### P0-A. `virtual-judge-npc-planning-current-state`

目标：

1. 将虚拟裁判 NPC 定档设计转换成可执行开发计划。
2. 将 default active 计划从空档切换到本模块。
3. 明确旧 `NPC Coach` / `Room QA` 不参与本模块。

执行范围：

1. [虚拟裁判NPC_开发计划.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/虚拟裁判NPC_开发计划.md)
2. [当前开发计划.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md)

验收标准：

1. active plan 明确当前主线为 `virtual-judge-npc-llm-agent-loop-mvp`。
2. 计划包含执行矩阵、每个切片 DoD、验证策略和暂不执行范围。
3. 文档不暗示 rule executor 是最终主路径。

### P1-A. `virtual-judge-npc-chat-action-spine`

目标：

1. 在 `chat` 侧建立 NPC action 的事实源。
2. 提供内部 candidate 接收接口。
3. 建立 guard、幂等、限频、能力开关的最小主链。

执行范围：

1. `chat/chat_server/src/event_bus.rs`
2. `chat/chat_server/src/handlers/*` 中内部 NPC API 路由位置
3. `chat/chat_server/src/models/debate/*` 或新的 NPC domain/model 文件
4. `chat/chat_server` migration
5. 必要的 OpenAPI / 内部 API 合同说明

建议步骤：

1. 新增 `debate_npc_room_configs` 与 `debate_npc_actions` 表。
2. 新增 `NpcActionCandidate`、`NpcAction`、`NpcRoomConfig` 类型。
3. 新增内部接口 `POST /internal/debate/npc/actions/candidates`。
4. 接口必须校验内部服务鉴权、session、NPC enabled、target message 同场、action schema、forbidden official fields。
5. 生成稳定 `action_uid` 并建立唯一索引。
6. 候选 action 通过后写入 `debate_npc_actions`，并 enqueue `DomainEvent::DebateNpcActionCreated`。

验收标准：

1. mock candidate 可落库并返回 `created`。
2. 重复 `action_uid` 返回 `replayed`。
3. target message 不属于 session 时拒绝。
4. NPC disabled 时拒绝。
5. 正式裁决字段被拒绝。
6. 用户发言主链路不等待 NPC 决策。

建议验证：

1. `cargo test -p chat-server` 的 NPC targeted tests。
2. 若只新增内部 handler/model，可先跑精确测试名。
3. 若新增 migration，补 sqlx / migration 运行证据。

### P1-B. `virtual-judge-npc-notify-replay-contract`

目标：

1. 将 `DebateNpcActionCreated` 纳入房间实时事件。
2. 支持 notify WS 推送、replay、ack 与 dedupe。
3. 确保前端断线重连后 NPC action 不丢、不重复。

执行范围：

1. `chat/chat_server/src/event_bus.rs`
2. `chat/notify_server/src/notif.rs`
3. `chat/notify_server/src/ws.rs`
4. `frontend/packages/realtime-sdk/src/index.ts`
5. `frontend/packages/debate-domain/src/index.ts`

建议步骤：

1. 定义 `DebateNpcActionCreated` outbox payload。
2. 在 `AppEvent` 中识别该事件为 debate room event。
3. 提供稳定 `debate_session_id` 与 `debate_dedupe_key`。
4. 前端 SDK / domain 增加 payload 类型和必要 parser。
5. 用 mock outbox 或 handler 测试验证 replay。

验收标准：

1. mock NPC action 可通过 WS 被房间用户收到。
2. `lastAckSeq` replay 后 action 不丢失。
3. dedupe key 稳定。
4. 用户可见 payload 不包含 `policyVersion`、`executorVersion`、trace、正式裁决字段。

建议验证：

1. notify targeted tests。
2. realtime-sdk / debate-domain type tests。
3. 必要时跑现有 web smoke，确认房间 WS 未回归。

完成记录：

1. `DebateNpcActionCreated` 已加入 notify 默认 Kafka topic 与 debate room event 识别。
2. room replay dedupe key 固定为 `npc_action:{action_uid}`。
3. 前端 `realtime-sdk` 暴露 NPC room event/payload 类型，`debate-domain` 暴露可见 payload guard。
4. 用户可见 payload 测试覆盖 `policyVersion`、`executorVersion`、trace 与正式裁决字段不泄漏。
5. 已通过 notify targeted tests、前端 targeted tests/typecheck 与 `post-module-test-guard --mode full`。

### P1-C. `virtual-judge-npc-frontend-shell`

目标：

1. 在 Debate Room 内展示虚拟裁判 NPC。
2. 支持 `observing / speaking / praising / silent / unavailable` 等状态。
3. 根据 `DebateNpcActionCreated` 渲染 action feed、赞赏目标和轻量动效。

执行范围：

1. `frontend/packages/app-shell/src/pages/DebateRoomPage.tsx`
2. 新增 `DebateNpcPanel`
3. 新增 `DebateNpcVisual`
4. 新增 `DebateNpcActionFeed`
5. 新增 `DebateNpcEffectLayer`
6. 新增 `useDebateNpcState` 或房间 reducer

建议步骤：

1. 先做不依赖后端的 NPC 展示壳。
2. 用 fixture / mock room event 驱动 `praise`、`speak`、`effect`。
3. 从 `DebateRoomPage` 抽出轻量 reducer，避免页面继续膨胀。
4. 加入 reduced motion，确保动效不遮挡消息和输入。
5. 保持 NPC UI 与 Judge / Draw 视觉区分。

验收标准：

1. 房间首屏能看到虚拟裁判 NPC。
2. mock `praise` action 能显示目标发言与赞赏文本。
3. 特效不遮挡输入框和消息阅读。
4. 低动效模式可关闭或降级。
5. 不出现“正式裁决”“官方判决”类误导文案。

建议验证：

1. app-shell / debate-domain targeted tests。
2. Playwright 或现有 web smoke 截图检查。
3. 桌面端如共用 app-shell，需要同步跑 desktop smoke 或说明未跑原因。

### P2-D. `virtual-judge-npc-service-skeleton-executor-router`

目标：

1. 新增独立 `npc_service/`。
2. 建立 FastAPI app、healthz、settings、chat client。
3. 建立 LLM provider adapter、executor router、`llm_executor_v1` 与 `rule_executor_v1` fallback。
4. 记录 decision run、失败原因和 fallback 来源。

执行范围：

1. 新增 `npc_service/`
2. workspace / runtime 配置
3. `npc_service` settings、models、executors、guards、chat client、tests
4. 必要时同步 [docs/architecture/README.md](/Users/panyihang/Documents/EchoIsle/docs/architecture/README.md)

建议步骤：

1. 搭建服务骨架和 `/healthz`。
2. 定义 `NpcDecisionContext`、`NpcActionCandidate`、`NpcDecisionRun`。
3. 实现 `OpenAI-compatible` LLM provider adapter，具体真实模型可通过配置注入。
4. executor router 默认选择 `llm_executor_v1`。
5. LLM 未配置、超时、限流、输出违规时回退 `rule_executor_v1`。
6. `rule_executor_v1` 只覆盖低风险赞赏、轻量状态变化或静默。
7. 所有输出都必须通过本地 guard。

验收标准：

1. `npc_service` 可本地启动。
2. mock LLM 返回合法结构化 action 时，executor router 产出 candidate。
3. mock LLM 失败时，router 回退 rule 或静默。
4. guard 拒绝胜负预测、正式裁决字段、过长文本和违规内容。
5. 新增 `npc_service/` 后同步 architecture map。

建议验证：

1. Python 相关命令执行前遵守仓库 Python venv guard 规则。
2. `npc_service` unit tests：executor router、LLM fallback、guard、chat client mock。
3. `git diff --check`。

### P2-E. `virtual-judge-npc-event-consumption-loop`

目标：

1. 让 `npc_service` 接收 `DebateMessageCreated`。
2. 拉取 chat 提供的公开房间 context。
3. 经 executor router 生成 candidate。
4. 回调 chat 内部 action sink。

执行范围：

1. `npc_service` event consumer
2. `chat` 内部 context 查询接口
3. service auth / callback config
4. retry / DLQ / offset 记录

建议步骤：

1. 冻结第一版事件投递策略：优先对齐系统设计的 Kafka / event bus；若本地闭环需要 webhook，应写明它是临时开发路径和移除条件。
2. 新增 chat 内部 context 查询接口，只返回公开房间数据。
3. `npc_service` 收到消息事件后拉取 context。
4. executor router 生成 candidate 后回调 `chat`。
5. callback 失败进入重试，多次失败进入 DLQ。
6. `chat` 拒绝候选动作时记录 rejected，不无限重试同一 payload。

验收标准：

1. 本地从用户发言到 NPC action 落库可以跑通。
2. LLM 不可用时 fallback 不影响房间发言。
3. context 不包含手机号、邮箱、钱包余额、历史胜率、正式裁判团内部审计。
4. `npc_service` 停止时，用户发言、置顶、Judge / Draw 仍正常。

建议验证：

1. `npc_service` integration tests with mock chat。
2. chat internal context tests。
3. 本地 smoke：发言事件触发 NPC candidate。

### P3-F. `virtual-judge-npc-e2e-smoke-and-fallback-hardening`

目标：

1. 验证完整 MVP 闭环。
2. 验证 LLM fallback、限频、幂等、隔离和 UI 可见性。
3. 防止 NPC 功能污染正式裁决和用户辩论助手。

执行范围：

1. chat targeted tests
2. notify targeted tests
3. frontend web / desktop smoke
4. `npc_service` unit / integration tests
5. 必要的 local runtime smoke

建议步骤：

1. 启动 chat、notify、frontend、npc_service。
2. 创建或进入启用 NPC 的 Debate Room。
3. 用户发言，触发 NPC 低频赞赏或发言。
4. 断线重连，验证 NPC action replay。
5. 模拟 LLM 超时 / 输出违规，验证 rule fallback 或静默。
6. 模拟 `npc_service` 停止，验证房间主链路不受影响。
7. 验证 Judge / Draw 区块不受 NPC action 影响。

验收标准：

1. 启用 NPC 的房间中能看到动态 NPC 区域。
2. 用户发送公开发言后，NPC 服务优先通过 LLM 生成公开赞赏或发言候选动作。
3. `chat` 能校验、落库并广播 `DebateNpcActionCreated`。
4. 前端能展示 NPC action、更新 NPC 状态并触发轻量动效。
5. NPC action 可通过 WS replay 恢复。
6. LLM 不可用时回退 rule 或静默，不影响房间主链路。
7. NPC 不输出胜负预测、阵营评分、正式裁决字段。
8. NPC 不提供私聊。

### P4-G. `virtual-judge-npc-stage-closure`

目标：

1. 将本轮主体成果归档。
2. 把完成项写入 [completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md)。
3. 把明确延后债务写入 [todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md)。
4. 重置或归档 [当前开发计划.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md)。

验收标准：

1. completed/todo 只记录结构化完成快照和延后债务，不复制活动计划原文。
2. 若观战 WS ACL、暂停辩论状态机、多 persona、运营后台等未做，按真实债务写入 todo。
3. stage closure 后 plan consistency / docs lint 通过。

## 5. 暂不执行与触发条件

1. 不做暂停 / 恢复辩论：只有当 MVP 公开反馈闭环稳定，并单独完成房间暂停状态机设计后再做。
2. 不做用户私聊 NPC：PRD 明确用户无法私聊虚拟裁判 NPC。
3. 不做正式裁决替代：NPC 永远不生成正式裁决报告。
4. 不做多 NPC 生态：MVP 只做默认虚拟裁判。
5. 不做用户自定义模型 / Prompt / 皮肤：等基础 Agent loop 稳定后再评估。
6. 不恢复 `NPC Coach` / `Room QA`：旧功能已废弃，当前用户辩论助手另走独立主线。
7. 不在第一阶段强行纳入观战用户 WS ACL：若产品要求首发观战可见，则提升为 P1-B/P1-C 的前置任务。

## 6. 验证总策略

每个代码切片完成后，至少提供对应证据：

1. chat 改动：targeted Rust tests，覆盖权限、幂等、限频、schema guard、forbidden fields。
2. notify 改动：event mapping、dedupe、replay、ack tests。
3. frontend 改动：domain/reducer/component tests，必要时 Playwright smoke 和截图。
4. `npc_service` 改动：executor router、LLM fallback、guard、chat client mock、event consumer tests。
5. 跨层闭环：本地 smoke 证明用户发言到 NPC action 可见。
6. 文档同步：新增 `npc_service/` 后更新 [docs/architecture/README.md](/Users/panyihang/Documents/EchoIsle/docs/architecture/README.md)。

## 7. 当前待决问题

1. `npc_service` 首个输入消费方式：直接消费 Kafka / event bus，还是先通过 chat 内部 webhook 建本地闭环。
2. 首个可运行环境是否必须配置真实 OpenAI API，还是本地允许 rule-only fallback。
3. LLM provider 配置名、默认模型、超时、重试和成本上限。
4. 前端动态形象首版资产采用 CSS / 图片序列 / Lottie / canvas 哪一种。
5. 观战用户是否进入第一阶段实时可见范围。
6. `npc_service` 是否复用 `ai_judge_service` 的 runtime 工具代码，还是完全独立复制最小工具。

## 8. 同步历史

- 2026-05-03：基于已定档的虚拟裁判 NPC PRD、MVP 切片与系统设计，生成本开发计划；主线为独立 `npc_service` + LLM executor router + rule fallback。
- 2026-05-03：完成 P1-A `virtual-judge-npc-chat-action-spine`；chat 侧已具备 NPC action/config 表、内部 candidate sink、二次 guard、限频、幂等重放与 `DebateNpcActionCreated` outbox 事件骨架；下一步执行 P1-B notify replay 合同。
- 2026-05-03：完成 P1-B `virtual-judge-npc-notify-replay-contract`；`DebateNpcActionCreated` 已纳入 notify Kafka topic、AppEvent、room replay、ack/dedupe 合同，并同步 realtime-sdk / debate-domain payload 类型与可见字段 guard；下一步执行 P1-C 前端展示壳。

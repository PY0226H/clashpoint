# 虚拟裁判 NPC 下一阶段开发计划

更新时间：2026-05-04
文档状态：active 开发计划
当前主线：`virtual-judge-npc-beta-readiness-productization`

关联 PRD：[虚拟裁判NPC完整PRD.md](/Users/panyihang/Documents/EchoIsle/docs/PRD/虚拟裁判NPC完整PRD.md)
关联系统设计：[虚拟裁判NPC_系统设计.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_系统设计.md)
关联 MVP 探索：[虚拟裁判NPC_MVP切片与技术探索.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_MVP切片与技术探索.md)
上一阶段归档：[20260504T012752Z-virtual-judge-npc-stage-closure.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/虚拟裁判/20260504T012752Z-virtual-judge-npc-stage-closure.md)

---

## 1. 计划定位

本计划承接虚拟裁判 NPC MVP 阶段收口后的下一阶段开发。

上一阶段已经完成：

1. `chat` 侧 NPC action/config、内部候选动作接收、二次 guard、幂等、限频和 `DebateNpcActionCreated` 事件。
2. `notify_server` 对 `DebateNpcActionCreated` 的房间 WS 推送、replay、ack/dedupe 合同。
3. 前端 Debate Room 内的虚拟裁判 NPC 展示壳、action feed、状态和轻量动效。
4. 独立 `npc_service`、`llm_executor_v1` 主路径、`rule_executor_v1` fallback、OpenAI-compatible provider adapter、guard 和本地 webhook 闭环。
5. in-process full smoke、LLM disabled fallback、违规 LLM 输出隔离和主链不阻塞验证。

下一阶段目标不是重做 MVP，而是把 MVP 从“可闭环”推进到“可面向真实房间联调 / Beta 验收”的状态：

1. 移除或替换本地临时 webhook 触发路径，落到长期事件消费形态。
2. 让观战用户也能实时感知 NPC，同时保持发言权限隔离。
3. 已补齐运营控制、用户反馈、公开呼叫、近期行为记录等 PRD 中的核心产品能力。
4. 强化真实 LLM 主路径的成本、延迟、熔断、观测和可回滚能力。
5. 形成真实多服务浏览器 smoke 与可观测性证据。
6. 对暂停 / 恢复辩论强动作先完成状态机设计评审，再决定是否进入实现切片。

## 2. 冻结边界

本阶段继续遵守以下不可突破边界：

1. 虚拟裁判 NPC 永远不替代 AI 裁判团生成正式裁决报告。
2. 虚拟裁判 NPC 永远不作为最终胜负官方判定来源。
3. 用户不能私聊虚拟裁判 NPC。
4. NPC 不代替用户发言，不自动参赛，不站队。
5. NPC 不写 `verdict_ledger`、`judge_trace`、review queue 或正式裁决字段。
6. NPC 赞赏用户公开发言不构成官方评分、阵营优势或正式裁决依据。
7. `llm_executor_v1` 是体验主路径；`rule_executor_v1` 只作为 LLM 未配置、不可用、熔断或输出违规时的 fallback。
8. `chat` 继续作为房间事实源；`npc_service` 只生成候选动作；`notify_server` 只广播 `chat` 已确认事件。
9. 不恢复旧 `NPC Coach` / `Room QA` 作为虚拟裁判 NPC 主链路。

## 3. 当前代码事实快照

| 领域 | 当前事实 | 下一阶段影响 |
| --- | --- | --- |
| NPC action 事实源 | [npc.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/debate/npc.rs) 与 [debate_npc.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_npc.rs) 已提供 NPC context 查询、candidate 接收、近期行为、公开呼叫和反馈主链 | 下一阶段继续复用该事实源，新增能力不得绕过 `chat` 二次校验 |
| 实时事件 | [notif.rs](/Users/panyihang/Documents/EchoIsle/chat/notify_server/src/notif.rs)、[realtime-sdk](/Users/panyihang/Documents/EchoIsle/frontend/packages/realtime-sdk/src/index.ts)、[debate-domain](/Users/panyihang/Documents/EchoIsle/frontend/packages/debate-domain/src/index.ts) 已识别 `DebateNpcActionCreated` | 观战可见性和 replay smoke 应优先复用现有事件，不新增平行 WS 事件 |
| 前端展示 | [DebateNpcPanel.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/components/DebateNpcPanel.tsx) 与 [DebateNpcModel.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/components/DebateNpcModel.ts) 已提供 NPC 面板、状态模型、公开呼叫和反馈入口 | 下一阶段补视觉体验增强时应保持与 Judge / Draw 区隔 |
| NPC 服务 | [npc_service](/Users/panyihang/Documents/EchoIsle/npc_service) 已包含 FastAPI app、event processor、chat client、executor router、OpenAI-compatible provider、guard、event consumer、公开呼叫事件处理和 tests | 下一阶段重点是真实 LLM canary、熔断/成本/延迟观测和持久化 DLQ |
| 临时输入路径 | [app_factory.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/app_factory.py) 保留 local-dev webhook trigger | 生产默认输入已切到 Kafka/event-bus consumer，webhook 仅用于本地调试 |
| 完成与债务 | [completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md) B50 记录 MVP 完成；[todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md) C47 记录后置债 | 本计划优先消化 C47，同时补齐 PRD 的观战、运营、呼叫、反馈和暂停设计缺口 |

## 4. 与 PRD / 系统设计的对齐

### 4.1 已满足的 PRD 能力

1. 房间内可见虚拟裁判 NPC。
2. NPC 可公开发言、赞赏、触发轻量特效和状态变化。
3. NPC 与正式 AI 裁判团视觉和事件边界隔离。
4. NPC 不私聊用户，不生成正式裁决报告。
5. NPC 不可用时不影响用户发言、置顶、Judge / Draw。
6. 观战用户实时可见 NPC action。
7. 用户可在 NPC 面板内发起公开呼叫，查看近期行为，并提交私有反馈。
8. 运营可按房间 / 场次控制 NPC 开关、风格、能力和人工接管。

### 4.2 后续重点补齐

1. 真实 LLM 主路径的成本、延迟、熔断和降级观测。
2. 暂停 / 恢复辩论状态机设计。
3. 真实多服务运行态 smoke 和 dashboard 基线。
4. 动态形象、动效分级、低动效和移动端体验增强。

### 4.3 本阶段仍不直接做

1. 多 NPC 剧情生态。
2. 用户自定义 NPC 模型、Prompt、完整行为脚本。
3. 用户私聊 NPC 或个人专属辩论建议。
4. NPC 直接触发正式裁判团。
5. 未经状态机设计的暂停 / 恢复辩论实现。

## 5. 执行矩阵

### 已完成/未完成矩阵

| 模块 | 目标 | 状态 | 说明 |
| --- | --- | --- | --- |
| P0-A. `virtual-judge-npc-next-stage-planning-current-state` | 生成下一阶段计划，承接 B50/C47 与 PRD 缺口 | 已完成 | 本文档完成后即为下一阶段执行入口；已切换 default slot |
| P1-B. `virtual-judge-npc-event-consumer-cutover` | 将 `npc_service` 输入从本地 webhook 推进到 Kafka/event-bus consumer | 已完成 | 已新增事件消费 wrapper、Kafka/event-bus envelope 解码、commit/retry/DLQ 语义、可选 Kafka source 和 webhook local-dev 开关 |
| P1-C. `virtual-judge-npc-spectator-realtime-visibility` | 让观战用户可实时看到 NPC action，同时保持只读权限 | 已完成 | notify Debate Room WS 支持 participant/spectator 访问，connected spectators 可收到 NPC action；消息列表返回 viewer role，前端按观战态禁用参赛动作 |
| P1-D. `virtual-judge-npc-ops-control-plane` | 补齐运营开关、风格、能力控制和人工接管最小闭环 | 已完成 | 已新增 chat room config 扩展、Ops API、candidate 状态/能力二次拦截、npc_service roomConfig 静默降级和 Ops Console 最小入口 |
| P2-E. `virtual-judge-npc-public-call-history-feedback` | 支持用户公开呼叫 NPC、查看近期行为和提交轻量反馈 | 已完成 | 已采用 NPC 面板公开请求入口，chat 作为事实源，npc_service 消费公开呼叫事件 |
| P2-F. `virtual-judge-npc-llm-canary-cost-latency-guard` | 强化真实 LLM 主路径：provider canary、成本/延迟预算、熔断和回滚 | 待执行 | 确保 `llm_executor_v1` 是主路径，rule 只降级 |
| P2-G. `virtual-judge-npc-visual-experience-polish` | 增强动态形象、动效分级、低动效和移动端表现 | 待执行 | 对齐 PRD 第 6 节动态形象展示 |
| P3-H. `virtual-judge-npc-pause-state-machine-design-gate` | 完成暂停 / 恢复辩论强动作状态机设计与评审 | 待执行 | 先设计再实现，不在本模块中默认写强动作代码 |
| P3-I. `virtual-judge-npc-observability-runtime-smoke` | 建立 dashboard 基线与真实多服务浏览器 smoke 证据 | 待执行 | 消化 C47 的 runtime smoke 和 observability 债务 |
| P4-J. `virtual-judge-npc-beta-stage-closure` | 阶段收口，回写 completed/todo 并归档计划 | 待执行 | 只在主体切片完成后执行 |

## 6. 下一开发模块建议

1. 下一步执行 P2-F `virtual-judge-npc-llm-canary-cost-latency-guard`，强化真实 LLM 主路径的可观测和可回滚能力。
2. P2-F 完成后执行 P2-G `virtual-judge-npc-visual-experience-polish`，增强动态形象和移动端体验。
3. P2-G 可按资源拆开推进，但视觉增强必须保持正式裁决隔离。
4. P3-H 暂停状态机只做设计门禁；设计未通过前不实现 NPC pause tool。
5. P3-I 作为 Beta 验收前的统一运行态证据切片。

## 7. 模块详情

### P0-A. `virtual-judge-npc-next-stage-planning-current-state`

目标：

1. 基于 PRD、MVP 探索、系统设计、B50 完成快照和 C47 后置债，生成下一阶段开发计划。
2. 明确下一阶段主线为 Beta readiness / productization，而不是重复 MVP。
3. 保留 default slot 空档状态，等用户确认执行后再同步 [当前开发计划.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md)。

验收标准：

1. 本文档包含执行矩阵、下一模块建议、每个切片 DoD、验证策略和暂不执行范围。
2. 计划明确 `llm_executor_v1` 主路径与 `rule_executor_v1` fallback 边界。
3. 计划不暗示 NPC 可替代正式裁决或支持私聊。

### P1-B. `virtual-judge-npc-event-consumer-cutover`

目标：

1. 让 `npc_service` 通过长期事件消费路径接收 `DebateMessageCreated`。
2. 将 MVP webhook trigger 降级为开发工具或移除。
3. 建立 offset、重试、DLQ 和拒绝不无限重试的可验证语义。

执行范围：

1. `npc_service` event consumer / runtime bootstrap。
2. `npc_service/app/event_processor.py`
3. `npc_service/app/settings.py`
4. `chat` outbox / Kafka topic 配置检查。
5. `npc_service` tests 和必要的脚本证据。

建议步骤：

1. 冻结消费来源：优先对齐现有 chat outbox / Kafka 模式，消费 `DebateMessageCreated`。
2. 为 `NpcEventProcessor` 增加 consumer wrapper，保持 context fetch / decide / submit 主逻辑不变。
3. 增加 offset 提交策略：只有 context fetch、decision 和 callback 完成或明确 terminal reject 后才提交。
4. 将多次失败事件写入持久化或可审计 DLQ。
5. 明确 webhook trigger 移除条件；若保留，仅限 local dev，并在配置中默认关闭。
6. 补充服务停止、chat 拒绝、LLM 失败、callback 失败的 targeted tests。

验收标准：

1. `DebateMessageCreated` 能通过 event consumer 触发 NPC decision。
2. 同一事件不会因重试重复生成同一 action。
3. callback 被 `chat` 拒绝时不无限重试同一 payload。
4. `npc_service` 停止或 consumer 异常不影响用户发言主链。
5. webhook trigger 不再是生产默认路径。

建议验证：

1. `npc_service` consumer integration tests。
2. `npc_service` event processor / DLQ targeted tests。
3. `cargo test -p chat-server models::debate::tests::npc_action`
4. `post-module-test-guard --mode full` 或阶段内约定的后置门禁。

### P1-C. `virtual-judge-npc-spectator-realtime-visibility`

目标：

1. 让符合条件的观战用户能够实时看到 `DebateNpcActionCreated`。
2. 观战用户只能读房间实时事件，不能发送参赛发言。
3. 前端区分参赛态和观战态，不误开放输入或参赛动作。

执行范围：

1. `chat/notify_server/src/ws.rs`
2. `chat/notify_server/src/notif.rs`
3. `chat/chat_server` debate session participant / spectator 权限模型相关代码。
4. `frontend/packages/realtime-sdk`
5. `frontend/packages/app-shell/src/pages/DebateRoomPage.tsx`

建议步骤：

1. 先核验当前 Debate Room WS ACL 是否只允许 participant。
2. 设计 `participant or allowed spectator` 的只读 WS 策略。
3. 确保发言 API 仍只允许正反方参赛用户。
4. 前端在观战态隐藏或禁用参赛发言入口，但保持 NPC action feed 可见。
5. 补 replay 场景：观战用户断线重连后能恢复 NPC action。

验收标准：

1. 观战用户能连接房间 WS 并收到 NPC action。
2. 观战用户不能发送参赛发言、置顶或触发参赛专属动作。
3. 参赛用户现有 WS、发言、Judge / Draw 流程不回归。
4. NPC action 对参赛和观战用户的用户可见 payload 一致，且不含内部字段。

建议验证：

1. notify WS ACL targeted tests。
2. chat 发言权限 targeted tests。
3. realtime-sdk / app-shell tests。
4. 运行态 browser smoke：参赛用户发言，观战用户看到 NPC action。

### P1-D. `virtual-judge-npc-ops-control-plane`

状态：已完成。

目标：

1. 提供运营可控的 NPC 启用、风格、能力开关和人工接管最小闭环。
2. 让高风险能力默认可关闭，后续公开呼叫、特效和暂停设计有运营兜底。
3. 保持配置权威在 `chat`，`npc_service` 读取配置但不能绕过。

执行范围：

1. `debate_npc_room_configs` 相关 model / handler。
2. Ops 或内部管理 API。
3. 前端 Ops 控制入口或最小管理面板。
4. `npc_service` context / capability 判断。

建议步骤：

1. 明确配置层级：全局默认、场次覆盖、房间临时覆盖。
2. 支持启用/关闭、persona/style、主动发言、赞赏、特效、公开呼叫、警告等能力开关。
3. 增加 `manual_takeover` / `silent` / `unavailable` 状态的房间可见表达。
4. `chat` 在 candidate 接收时二次校验 capability allowed。
5. 前端展示 NPC 状态变化，不把人工接管误解成正式裁决。

验收标准：

1. 运营能按场次关闭 NPC，关闭后新事件不产生 action。
2. 运营能关闭赞赏或特效，`chat` 会拒绝对应候选动作。
3. 人工接管状态可被房间用户看见。
4. 配置变更不影响正式 AI 裁判团链路。

建议验证：

1. chat config / candidate guard targeted tests。
2. npc_service context capability tests。
3. app-shell 状态展示 tests。

完成快照：

1. `debate_npc_room_configs` 扩展为按场次控制启用状态、persona style、`active/silent/manual_takeover/unavailable`、发言/赞赏/特效/state change/警告/公开呼叫/暂停能力位。
2. `chat` 提供 Ops 读写 NPC room config API，并在状态变更时写入房间可见 `state_changed` action。
3. `chat` 在 candidate 接收边界二次校验 `enabled`、room status 和 capability，不允许 `npc_service` 绕过运营开关。
4. `npc_service` 从 decision context 读取 `roomConfig`，在关闭、非 active 或公开能力全关时直接 silent，不调用 executor。
5. Ops Console 增加按场次加载、编辑和保存 NPC 配置的最小管理面板。
6. 本切片未改动正式 AI 裁判团裁决链路。

### P2-E. `virtual-judge-npc-public-call-history-feedback`

状态：已完成。

目标：

1. 支持用户在房间公开呼叫 NPC。
2. 支持用户查看 NPC 最近关键行为。
3. 支持用户对 NPC 行为提交轻量反馈。

执行范围：

1. 房间公开消息解析或专用公开呼叫入口。
2. `npc_service` 新增 `UserNpcCallCreated` 或等价输入事件。
3. `debate_npc_actions` 查询 API。
4. `debate_npc_action_feedback` 或等价反馈记录。
5. 前端 NPC 面板交互。

建议步骤：

1. 冻结公开呼叫形式：例如公开消息中 `@虚拟裁判`，或 NPC 面板内发送公开请求。
2. 呼叫请求必须作为房间公开事件处理，不提供私聊。
3. 呼叫类型首版限制为规则解释、争点总结、请求暂停评估、举报刷屏/跑题、请求气氛效果。
4. NPC 可以回应、拒绝、静默观察或标记交给运营。
5. 最近行为列表展示时间、action type、内容、原因、是否人工接管。
6. 反馈类型支持有帮助、打断过多、不够中立、看不懂、其他问题。

验收标准：

1. 用户公开呼叫 NPC 后，房间内能看到 NPC 回应或拒绝说明。
2. 呼叫不会产生私聊消息，也不会返回个人专属辩论建议。
3. 用户能查看最近 NPC 行为。
4. 用户反馈可记录，且不在房间内公开引发争执。
5. NPC 仍不输出胜负预测、阵营评分或正式裁决字段。

建议验证：

1. chat / npc_service public call targeted tests。
2. action history API tests。
3. feedback API tests。
4. app-shell interaction tests。

完成快照：

1. `chat` 新增 `debate_npc_public_calls` 与 `debate_npc_action_feedback`，公开呼叫和反馈均由房间事实源统一落库。
2. `chat` 新增公开 API：近期 NPC 行为查询、公开呼叫创建、NPC action 私有反馈；对外只暴露 `actionId/actionUid/actionType/publicText/reasonCode/createdAt` 等公开字段。
3. `chat` 内部 context 支持 `publicCallId`，`DebateNpcPublicCallCreated` 事件进入 outbox / Kafka worker 校验链路。
4. `npc_service` 支持消费 `debate.npc.public_call.created`，根据 `publicCall` context 走 LLM / rule fallback，并在 `allowPublicCall=false` 时静默。
5. 前端 Debate Room NPC 面板增加公开呼叫入口、近期行为 hydration、每条行为的轻量反馈按钮；观战态和不可发言态不会开放公开呼叫。
6. 本切片不提供私聊、不提供个人辩论建议、不写正式裁决字段，也不触发正式 AI 裁判团。

### P2-F. `virtual-judge-npc-llm-canary-cost-latency-guard`

目标：

1. 让真实 LLM provider canary 成为可控、可观测、可回滚的主路径验证。
2. 为 `llm_executor_v1` 增加成本、延迟、熔断和输出违规统计。
3. 保持 `rule_executor_v1` 只是 fallback，不把 fallback 当成最终体验。

执行范围：

1. `npc_service/app/openai_provider.py`
2. `npc_service/app/executors.py`
3. `npc_service/app/settings.py`
4. `npc_service/app/guard.py`
5. 运行态配置与 evidence 文档。

建议步骤：

1. 明确 provider 配置名、model、timeout、retry、max tokens、每日/每房成本上限。
2. 增加 circuit breaker：限流、认证错误、超时、连续输出违规时自动 fallback。
3. 记录 `fallback_from_executor_kind`、`llm_error_code`、latency、token usage、model name。
4. 增加 provider canary 模式，只对测试房间或指定场次启用真实 LLM。
5. 强化结构化输出：LLM 只能返回 `NpcActionCandidate` 或 `no_action`。
6. 增加 prompt / policy 版本记录，但不向用户可见 payload 泄漏。

验收标准：

1. mock OpenAI-compatible provider 成功时走 `llm_executor_v1`。
2. provider 超时、限流、认证失败、输出违规时回退 rule 或静默。
3. 成本/延迟/错误指标可被记录和查询。
4. 真实 provider canary 有明确开启、关闭和回滚方式。
5. LLM 输出不能绕过 `npc_service` guard 与 `chat` 二次校验。

建议验证：

1. npc_service provider / executor targeted tests。
2. fault injection tests。
3. canary evidence 文档。

### P2-G. `virtual-judge-npc-visual-experience-polish`

目标：

1. 让 NPC 动态形象更符合娱乐化现场裁判定位。
2. 补齐状态、动效分级、低动效、移动端和观战态表现。
3. 确保 NPC 不遮挡消息、输入、倒计时、Judge / Draw。

执行范围：

1. [DebateNpcPanel.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/components/DebateNpcPanel.tsx)
2. [DebateNpcModel.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/components/DebateNpcModel.ts)
3. Debate Room 样式与响应式布局。
4. 必要的视觉资产或 CSS/Lottie/canvas 方案。

建议步骤：

1. 冻结首版视觉资产策略：CSS 动效、图片序列、Lottie 或 canvas。
2. 为 `observing / speaking / praising / silent / unavailable / manual_takeover` 提供可区分状态。
3. 对 `praise / speak / effect / state_changed` 定义动效强度。
4. 增加 reduced motion 和低性能降级。
5. 检查移动端、桌面端、窄屏下文本和按钮不溢出。

验收标准：

1. 用户进入房间后能立即识别 NPC 是赛中娱乐角色。
2. NPC 与赛后官方裁决入口视觉区分明确。
3. 特效不遮挡核心聊天内容和输入。
4. 低动效模式可用。
5. 移动端和桌面端布局稳定。

建议验证：

1. app-shell component tests。
2. Playwright screenshot / browser smoke。
3. reduced motion 检查。

### P3-H. `virtual-judge-npc-pause-state-machine-design-gate`

目标：

1. 单独完成暂停 / 恢复辩论状态机设计。
2. 明确 NPC 是否、何时、如何能触发暂停建议或暂停动作。
3. 在设计通过前，不把 `pause_debate` 加入 NPC 可执行 tool。

执行范围：

1. 新增或更新 `docs/module_design/虚拟裁判NPC` 下的暂停状态机设计。
2. `chat` 房间状态机、发言权限、倒计时、阶段流转影响分析。
3. 前端暂停态 UI 与用户提示设计。
4. 审计、权限、人工接管和撤销规则。

建议步骤：

1. 区分 `pause_suggestion`、`soft_pause`、`hard_pause`、`resume`。
2. 明确谁有权批准：系统规则、运营、管理员或 NPC 自动强动作。
3. 定义暂停期间是否允许消息、消息如何标记、倒计时如何处理。
4. 定义 WS replay、历史记录、用户可见原因和人工撤销。
5. 输出实现切片与风险清单，由用户确认后再进入代码开发。

验收标准：

1. 暂停 / 恢复状态机设计文档完成。
2. 权限、审计、replay、倒计时、输入禁用和恢复语义明确。
3. NPC tool schema 明确哪些动作是建议，哪些动作是强动作。
4. 用户确认是否进入实现阶段。

建议验证：

1. 设计评审 checklist。
2. 状态机测试计划。
3. 关键边界与 PRD 对齐检查。

### P3-I. `virtual-judge-npc-observability-runtime-smoke`

目标：

1. 建立 NPC dashboard / metrics / log baseline。
2. 形成真实多服务运行态 smoke 证据。
3. 验证 LLM fallback、WS replay、观战可见、服务不可用和正式裁决隔离。

执行范围：

1. `npc_service` metrics / logs。
2. `chat` NPC candidate/action metrics。
3. notify WS replay smoke。
4. frontend web smoke。
5. 运行态 evidence 文档。

建议步骤：

1. 定义指标：decision status、executor、fallback reason、callback accepted/rejected/failed、DLQ、latency、LLM timeout/rate-limit。
2. 定义 chat 指标：candidate request、created、rejected、rate limited、idempotency replayed、outbox enqueue failure。
3. 启动 chat、notify、frontend、npc_service。
4. 参赛用户发言，确认 NPC action 可见。
5. 观战用户进入，确认实时可见和 replay。
6. 模拟 LLM 失败、callback 失败、npc_service 停止。
7. 产出 smoke evidence。

验收标准：

1. 真实多服务 smoke 通过。
2. 断线重连后 NPC action 不丢、不重复。
3. `npc_service` 停止不影响发言、置顶、Judge / Draw。
4. dashboard / metrics / logs 能回答“为什么 fallback / 为什么拒绝 / 哪个 callback 失败”。
5. smoke evidence 不把本地 mock 或 rule-only fallback 宣称为真实 LLM 体验通过。

建议验证：

1. browser / Playwright smoke。
2. fault injection logs。
3. `post-module-test-guard --mode full`。
4. `git diff --check`。

### P4-J. `virtual-judge-npc-beta-stage-closure`

目标：

1. 汇总下一阶段主体成果。
2. 回写 [completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md)。
3. 将明确延后项写入 [todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md)。
4. 归档本开发计划。

验收标准：

1. completed/todo 只记录结构化完成快照和延后技术债，不复制活动计划全文。
2. Kafka consumer、观战 WS、运营控制、公开呼叫、LLM canary、视觉体验、暂停状态机设计、运行态 smoke 的完成状态清晰。
3. harness docs lint 通过。

## 8. 验证总策略

本阶段按风险分层验证：

1. `chat` 改动：优先覆盖权限、NPC enabled/capability、幂等、限频、forbidden fields、target message 同场和 outbox。
2. `notify_server` 改动：优先覆盖观战 WS ACL、participant 权限不回归、replay、ack、dedupe。
3. `npc_service` 改动：优先覆盖 event consumer、offset/retry/DLQ、LLM provider、fallback、guard、chat callback。
4. 前端改动：优先覆盖 NPC reducer、观战态、公开呼叫、反馈、动态形象、reduced motion 和 Judge / Draw 区隔。
5. 运行态：至少完成一次多服务 smoke，覆盖用户发言 -> NPC action -> WS replay -> 观战可见 -> LLM fallback -> 服务不可用不阻塞。
6. 文档同步：如果代码结构、主入口或第一跳定位变化，检查 [docs/architecture/README.md](/Users/panyihang/Documents/EchoIsle/docs/architecture/README.md) 是否需要更新。

## 9. 当前待决问题

1. 真实 LLM canary 首选模型、超时、成本上限和默认关闭策略。
2. 动态形象首版资产采用 CSS、图片序列、Lottie 还是 canvas。
3. 暂停 / 恢复是否由 NPC 直接触发，还是只能提出暂停建议并等待运营确认。

## 10. 同步历史

### 模块完成同步历史

- 2026-05-03：虚拟裁判 NPC MVP 已阶段收口，完成快照写入 [completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md) B50，后置债写入 [todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md) C47，完整活动计划归档到 [20260504T012752Z-virtual-judge-npc-stage-closure.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/虚拟裁判/20260504T012752Z-virtual-judge-npc-stage-closure.md)。
- 2026-05-04：基于虚拟裁判 NPC PRD、MVP 探索和系统设计，生成下一阶段 `virtual-judge-npc-beta-readiness-productization` 开发计划；P0-A 已完成，下一步建议执行 P1-B event consumer cutover。
- 2026-05-04：按用户确认开始执行下一阶段计划；default slot 已切换到本计划，P1-B `virtual-judge-npc-event-consumer-cutover` 进入进行中。
- 2026-05-04：完成 P1-B `virtual-judge-npc-event-consumer-cutover`；`npc_service` 已具备 Kafka/event-bus envelope consumer、终态 commit、失败重试、DLQ JSONL、可选 Kafka source 与 webhook local-dev 开关；下一步执行 P1-C `virtual-judge-npc-spectator-realtime-visibility`。
- 2026-05-04：完成 P1-C `virtual-judge-npc-spectator-realtime-visibility`；notify Debate Room WS 入口支持 participant/spectator 两种访问，connected spectator 会被纳入房间事件 fanout，`ListDebateMessagesOutput` 返回 viewer role，前端 Debate Room 观战态禁用发言、置顶、Judge / Draw 等参赛动作；下一步执行 P1-D `virtual-judge-npc-ops-control-plane`。
- 2026-05-04：完成 P1-D `virtual-judge-npc-ops-control-plane`；chat 新增 NPC room config 扩展、Ops 读写 API、状态/能力二次拦截和人工接管状态事件，npc_service 按 `roomConfig` 静默降级，Ops Console 增加按场次配置入口；下一步执行 P2-E `virtual-judge-npc-public-call-history-feedback`。
- 2026-05-04：完成 P2-E `virtual-judge-npc-public-call-history-feedback`；chat 新增公开呼叫、近期行为和私有反馈事实源/API，npc_service 支持公开呼叫事件与 `publicCall` context，前端 NPC 面板增加公开请求、近期行为 hydration 和反馈入口；下一步执行 P2-F `virtual-judge-npc-llm-canary-cost-latency-guard`。

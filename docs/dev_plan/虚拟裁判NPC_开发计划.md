# 虚拟裁判 NPC 下一阶段开发计划

更新时间：2026-05-04
文档状态：active，P1-B 已完成
当前主线：`virtual-judge-npc-beta-real-env-canary-dashboard-closure`

关联 PRD：[虚拟裁判NPC完整PRD.md](/Users/panyihang/Documents/EchoIsle/docs/PRD/虚拟裁判NPC完整PRD.md)
关联系统设计：[虚拟裁判NPC_系统设计.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_系统设计.md)
关联 canary 手册：[虚拟裁判NPC_LLM_Canary运行手册.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_LLM_Canary运行手册.md)
关联 readiness 清单：[虚拟裁判NPC_Beta真实环境Readiness输入清单.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_Beta真实环境Readiness输入清单.md)
关联 dashboard 基线：[虚拟裁判NPC_CanaryDashboard查询与告警基线.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_CanaryDashboard查询与告警基线.md)
关联 pause_suggestion 证据：[虚拟裁判NPC_pause_suggestion_Smoke与Guard证据.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_pause_suggestion_Smoke与Guard证据.md)
上一阶段归档：[20260504T230728Z-virtual-judge-npc-real-env-pause-stage-closure.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/虚拟裁判/20260504T230728Z-virtual-judge-npc-real-env-pause-stage-closure.md)
完成快照：[completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md) B52
后置待办：[todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md) C47

---

## 1. 计划定位

本计划承接 B52 `virtual-judge-npc-real-env-and-pause-suggestion-stage-closure`。

上一阶段已经完成仓内闭环：

1. 虚拟裁判 NPC 已采用独立 `npc_service` 架构，`llm_executor_v1` 为体验主路径，`rule_executor_v1` 为 LLM 不可用或输出违规时的 fallback。
2. `chat` 是 NPC action 的唯一房间事实源，`notify_server` 只广播已确认事件。
3. 前端 Debate Room 已展示公开虚拟裁判 NPC 动态面板、动作 feed、公开呼叫和反馈入口。
4. `pause_suggestion` 已完成合同冻结、跨层实现、观战 replay、只读 smoke 与 guard 证据。
5. NPC 仍保持娱乐导向，不私聊用户，不替代 AI 裁判团正式裁决报告。

本阶段不继续扩展新能力，而是收敛 C47 中最高优先级的真实环境债：

1. 在 Beta / staging 环境验证真实 OpenAI-compatible provider、Kafka/event-bus、chat callback、notify WS 和前端房间联动。
2. 让 dashboard / 日志查询能回答真实 canary 中的 executor、fallback、callback、DLQ、成本、延迟、熔断和拒绝原因。
3. 形成 `pass / env_blocked / fail / rollback_required` 的 evidence 结论，为后续 Beta 开关或强暂停状态机决策提供依据。

## 2. 当前代码事实快照

| 领域 | 当前事实 | 代码 / 文档证据 |
| --- | --- | --- |
| `chat` action spine | `debate_npc_actions` 已支持 `speak/praise/effect/state_changed/pause_suggestion`；candidate 会校验能力位、正式裁决字段、幂等和 replay event | [npc.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/debate/npc.rs), [npc_action.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/debate/tests/npc_action.rs), [20260504123000_debate_npc_pause_suggestion_action_type.sql](/Users/panyihang/Documents/EchoIsle/chat/migrations/20260504123000_debate_npc_pause_suggestion_action_type.sql) |
| `allow_pause` 边界 | `allow_pause=true` 只允许 `pause_suggestion`，不授权强暂停 / 恢复；`pause_review` 已可作为公开呼叫进入 NPC 决策上下文 | [npc.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/debate/npc.rs), [npc_action.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/debate/tests/npc_action.rs) |
| `npc_service` executor | router 已覆盖 LLM、canary session 限制、成本/延迟 metrics、熔断、`no_action`、rule fallback 和 guard 拒绝 | [executors.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/executors.py), [llm_runtime.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/llm_runtime.py), [guard.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/guard.py), [test_executors.py](/Users/panyihang/Documents/EchoIsle/npc_service/tests/test_executors.py) |
| 真实 LLM provider | OpenAI-compatible provider 与 prompt guard 已有仓内 mock 验证；真实 provider canary 尚未执行 | [openai_provider.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/openai_provider.py), [test_openai_provider.py](/Users/panyihang/Documents/EchoIsle/npc_service/tests/test_openai_provider.py), [虚拟裁判NPC_LLM_Canary运行手册.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_LLM_Canary运行手册.md) |
| 事件消费 | `npc_service` 已有 `DebateMessageCreated` / `DebateNpcPublicCallCreated` consumer 与 DLQ 测试；真实 Kafka topic / consumer group 尚未在 Beta/staging 证据中确认 | [event_consumer.py](/Users/panyihang/Documents/EchoIsle/npc_service/app/event_consumer.py), [test_event_consumer.py](/Users/panyihang/Documents/EchoIsle/npc_service/tests/test_event_consumer.py) |
| notify replay | `DebateNpcActionCreated` 可 replay 给观战者，已补 `pause_suggestion` 只读观战测试 | [notif.rs](/Users/panyihang/Documents/EchoIsle/chat/notify_server/src/notif.rs), [ws.rs](/Users/panyihang/Documents/EchoIsle/chat/notify_server/src/ws.rs) |
| 前端房间 | Debate Room 已支持 NPC action hydration、WS live event、`pause_suggestion` 展示、公开呼叫、反馈和观战只读 smoke | [DebateRoomPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/DebateRoomPage.tsx), [DebateNpcPanel.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/components/DebateNpcPanel.tsx), [auth-smoke.spec.ts](/Users/panyihang/Documents/EchoIsle/frontend/tests/e2e/auth-smoke.spec.ts) |
| 真实环境证据 | 仓内 smoke / guard 已通过；真实 Beta / staging canary、dashboard 截图、真实 provider 成本 / 延迟证据仍为 `env_blocked` | [虚拟裁判NPC_pause_suggestion_Smoke与Guard证据.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_pause_suggestion_Smoke与Guard证据.md), [todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md) C47 |

计划生成时工作区仍有上一阶段收口文档未提交；开始执行真实环境阶段前，建议先确认这些文档是否纳入同一提交，避免 evidence 口径在后续计划中漂移。

## 3. 冻结边界

本阶段继续遵守以下边界：

1. 虚拟裁判 NPC 永远不替代 AI 裁判团生成正式裁决报告。
2. 虚拟裁判 NPC 不输出胜负判定、阵营评分、正式裁决字段或 judge trace。
3. 用户不能私聊虚拟裁判 NPC。
4. NPC 不代替用户发言，不自动参赛，不站队。
5. `pause_suggestion` 只表达公开建议，不改变房间状态、不禁用输入、不冻结倒计时。
6. 本阶段不实现 `soft_pause/hard_pause/resume` 强暂停状态机。
7. 真实环境 canary 未执行前，不得把本地 mock、仓内 smoke、rule-only fallback 或字段存在宣称为真实环境通过。
8. 若真实 LLM、Kafka、dashboard 或测试账号缺失，本阶段只能输出 `env_blocked`，不能硬写 `pass`。

## 4. 阶段目标

### 4.1 产品目标

1. 让运营和产品可以判断虚拟裁判 NPC 是否具备进入 Beta 小流量的证据。
2. 证明用户在真实房间内能清楚区分娱乐 NPC 行为与正式 AI 裁判团裁决。
3. 证明 `pause_suggestion` 在真实房间中只是建议，不会制造“房间已暂停”的误解。
4. 形成明确回滚路径：真实 LLM 出错时，房间发言、观战和正式裁决主链不受影响。

### 4.2 工程目标

1. 完成真实 Beta / staging provider、Kafka/event-bus、chat、notify、frontend、npc_service 的端到端 canary。
2. 固化 dashboard / 日志 / SQL / Kafka / DLQ 查询证据，让关键异常可定位。
3. 演练 provider 不可用、canary 关闭、callback 拒绝、`npc_service` 停止等故障场景。
4. 产出 evidence 文档，并根据真实结果给出 `pass / env_blocked / fail / rollback_required` 结论。

### 已完成/未完成矩阵

| 模块 | 目标 | 状态 | 说明 |
| --- | --- | --- | --- |
| P0-A. `virtual-judge-npc-beta-real-env-plan-current-state` | 基于 PRD、module_design 和当前代码事实生成下一阶段计划 | 已完成 | 本文档即该模块输出；用户已确认执行，default slot 已绑定本主线 |
| P1-B. `virtual-judge-npc-preflight-working-tree-and-config-baseline` | 开始真实环境前整理上一阶段收口状态、迁移状态、配置清单和执行窗口 | 已完成 | 已输出 [虚拟裁判NPC_Beta真实环境Preflight基线.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_Beta真实环境Preflight基线.md)；本机 DB 迁移为 pending，真实环境输入仍需 P1-C 核验 |
| P1-C. `virtual-judge-npc-beta-readiness-gate-run` | 按 readiness 清单执行真实环境前置检查，输出 `ready / env_blocked / fail` | 待执行 | 缺 provider、Kafka、服务编排、dashboard、账号任一关键项时直接 `env_blocked` |
| P1-D. `virtual-judge-npc-single-session-llm-canary-run` | 在单个 Beta / staging 房间跑真实 LLM canary | 待执行（环境具备后） | 验证真实 provider 响应、NPC action 生成、参赛者可见、观战实时 / replay 可见 |
| P1-E. `virtual-judge-npc-canary-dashboard-evidence-pack` | 固化 dashboard / 日志 / SQL / Kafka / DLQ 查询证据 | 待执行（环境具备后） | 必须能查 executor、fallback reason、callback accepted/rejected/failed、DLQ、latency、cost、circuit |
| P2-F. `virtual-judge-npc-failure-drill-and-rollback` | 演练真实环境失败路径与回滚 | 待执行（环境具备后） | 覆盖 provider unavailable、canary session 移除、chat candidate rejected、`npc_service` stop |
| P2-G. `virtual-judge-npc-real-env-evidence-and-release-decision` | 汇总 canary evidence 并给出 release decision | 待执行 | 输出 `pass / env_blocked / fail / rollback_required`，并给出是否进入 Beta 小流量建议 |
| P3-H. `virtual-judge-npc-real-env-findings-remediation` | 针对真实 canary 发现的问题进行最小修复 | 待执行（条件） | 仅在 P1-D/P1-E/P2-F 发现真实缺陷后执行；不得扩展强暂停或新能力 |
| P4-I. `virtual-judge-npc-beta-real-env-stage-closure` | 阶段收口，回写 completed/todo 并归档计划 | 待执行 | 仅在 evidence 结论明确后执行 |

### 下一开发模块建议

1. 默认下一步执行 P1-C `virtual-judge-npc-beta-readiness-gate-run`。
2. 如果 P1-B/P1-C 发现真实环境关键输入缺失，直接产出 `env_blocked` evidence，并跳到 P2-G/P4-I 做阶段收口。
3. 只有 P1-C 判定 `ready` 后，才执行 P1-D/P1-E/P2-F 的真实 canary 与故障演练。

## 5. 模块详情

### P0-A. `virtual-judge-npc-beta-real-env-plan-current-state`

目标：

1. 根据 PRD、系统设计、canary 手册、readiness 清单、dashboard 基线、B52/C47 和当前代码事实生成下一阶段计划。
2. 明确本阶段只做真实环境 canary/dashboard closure，不做强暂停状态机。
3. 明确 `env_blocked` 是合法阶段结论，避免为了推进计划伪造真实环境 pass。

验收标准：

1. 计划包含执行矩阵、下一模块建议、模块 DoD、验证策略和冻结边界。
2. 计划明确真实 provider / Kafka / dashboard 证据缺失时的处理方式。
3. 计划引用当前代码事实，而不是只复述设计文档。

### P1-B. `virtual-judge-npc-preflight-working-tree-and-config-baseline`

目标：

1. 在进入真实环境前，确认上一阶段收口文档、ignored evidence、迁移和配置模板状态。
2. 确认本阶段不会在未提交或口径不一致的基础上继续叠 evidence。
3. 准备真实环境执行窗口所需的非 secret 输入。

执行范围：

1. `git status` 与上一阶段文档归档状态。
2. `chat` migration 状态：`20260503090000_debate_npc_action_spine.sql`、`20260504100000_debate_npc_ops_control_plane.sql`、`20260504123000_debate_npc_pause_suggestion_action_type.sql`。
3. `npc_service` canary env 模板：`NPC_SERVICE_LLM_ENABLED`、`NPC_SERVICE_LLM_CANARY_ENABLED`、`NPC_SERVICE_LLM_CANARY_SESSION_IDS`、provider base URL、模型、成本上限、Kafka topic/group。
4. 测试账号、canary session、观战账号、Ops 开关权限。

验收标准：

1. 明确哪些上一阶段文件需要纳入提交或保留为本地证据。
2. 明确真实环境执行所需输入是否齐备。
3. 若缺少必需输入，输出缺口清单并进入 P1-C `env_blocked`。

建议验证：

1. `git status --short`
2. `git diff --check`
3. `bash scripts/quality/harness_docs_lint.sh`
4. `sqlx migrate info` 或当前项目等价迁移核验命令。

完成结果：

1. 已确认上一阶段仍有未提交收口文档与新归档文件。
2. 已确认 `pause_suggestion` smoke 证据与本次 preflight 文档受 `docs/**` ignore 影响，提交时需要 `git add -f`。
3. 已确认三条 NPC migration 文件存在。
4. 已执行本机 `sqlx migrate info`；当前本机 `chat` 数据库显示包括 NPC 迁移在内均为 `pending`，不能作为真实 canary ready 证据。
5. 已确认 `npc_service` canary env、Kafka topic、DLQ、OpenAI-compatible provider 配置入口存在。
6. 已确认真实 provider、Kafka broker/topic/group、dashboard、canary session、测试账号与 Ops 权限仍需外部输入。

### P1-C. `virtual-judge-npc-beta-readiness-gate-run`

目标：

1. 按 readiness 清单执行真实环境 gate。
2. 给出 `ready / env_blocked / fail` 三态结论。
3. 不跑真实用户影响面之前，先确认可回滚、可观测、可停止。

执行范围：

1. Beta / staging `chat`、`notify_server`、`npc_service`、frontend web/desktop 入口健康检查。
2. 真实 OpenAI-compatible provider 可用性检查。
3. Kafka/event-bus topic、consumer group、offset、DLQ 路径检查。
4. chat internal API auth 与 callback auth 检查。
5. dashboard / 日志聚合权限检查。

验收标准：

1. `npc_service` `/healthz` 与 `/api/internal/npc/runtime/metrics` 可访问且鉴权符合预期。
2. provider 可返回真实响应，或明确记录不可用原因。
3. Kafka topic / consumer group 能看到目标事件流或明确记录缺失原因。
4. dashboard / 日志入口能查询 P1-E 所需字段，或明确记录缺失原因。
5. 任一关键项缺失时输出 `env_blocked`，不继续 P1-D。

### P1-D. `virtual-judge-npc-single-session-llm-canary-run`

目标：

1. 在一个指定 Beta / staging canary session 中启用真实 `llm_executor_v1`。
2. 验证公开发言、公开呼叫和 `pause_review` 可以触发合法 NPC 行为。
3. 验证非 canary session 不会被真实 LLM 处理。

执行范围：

1. 单 session canary 配置。
2. 参赛用户发言触发 `DebateMessageCreated`。
3. 参赛用户公开呼叫触发 `DebateNpcPublicCallCreated`。
4. 观战用户实时进入与断线重连 replay。
5. `pause_suggestion` 只展示建议，不改房间状态。

验收标准：

1. canary session 内至少产生一次真实 provider 驱动的合法 NPC action。
2. `executorKind=llm_executor_v1`、model/provider、latency、token 或成本字段可查。
3. 参赛双方和观战用户均可见 NPC action。
4. replay 不丢、不重、不把 `pause_suggestion` 显示成“已暂停”。
5. 非 canary session 被 `llm_canary_session_not_allowed` 阻断，并按配置 fallback 或静默。

### P1-E. `virtual-judge-npc-canary-dashboard-evidence-pack`

目标：

1. 把 P1-D 的运行态证据落到 dashboard / 日志 / SQL / Kafka / DLQ 查询包。
2. 证明关键问题可以定位：谁生成、为什么 fallback、哪里拒绝、是否熔断、成本多少。

执行范围：

1. `npc_service` runtime metrics 与 decision run。
2. `chat` candidate accepted / rejected / failed 日志。
3. `debate_npc_actions` 与 `event_outbox` 查询。
4. Kafka offset、consumer lag、DLQ。
5. notify live / replay / send_failed / lag。
6. 前端 roomEvent trace 或 smoke 记录。

验收标准：

1. 每个关键字段都有查询入口、截图或导出。
2. fallback reason、callback status、DLQ、latency、cost、circuit、guard rejected 均可查。
3. dashboard 缺失时不得判定真实 canary `pass`，只能 `env_blocked` 或 `fail`。

### P2-F. `virtual-judge-npc-failure-drill-and-rollback`

目标：

1. 演练真实环境中最可能发生的故障。
2. 确认虚拟裁判 NPC 出问题时不会阻塞辩论主链。
3. 确认运营可回滚到 rule fallback、静默或关闭 NPC。

故障演练范围：

1. provider unavailable / timeout / rate limit。
2. canary session 从 allowlist 移除。
3. LLM 输出正式裁决字段或强暂停字段。
4. `chat` candidate rejected。
5. `npc_service` 停止或 Kafka consumer 停止。
6. notify replay lag 或断线重连。

验收标准：

1. 发言主链不阻塞。
2. 正式 AI 裁判团链路不受 NPC 故障影响。
3. provider 或 guard 失败可 fallback 到 rule 或静默。
4. 回滚步骤可由工程或运营按文档执行。
5. 失败、fallback、DLQ、熔断、callback 状态可观测。

### P2-G. `virtual-judge-npc-real-env-evidence-and-release-decision`

目标：

1. 汇总 P1-C/P1-D/P1-E/P2-F 的真实环境证据。
2. 给出 `pass / env_blocked / fail / rollback_required` 结论。
3. 给出是否允许进入 Beta 小流量的建议。

输出要求：

1. 新增 evidence 文档到 `docs/module_design/虚拟裁判NPC`。
2. 标明环境、时间窗口、canary session、账号角色、服务版本、配置摘要。
3. 隐去真实 secret、用户隐私和不可公开环境信息。
4. 对所有异常给出处理状态：已修复、已回滚、后置债、阻塞。

验收标准：

1. evidence 能支撑最终结论。
2. 若结论为 `pass`，必须同时具备真实 provider、Kafka、callback、notify、frontend、dashboard / 日志证据。
3. 若结论为 `env_blocked`，必须列明缺失项与下一次触发条件。
4. 若结论为 `fail` 或 `rollback_required`，必须列明用户影响、回滚动作和修复计划。

### P3-H. `virtual-judge-npc-real-env-findings-remediation`

目标：

1. 对真实 canary 发现的问题做最小修复。
2. 只修真实环境暴露出的缺陷，不扩展新能力。

允许范围：

1. 配置解析、healthcheck、metrics 字段、日志字段、dashboard 查询脚本。
2. provider 超时、fallback reason、DLQ 标记、callback 错误分类。
3. 前端真实 roomEvent 展示或 replay hydration 缺陷。
4. notify live / replay 一致性问题。

禁止范围：

1. 强暂停 / 恢复状态机。
2. 私聊 NPC。
3. 官方裁决字段。
4. 新增未在 PRD / 系统设计确认的 NPC 能力。

验收标准：

1. 每个修复都有真实故障证据和 targeted regression。
2. 修复后重新执行相关 canary / drill 或给出无法执行原因。

### P4-I. `virtual-judge-npc-beta-real-env-stage-closure`

目标：

1. 将本阶段主体结论写入 `completed.md`。
2. 将真实环境缺口或后置能力写入 `todo.md`。
3. 归档本开发计划，并重置活动计划。

验收标准：

1. completed 只记录主体完成快照。
2. todo 只记录延后技术债，不复制活动计划正文。
3. 归档文档包含真实 evidence 结论和验证摘要。
4. `harness_docs_lint.sh` 通过。

## 6. 验证策略

### 6.1 本地回归基线

在进入真实环境前，建议至少复跑：

1. `cargo test -p chat-server npc_action`
2. `cargo test -p notify-server debate_room_ws_handler_should_replay_pause_suggestion_to_readonly_spectator`
3. `/Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/python -m pytest tests/test_guard.py tests/test_executors.py tests/test_event_processor.py`
4. `pnpm --dir frontend --filter @echoisle/debate-domain test`
5. `pnpm --dir frontend --filter @echoisle/realtime-sdk test`
6. `pnpm --dir frontend --filter @echoisle/app-shell test -- DebateNpc`
7. `pnpm --dir frontend --filter @echoisle/app-shell typecheck`
8. targeted Playwright NPC / spectator smoke
9. `git diff --check`
10. `bash scripts/quality/harness_docs_lint.sh`

### 6.2 真实环境验证

真实 canary 必须覆盖：

1. 真实 provider 成功生成合法 NPC action。
2. provider 失败、超时、限流、输出违规时 fallback / silent 不阻塞主链。
3. 参赛者、观战者实时可见与 replay 一致。
4. `pause_suggestion` 不改变房间状态。
5. 非 canary session 不走真实 LLM。
6. dashboard / 日志能查询全部关键字段。
7. 回滚后 NPC 关闭或降级生效。

## 7. 风险与处理

| 风险 | 影响 | 处理 |
| --- | --- | --- |
| 真实 provider 或 secret 未提供 | 无法验证 LLM 主路径 | P1-C 输出 `env_blocked`，不伪造 pass |
| Kafka / event-bus 与本地配置不一致 | NPC action 不触发或 DLQ 积压 | P1-C 先查 topic/group/offset，P2-F 演练 consumer 停止 |
| dashboard 字段缺失 | 无法定位 fallback / 成本 / callback | P1-E 必须补查询入口；缺失则 `env_blocked` |
| LLM 输出越权字段 | 可能混淆正式裁决 | guard 必须拒绝，chat candidate 再拒绝，P2-F 演练 |
| `pause_suggestion` 被用户理解为已暂停 | 产品误解 | 前端只展示建议卡片，不显示暂停横幅，不禁用输入 |
| NPC 故障影响发言主链 | 核心流程风险 | `chat` 事实源优先，`npc_service` 停止不应阻塞发言 |

## 8. 执行决策点

1. P1-C 若为 `ready`：继续 P1-D/P1-E/P2-F。
2. P1-C 若为 `env_blocked`：跳到 P2-G 输出缺口 evidence，再进入 P4-I 收口。
3. P1-D/P1-E/P2-F 若出现真实缺陷：进入 P3-H 最小修复。
4. P2-G 若为 `pass`：建议进入 Beta 小流量开关策略设计。
5. P2-G 若为 `fail` 或 `rollback_required`：先修复真实故障，不进入强暂停或新能力开发。

### 模块完成同步历史

1. 2026-05-04：生成 `virtual-judge-npc-beta-real-env-canary-dashboard-closure` 下一阶段开发计划；P0-A 已完成，下一步建议执行 P1-B。
2. 2026-05-04：执行 P1-B preflight，完成工作区、迁移、配置入口、topic 与外部输入缺口基线；下一步建议执行 P1-C readiness gate。

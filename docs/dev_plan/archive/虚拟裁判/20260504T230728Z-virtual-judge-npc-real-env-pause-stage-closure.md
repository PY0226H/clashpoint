# 虚拟裁判 NPC Real-Env & pause_suggestion 阶段收口

更新时间：2026-05-04
文档状态：archived stage closure
当前主线：`virtual-judge-npc-real-env-and-pause-suggestion`（已收口）

关联 PRD：[虚拟裁判NPC完整PRD.md](/Users/panyihang/Documents/EchoIsle/docs/PRD/虚拟裁判NPC完整PRD.md)
关联系统设计：[虚拟裁判NPC_系统设计.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_系统设计.md)
关联完成快照：[completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md) B52
关联后置债：[todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md) C47

---

## 1. 收口结论

本阶段主体已完成：

1. 真实 Beta / staging readiness 输入清单已形成。
2. canary dashboard / 日志查询 / 告警演练基线已形成。
3. `pause_suggestion` 产品与技术合同已冻结。
4. `chat` 已支持 `pause_suggestion` candidate、`allow_pause` 能力位、DB check 迁移、公开呼叫门禁和 targeted tests。
5. `npc_service` 已支持 LLM / rule 生成暂停建议，并通过 guard 隔离强暂停动作、官方裁决字段和不合规输出。
6. 前端已支持 `pause_suggestion` action union、runtime parser、NPC feed / panel、replay hydration、参赛者 smoke 和观战者 read-only smoke。
7. `notify_server` 已补观战者 replay `pause_suggestion` 的 WS 测试。
8. smoke / guard 证据已归档，仓内跨层验证通过。

关键产品边界：

1. `pause_suggestion` 只是公开建议，不改变房间状态。
2. `pause_suggestion` 不禁用参赛者输入、不冻结倒计时、不显示“已暂停”。
3. 虚拟裁判 NPC 永远不替代 AI 裁判团生成正式裁决报告。
4. 用户不能私聊虚拟裁判 NPC。
5. `soft_pause/hard_pause/resume` 不在本阶段实现；未来若做，必须由 `chat` 状态机、审批、审计和 replay 合同承载。

真实环境状态：

1. 真实 Beta / staging canary 未执行。
2. 当前无真实 OpenAI-compatible provider、Kafka topic / consumer group、服务编排窗口和 dashboard 截图证据。
3. P1-D 仍为 `env_blocked`，不得把本地 mock / 仓内 smoke 宣称为真实环境 pass。

## 2. 完成模块

| 模块 | 状态 | 归档说明 |
| --- | --- | --- |
| P0-A. `virtual-judge-npc-next-stage-plan-current-state` | 已完成 | 基于 PRD、module_design 和当前代码事实生成阶段计划 |
| P1-B. `virtual-judge-npc-real-env-readiness-pack` | 已完成 | 输出真实 Beta / staging readiness 输入清单 |
| P1-C. `virtual-judge-npc-dashboard-query-pack` | 已完成 | 输出 canary dashboard / 日志查询 / 告警演练基线 |
| P1-D. `virtual-judge-npc-real-env-canary-run` | 条件后置 | 缺真实环境，保持 `env_blocked`，写入 C47 |
| P2-E. `virtual-judge-npc-pause-suggestion-contract-freeze` | 已完成 | 冻结 `pause_suggestion` 合同、展示和非目标 |
| P2-F. `virtual-judge-npc-pause-suggestion-chat-spine` | 已完成 | `chat` 事实源支持 `pause_suggestion` |
| P2-G. `virtual-judge-npc-pause-suggestion-npc-service-executor` | 已完成 | `npc_service` LLM / rule / guard 支持暂停建议 |
| P2-H. `virtual-judge-npc-pause-suggestion-frontend-ux` | 已完成 | 前端建议卡片、replay hydration 和 feedback 已支持 |
| P3-I. `virtual-judge-npc-pause-suggestion-smoke-and-guard` | 已完成 | 跨层 smoke / guard 证据已归档 |
| P4-J. `virtual-judge-npc-real-env-pause-stage-closure` | 已完成 | 已回写 completed / todo 并重置活动计划 |

## 3. 验证摘要

已通过：

1. `cargo test -p chat-server npc_action`（19 passed）
2. `cargo test -p notify-server debate_room_ws_handler_should_replay_pause_suggestion_to_readonly_spectator`（1 passed）
3. `/Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/python -m pytest tests/test_guard.py tests/test_executors.py tests/test_event_processor.py`（30 passed）
4. `pnpm --dir frontend --filter @echoisle/debate-domain test`（17 passed）
5. `pnpm --dir frontend --filter @echoisle/realtime-sdk test`（6 passed）
6. `pnpm --dir frontend --filter @echoisle/app-shell test -- DebateNpc`（17 passed）
7. `pnpm --dir frontend --filter @echoisle/app-shell typecheck`
8. targeted Playwright NPC / spectator smoke（2 passed）
9. `pnpm --dir frontend e2e:smoke:web`（11 passed）
10. `cargo fmt --all`
11. `git diff --check`

## 4. 长期文档同步

1. `completed.md` 新增 B52 `virtual-judge-npc-real-env-and-pause-suggestion-stage-closure`。
2. `todo.md` C47 更新为两个后置项：
   - `virtual-judge-npc-beta-real-env-canary-dashboard-closure`
   - `virtual-judge-npc-strong-pause-approval-state-machine-implementation`
3. `当前开发计划.md` 重置为 default slot 空档。
4. `虚拟裁判NPC_开发计划.md` 重置为已收口索引。

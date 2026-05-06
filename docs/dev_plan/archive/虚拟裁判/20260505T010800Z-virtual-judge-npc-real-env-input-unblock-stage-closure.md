# 虚拟裁判 NPC 真实环境输入解锁阶段收口

更新时间：2026-05-04
文档状态：archived stage closure
当前主线：`virtual-judge-npc-real-env-input-unblock-pack`（已收口）

关联 PRD：[虚拟裁判NPC完整PRD.md](/Users/panyihang/Documents/EchoIsle/docs/PRD/虚拟裁判NPC完整PRD.md)
关联完成快照：[completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md) B54
关联后置债：[todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md) C47

---

## 1. 收口结论

本阶段结论为 `still_env_blocked`。

已完成：

1. P0-A 生成并绑定 `virtual-judge-npc-real-env-input-unblock-pack` 计划。
2. P1-B 输出真实环境输入 Owner 交付合同。
3. P1-C 输出真实环境 Evidence 脱敏模板。
4. P1-D 输出 Readiness Gate 重跑手册。
5. P2-E 输出目标环境 migration 与服务地图。
6. P2-F 输出 Kafka 与 Dashboard 交付合同。
7. P2-G 输出 Canary Session 与账号输入包。
8. P3-H 输出真实环境输入解锁 Decision，结论为 `still_env_blocked`。

未执行：

1. 不重跑真实环境 readiness gate。
2. 不执行真实单 session LLM canary。
3. 不进入 Beta 小流量。
4. 不执行强暂停 / 恢复状态机开发。

未执行原因：真实 Beta/staging 服务入口、provider、Kafka/topic/group、dashboard/log 权限、canary session、测试账号、Ops 回滚 owner、目标环境 migration 证据和数据合规 reviewer 仍未交付。

## 2. 完成模块

| 模块 | 状态 | 归档说明 |
| --- | --- | --- |
| P0-A. `virtual-judge-npc-real-env-input-unblock-plan-current-state` | 已完成 | 基于 PRD、module design、B53/C47 和当前代码事实生成输入解锁计划 |
| P1-B. `virtual-judge-npc-real-env-input-owner-handoff-contract` | 已完成 | 定义真实环境输入 owner、交付格式和验收口径；不记录 secret |
| P1-C. `virtual-judge-npc-redacted-evidence-template-pack` | 已完成 | 定义 service、provider、Kafka、dashboard、账号、rollback、frontend/notify smoke 的脱敏模板 |
| P1-D. `virtual-judge-npc-readiness-gate-rerun-playbook` | 已完成 | 固化输入齐备后如何从 `env_blocked` 重新进入 readiness gate |
| P2-E. `virtual-judge-npc-target-env-migration-and-service-map` | 已完成 | 明确目标环境 migration、chat routes、npc_service health/metrics、notify WS、frontend/Ops 检查入口 |
| P2-F. `virtual-judge-npc-kafka-dashboard-query-contract` | 已完成 | 明确 Kafka / DLQ / dashboard 查询 owner、字段、截图或 export 口径 |
| P2-G. `virtual-judge-npc-canary-session-and-account-pack` | 已完成 | 定义 canary session、参赛/观战/Ops 账号、权限和数据合规输入包 |
| P3-H. `virtual-judge-npc-real-env-unblock-decision` | 已完成（still_env_blocked） | 明确当前不得重跑 readiness gate、不得执行 LLM canary、不得进入 Beta |
| P4-I. `virtual-judge-npc-real-env-input-unblock-stage-closure` | 已完成 | 回写 completed/todo 并归档计划 |

## 3. 验证摘要

已执行：

1. 当前代码事实核验：chat route、NPC migration、npc_service provider / Kafka / runtime metrics 配置入口、notify replay 和权限口径。
2. `git diff --check`。
3. `bash scripts/quality/harness_docs_lint.sh`。

未执行：

1. 真实 provider 调用。
2. 真实 Kafka consumer / DLQ 查询。
3. 真实 dashboard / 日志查询。
4. 真实 frontend / notify / room canary。

## 4. 长期文档同步

1. `completed.md` 新增 B54 `virtual-judge-npc-real-env-input-unblock-stage-closure`。
2. `todo.md` C47 更新真实环境 canary/dashboard 债务来源和触发条件。
3. `当前开发计划.md` 重置为 default slot 空档。
4. `虚拟裁判NPC_开发计划.md` 重置为已收口索引。

## 5. 后续触发条件

只有当真实环境 owner evidence 补齐，并按脱敏模板输出 `ready_to_rerun_gate` 后，才允许新建计划重新执行真实环境 readiness gate。

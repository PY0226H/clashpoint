# 虚拟裁判 NPC 开发计划 Pending 留档

迁移时间：2026-05-04
来源：[虚拟裁判NPC_开发计划.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/虚拟裁判NPC_开发计划.md)
状态：等待真实 Beta/staging 环境输入就绪后恢复；当前不再作为 active 计划执行

---

# 虚拟裁判 NPC 开发计划

更新时间：2026-05-04
文档状态：pending，上一阶段已收口
当前主线：暂无 active 绑定

关联 PRD：[虚拟裁判NPC完整PRD.md](/Users/panyihang/Documents/EchoIsle/docs/PRD/虚拟裁判NPC完整PRD.md)
最近归档：[20260505T010800Z-virtual-judge-npc-real-env-input-unblock-stage-closure.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/虚拟裁判/20260505T010800Z-virtual-judge-npc-real-env-input-unblock-stage-closure.md)
完成快照：[completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md) B54
后置待办：[todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md) C47

---

## 1. 当前状态

虚拟裁判 NPC 真实环境输入解锁阶段已收口，结论为 `still_env_blocked`。

本阶段已经完成：

1. [真实环境输入 Owner 交付合同](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_真实环境输入Owner交付合同.md)
2. [真实环境 Evidence 脱敏模板](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_真实环境Evidence脱敏模板.md)
3. [Readiness Gate 重跑手册](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_ReadinessGate重跑手册.md)
4. [目标环境 Migration 与服务地图](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_目标环境Migration与服务地图.md)
5. [Kafka 与 Dashboard 交付合同](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_Kafka与Dashboard交付合同.md)
6. [Canary Session 与账号输入包](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_CanarySession与账号输入包.md)
7. [真实环境输入解锁 Decision](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_真实环境输入解锁Decision.md)

当前不得：

1. 重跑真实环境 readiness gate。
2. 执行真实 LLM canary。
3. 进入 Beta 小流量。
4. 将本地 mock、rule fallback、字段存在、配置入口存在或输入模板存在宣称为真实环境通过。

## 2. 后续触发条件

若后续真实 Beta/staging 输入齐备，需要新建开发计划并从以下动作开始：

1. 按 Owner 交付合同补齐真实环境 owner evidence。
2. 按 Evidence 脱敏模板确认所有证据可公开归档。
3. 按 Readiness Gate 重跑手册输出 `ready_to_rerun_gate`。
4. 再进入真实环境 readiness gate、单 session LLM canary、dashboard evidence 和 release decision。

若要推进 `soft_pause/hard_pause/resume` 强暂停状态机，需要先满足：

1. 产品明确确认强暂停 / 恢复需求和审批边界。
2. 真实 Beta/staging canary 与观测面板已具备。
3. 设计必须继续保证 NPC 不替代 AI 裁判团正式裁决。

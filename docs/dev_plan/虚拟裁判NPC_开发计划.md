# 虚拟裁判 NPC 下一阶段开发计划

更新时间：2026-05-04
文档状态：active，P1-B 已完成
当前主线：`virtual-judge-npc-real-env-input-unblock-pack`

关联 PRD：[虚拟裁判NPC完整PRD.md](/Users/panyihang/Documents/EchoIsle/docs/PRD/虚拟裁判NPC完整PRD.md)
关联系统设计：[虚拟裁判NPC_系统设计.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_系统设计.md)
关联 readiness 清单：[虚拟裁判NPC_Beta真实环境Readiness输入清单.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_Beta真实环境Readiness输入清单.md)
关联 dashboard 基线：[虚拟裁判NPC_CanaryDashboard查询与告警基线.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_CanaryDashboard查询与告警基线.md)
关联 preflight：[虚拟裁判NPC_Beta真实环境Preflight基线.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_Beta真实环境Preflight基线.md)
关联 readiness gate：[虚拟裁判NPC_Beta真实环境ReadinessGate证据.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_Beta真实环境ReadinessGate证据.md)
关联 release decision：[虚拟裁判NPC_Beta真实环境ReleaseDecision.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_Beta真实环境ReleaseDecision.md)
关联 Owner 交付合同：[虚拟裁判NPC_真实环境输入Owner交付合同.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_真实环境输入Owner交付合同.md)
上一阶段归档：[20260504T235621Z-virtual-judge-npc-beta-real-env-no-go-stage-closure.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/虚拟裁判/20260504T235621Z-virtual-judge-npc-beta-real-env-no-go-stage-closure.md)
完成快照：[completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md) B53
后置待办：[todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md) C47

---

## 1. 计划定位

本计划承接 B53 `virtual-judge-npc-beta-real-env-no-go-stage-closure`。

上一阶段结论已经明确：

1. 仓内 `pause_suggestion`、LLM/rule executor、guard、notify replay、前端展示和 smoke 已完成。
2. `npc_service` 已有 OpenAI-compatible provider、LLM canary、runtime metrics、Kafka consumer、DLQ、chat callback 等配置入口。
3. P1-B/P1-C/P2-G 已完成真实环境证据化，结论为 `env_blocked / no-go`。
4. 阻塞原因不是仓内功能缺口，而是真实 Beta / staging 输入缺失：服务入口、provider、Kafka、dashboard、canary session、测试账号、Ops 权限、回滚 owner、目标环境 migration 证据均未齐备。

因此下一阶段不重复跑 readiness gate，也不进入强暂停状态机，而是先做 **真实环境输入解锁与交付包**：

1. 把真实环境所需输入拆成 owner、格式、验收口径和脱敏证据模板。
2. 把“拿到输入后如何重新触发 P1-C”固化成可执行流程。
3. 把真实 canary 前必须完成的 migration、服务、Kafka、dashboard、账号、回滚窗口全部变成 checklist / handoff contract。
4. 在不接触真实 secret 的前提下，让下一次真实环境窗口可以直接进入 readiness gate，而不是再次因为输入散落而 no-go。

## 2. 当前代码事实快照

| 领域 | 当前事实 | 下一阶段影响 |
| --- | --- | --- |
| `chat` NPC fact source | `debate_npc_actions`、candidate handler、public call、feedback、OpenAPI 与 outbox/replay 已存在；`pause_suggestion` 已接入能力位与 guard | 下一阶段不改 action 合同，重点确认目标环境 migration 与内部 API 可用 |
| `npc_service` executor | `llm_executor_v1`、`rule_executor_v1`、canary 限制、成本/延迟 metrics、熔断、guard、`no_action`、fallback 均已有代码和测试 | 下一阶段只整理真实 provider 与 canary env 输入，不改变 executor 策略 |
| Event consumer | `NPC_EVENT_CONSUMER_ENABLED`、Kafka brokers/topic/group/client/DLQ 配置入口存在 | 下一阶段需要真实 topic prefix、consumer group、offset/lag/DLQ 查询入口 |
| OpenAI-compatible provider | `NPC_OPENAI_*` 配置入口存在，仓内有 mock provider 测试；真实 provider 未验证 | 下一阶段需要 provider owner、安全注入方式、模型、成本口径和脱敏响应证据 |
| Frontend / notify | Debate Room 已支持 NPC live / replay、观战只读和 `pause_suggestion` 展示 | 下一阶段需要真实 frontend/notify URL、参赛/观战账号、重连 replay 验证窗口 |
| 真实环境证据 | P1-C/P2-G 已判定 `env_blocked / no-go` | 下一阶段目标是让阻塞项具备可交付输入，而不是宣称 pass |

## 3. 冻结边界

本阶段继续遵守：

1. 虚拟裁判 NPC 永远不替代 AI 裁判团生成正式裁决报告。
2. 虚拟裁判 NPC 不输出胜负判定、阵营评分、正式裁决字段、judge trace 或 review queue 字段。
3. 用户不能私聊虚拟裁判 NPC。
4. `pause_suggestion` 只是公开建议，不改变房间状态、不禁用输入、不冻结倒计时。
5. 本阶段不实现 `soft_pause/hard_pause/resume` 强暂停状态机。
6. 不读取、不复制、不提交真实 secret、cookie、token、手机号、邮箱、密码或完整用户隐私文本。
7. 不把本地 mock、仓内 smoke、rule fallback、字段存在、配置文件存在宣称为真实环境通过。
8. 没有真实环境输入前，任何 release 结论仍只能保持 `env_blocked / no-go`。

## 4. 阶段目标

### 4.1 产品目标

1. 为虚拟裁判 NPC 进入真实 Beta 小流量前建立清晰的输入交付口径。
2. 让产品、运营、后端、前端、基础设施和模型 provider 各自知道需要交付什么证据。
3. 保护用户对娱乐 NPC 与正式 AI 裁判团裁决的区分，避免为了推进 canary 牺牲正式裁决隔离。

### 4.2 工程目标

1. 输出真实环境输入 handoff contract。
2. 输出脱敏 evidence 模板与 redaction policy。
3. 输出重新触发 P1-C readiness gate 的执行顺序。
4. 输出真实环境 migration / service / Kafka / dashboard / account / rollback owner 的缺口矩阵。
5. 若发现仓内文档、脚本或配置模板与当前代码不一致，只做最小文档修正；不扩展业务能力。

### 已完成/未完成矩阵

| 模块 | 目标 | 状态 | 说明 |
| --- | --- | --- | --- |
| P0-A. `virtual-judge-npc-real-env-input-unblock-plan-current-state` | 基于 PRD、module_design、B53/C47 和当前代码事实生成下一阶段计划 | 已完成 | 本文档即该模块输出；已绑定 default slot 执行 |
| P1-B. `virtual-judge-npc-real-env-input-owner-handoff-contract` | 生成真实环境输入 owner / 交付格式 / 验收口径清单 | 已完成 | 已输出 [Owner 交付合同](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_真实环境输入Owner交付合同.md)，面向工程、运营、基础设施、前端、模型 provider；不记录 secret |
| P1-C. `virtual-judge-npc-redacted-evidence-template-pack` | 生成脱敏 evidence 模板包 | 待执行 | 下一步建议执行；覆盖 service health、provider、Kafka、dashboard、账号、rollback、frontend/notify smoke |
| P1-D. `virtual-judge-npc-readiness-gate-rerun-playbook` | 生成重新触发 P1-C 的执行手册 | 待执行 | 明确输入齐备后如何从 `env_blocked` 切回 `ready` gate |
| P2-E. `virtual-judge-npc-target-env-migration-and-service-map` | 固化目标环境 migration / service / route / healthcheck 对照表 | 待执行 | 不执行真实迁移；只规定检查入口、命令和通过口径 |
| P2-F. `virtual-judge-npc-kafka-dashboard-query-contract` | 将 Kafka / DLQ / dashboard 查询需求转成可交付 contract | 待执行 | 明确 query owner、字段、截图 / export 口径和 P0/P1 告警 |
| P2-G. `virtual-judge-npc-canary-session-and-account-pack` | 定义 canary session、参赛/观战/Ops 账号、权限和数据合规输入包 | 待执行 | 不记录密码/token；只记录角色、权限和可验证入口 |
| P3-H. `virtual-judge-npc-real-env-unblock-decision` | 汇总输入交付状态，给出是否可重新触发 readiness gate 的结论 | 待执行 | 输出 `ready_to_rerun_gate / still_env_blocked` |
| P4-I. `virtual-judge-npc-real-env-input-unblock-stage-closure` | 阶段收口，回写 completed/todo 并归档计划 | 待执行 | 只在 P3-H 有结论后执行 |

### 下一开发模块建议

1. 默认下一步执行 P1-C `virtual-judge-npc-redacted-evidence-template-pack`。
2. 若后续输入收集发现真实环境 owner 无法明确，应在 P3-H 结论中保持 `still_env_blocked`，不生成可执行 canary。
3. 只有 P3-H 输出 `ready_to_rerun_gate` 后，才允许重新生成或恢复真实环境 readiness gate 计划。

## 5. 模块详情

### P0-A. `virtual-judge-npc-real-env-input-unblock-plan-current-state`

目标：

1. 基于最新 PRD、module design、B53 no-go 收口和当前代码事实生成下一阶段计划。
2. 明确本阶段是“输入解锁”，不是“真实 canary pass”。
3. 避免重复执行 P1-C 并再次得到同样的 `env_blocked`。

验收标准：

1. 计划包含执行矩阵、下一开发模块建议、冻结边界和模块 DoD。
2. 计划明确不读取 / 不提交真实 secret。
3. 计划明确真实输入齐备前不得进入 Beta 小流量。

### P1-B. `virtual-judge-npc-real-env-input-owner-handoff-contract`

目标：

1. 将真实环境 canary 输入拆成 owner / 交付物 / 验收口径。
2. 明确每类输入缺失时的阻塞结论。
3. 让下一次 P1-C 不再依赖口头信息或散落配置。

输出范围：

1. `docs/module_design/虚拟裁判NPC/虚拟裁判NPC_真实环境输入Owner交付合同.md`
2. 输入分类：
   - 环境与服务入口
   - provider 与模型
   - Kafka / event-bus / DLQ
   - dashboard / 日志
   - canary session 与测试账号
   - Ops 开关与回滚 owner
   - 目标环境 migration
3. 每项输入只记录 owner、脱敏摘要、证据位置和验收口径，不记录 secret。

验收标准：

1. 每个输入项都有明确 owner 或标记为 `owner_missing`。
2. 每个输入项都有交付格式和 pass / blocked 口径。
3. 合同能直接作为下一次 readiness gate 的前置 checklist。

完成结果：

1. 已输出 [虚拟裁判NPC_真实环境输入Owner交付合同.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/虚拟裁判NPC/虚拟裁判NPC_真实环境输入Owner交付合同.md)。
2. 合同按环境、provider、LLM canary、fallback、chat、migration、Kafka、dashboard、frontend/notify、账号、Ops 回滚和数据合规拆分 owner。
3. 合同明确当前真实输入仍为 `owner_missing / input_missing`，只能作为 P1-C/P1-D/P2 系列交付前置，不能宣称真实环境通过。

### P1-C. `virtual-judge-npc-redacted-evidence-template-pack`

目标：

1. 输出真实环境 evidence 模板。
2. 统一脱敏规则，避免把 secret、用户隐私或内部 token 粘贴进文档。

输出范围：

1. `docs/module_design/虚拟裁判NPC/虚拟裁判NPC_真实环境Evidence脱敏模板.md`
2. 模板覆盖：
   - `/healthz`
   - runtime metrics
   - provider 响应摘要
   - Kafka topic / group / offset / lag
   - DLQ
   - chat candidate accepted / rejected
   - notify live / replay
   - frontend 参赛 / 观战截图或 trace
   - rollback 前后快照

验收标准：

1. 模板明确允许记录字段和禁止记录字段。
2. 每个截图 / 日志 / export 都有脱敏要求。
3. 模板能支持 `pass / env_blocked / fail / rollback_required` 四种结论。

### P1-D. `virtual-judge-npc-readiness-gate-rerun-playbook`

目标：

1. 固化从输入齐备到重新触发 P1-C 的流程。
2. 避免直接跳到真实 LLM canary。

输出范围：

1. `docs/module_design/虚拟裁判NPC/虚拟裁判NPC_ReadinessGate重跑手册.md`
2. 执行顺序：
   - 输入完整性检查
   - secret 注入确认
   - 目标环境 migration 状态确认
   - service health
   - Kafka / DLQ / dashboard query
   - canary session / accounts / Ops rollback
   - dry-run no-go / ready 判定

验收标准：

1. 手册明确何时可以输出 `ready_to_rerun_gate`。
2. 手册明确任一关键项缺失时保持 `env_blocked`。
3. 手册明确不能绕过 P1-C 直接执行 P1-D。

### P2-E. `virtual-judge-npc-target-env-migration-and-service-map`

目标：

1. 把目标环境的迁移与服务检查入口整理成对照表。
2. 明确本机 DB pending 不能作为目标环境状态。

输出范围：

1. `docs/module_design/虚拟裁判NPC/虚拟裁判NPC_目标环境Migration与服务地图.md`
2. 对照：
   - `chat` migration 三条 NPC 相关 migration
   - `chat` internal NPC routes
   - `npc_service` `/healthz` 和 runtime metrics
   - `notify_server` WS live / replay
   - frontend web / desktop 指向环境
   - Ops 房间 NPC config

验收标准：

1. 每个检查项有目标环境命令 / URL 口径和通过标准。
2. 明确哪些检查需要审批或真实环境权限。
3. 不执行真实迁移，不记录真实连接串。

### P2-F. `virtual-judge-npc-kafka-dashboard-query-contract`

目标：

1. 把 dashboard 基线转换成真实环境 owner 可交付的 query contract。
2. 明确下一次 canary 需要哪些截图、export 或日志片段。

输出范围：

1. `docs/module_design/虚拟裁判NPC/虚拟裁判NPC_Kafka与Dashboard交付合同.md`
2. 覆盖字段：
   - executor kind / fallback reason
   - provider error code / latency / token / cost
   - callback accepted / rejected / failed
   - DLQ / retry exhausted
   - Kafka offset / lag
   - circuit state
   - notify replay gap

验收标准：

1. 每个 query 有 owner、入口、字段、时间窗口和脱敏要求。
2. 明确没有 dashboard 时允许的临时日志证据。
3. 明确缺任一 P0/P1 查询时不能判定 `pass`。

### P2-G. `virtual-judge-npc-canary-session-and-account-pack`

目标：

1. 定义 canary session、参赛账号、观战账号、Ops 权限和数据合规输入包。
2. 避免真实 canary 开始后才发现账号或房间状态不可用。

输出范围：

1. `docs/module_design/虚拟裁判NPC/虚拟裁判NPC_CanarySession与账号输入包.md`
2. 覆盖：
   - canary session 选择规则
   - 房间 NPC config 必需能力位
   - 正方 / 反方 / 观战 / Ops 角色
   - 数据合规确认
   - 回滚 owner 与窗口
   - 不记录密码、token、手机号、邮箱明文

验收标准：

1. 输入包能支持下一次真实环境 P1-C。
2. 能明确区分参赛和观战权限。
3. 能证明回滚 owner 有执行关闭动作的权限。

### P3-H. `virtual-judge-npc-real-env-unblock-decision`

目标：

1. 汇总 P1-B 到 P2-G 的输入交付状态。
2. 给出是否可以重新触发 P1-C readiness gate 的结论。

输出范围：

1. `docs/module_design/虚拟裁判NPC/虚拟裁判NPC_真实环境输入解锁Decision.md`
2. 结论只允许：
   - `ready_to_rerun_gate`
   - `still_env_blocked`

验收标准：

1. 若为 `ready_to_rerun_gate`，必须列出所有必需输入的证据位置。
2. 若为 `still_env_blocked`，必须列出缺失 owner、缺失输入和下一次触发条件。
3. 不允许直接输出真实环境 `pass`。

### P4-I. `virtual-judge-npc-real-env-input-unblock-stage-closure`

目标：

1. 将本阶段完成快照写入 `completed.md`。
2. 将仍未齐备的真实环境债务写入 `todo.md`。
3. 归档本计划并重置活动计划。

验收标准：

1. completed 只记录主体完成快照。
2. todo 只保留真实后置债，不复制活动计划正文。
3. 归档文档记录 `ready_to_rerun_gate` 或 `still_env_blocked`。
4. `harness_docs_lint.sh` 通过。

## 6. 验证策略

本阶段主要是文档与交付口径，不默认运行业务测试。

建议验证：

1. `git diff --check`
2. `bash scripts/quality/harness_docs_lint.sh`
3. 如新增脚本或配置模板，再补对应脚本自检或 dry-run。

## 7. 风险与处理

| 风险 | 影响 | 处理 |
| --- | --- | --- |
| owner 不明确 | 输入无法交付，继续 no-go | 在 handoff contract 标为 `owner_missing`，P3-H 输出 `still_env_blocked` |
| secret 泄漏 | 安全与合规风险 | evidence 模板只允许脱敏摘要，禁止粘贴 key/token/cookie/password |
| 文档与当前代码 env 不一致 | 下一次 gate 使用错误字段 | P1-B/P2-E 必须引用 `npc_service/app/settings.py` 当前字段 |
| 误把输入解锁当成 canary pass | release 风险 | P3-H 只允许 `ready_to_rerun_gate / still_env_blocked` |
| 过早进入强暂停 | 产品边界风险 | 强暂停仍保留到 C47 后置债，等待真实环境证据和产品确认 |

## 8. 执行决策点

1. P1-B 若 owner 缺失严重：可以直接进入 P3-H 输出 `still_env_blocked`。
2. P1-C/P1-D/P2-E/P2-F/P2-G 若全部完成且输入齐备：P3-H 输出 `ready_to_rerun_gate`。
3. P3-H 若输出 `ready_to_rerun_gate`：下一阶段重新触发 P1-C readiness gate。
4. P3-H 若输出 `still_env_blocked`：进入 P4-I 收口并继续保留 C47。

### 模块完成同步历史

1. 2026-05-04：生成 `virtual-judge-npc-real-env-input-unblock-pack` 下一阶段开发计划；P0-A 已完成，下一步建议执行 P1-B。
2. 2026-05-04：执行 P1-B `virtual-judge-npc-real-env-input-owner-handoff-contract`，新增 Owner 交付合同；下一步建议执行 P1-C 脱敏 evidence 模板包。

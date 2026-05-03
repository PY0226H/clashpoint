# 当前开发计划

关联 slot：`default`
更新时间：2026-05-02
当前主线：`ai-judge-official-verdict-plane-local-stability-pack`
当前状态：已完成 P0-A 官方裁决合同回归补强、P0-B real-env evidence drift guard、P1-C readiness 三层一致性补强与 P1-D 本地参考回归证据刷新；本地参考基线稳定，下一步可进入 stage closure，或先执行 P2-E 轻量热点审计；真实环境未提供，real-env pass 后置；`NPC Coach` / `Room QA` 继续暂停

---

## 1. 计划定位

1. 本计划基于当前工作区代码事实、[AI_Judge_Service-架构与技术栈决策方案-2026-04-13.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/AI_Judge_Service-架构与技术栈决策方案-2026-04-13.md) 与 [AI_Judge_Service-企业级Agent服务设计方案-2026-04-13.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/AI_Judge_Service-企业级Agent服务设计方案-2026-04-13.md) 生成。
2. 上一阶段 `ai-judge-real-env-readiness-prep-stage-closure` 已完成，完整计划已归档到：[20260501T223857Z-ai-judge-real-env-readiness-prep-stage-closure.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260501T223857Z-ai-judge-real-env-readiness-prep-stage-closure.md)。
3. 主体完成快照已写入 [completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md) B47；真实环境后置债已写入 [todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md) C46。
4. 当前没有真实环境，下一轮不进入 real-env pass，不把 `local_reference`、mock provider/callback 或手工 ready 写成 real-env `pass`。
5. `NPC Coach` / `Room QA` 已按产品决策暂停；本计划不删除历史实现、不继续开发、不接真实 LLM executor，仅保持官方 `Judge App` / `Official Verdict Plane` 主线。

## 2. 当前代码事实快照

| 领域 | 当前事实 | 计划影响 |
| --- | --- | --- |
| 官方 Judge 主入口 | [judge_command_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_command_routes.py) 约 2204 行，[judge_dispatch_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_dispatch_runtime.py) 约 180 行，[judge_mainline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_mainline.py) 约 61 行 | 官方裁决链仍是可继续推进的主线；下一步优先补合同回归与入口防漂移，不做新产品面 |
| 8 Agent / 法庭式角色 | [judge_workflow_roles.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_workflow_roles.py) 约 1485 行，已承载 Clerk/Recorder/Claim/Evidence/Panel/Fairness/Arbiter/Opinion 角色语义 | 下一轮重点确认角色顺序、fact lock、fairness sentinel 与 arbiter 边界没有被后续治理面改动污染 |
| chat_server 裁判门面 | [debate_judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_judge.rs) 约 1589 行，已包含 judge job、report、public verify、challenge 与 assistant advisory 路由 | 本轮不扩展 assistant advisory；只检查官方裁判 job/report/public verify/challenge 合同是否稳定 |
| AI 服务装配热点 | [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) 约 2346 行，仍是装配与 route 聚合热点 | 本轮只做必要维护；若发现第一跳定位继续变差，单独拆分小 helper，不做大重构 |
| trust / readiness / fairness 证据链 | [ops_trust_monitoring.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_trust_monitoring.py)、[release_readiness_projection.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/release_readiness_projection.py)、[registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py) 已形成 release/readiness 汇总 | 下一轮优先防止 `local_reference_ready` 与 `pass` 混淆，保持 real-env 缺口透明 |
| 真实环境状态 | [ai_judge_artifact_store_healthcheck.json](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_artifact_store_healthcheck.json) 当前为 `provider=local`、`status=local_reference`、`productionReady=false`；[ai_judge_real_env_window_closure.md](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_real_env_window_closure.md) 当前为 `env_blocked` | 不执行真实环境 pass；只维护 preflight、输入模板、阻塞证据与本地参考回归 |
| 前端 / Ops 控制面 | [runtimeReadiness.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/ops-domain/src/runtimeReadiness.ts)、[OpsConsolePage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/OpsConsolePage.tsx) 已有 runtime readiness 展示 | 如后续改动 readiness payload，必须同步 domain resolver 与页面展示；本计划优先检查一致性 |
| Interactive Guidance 历史资产 | `assistant_*`、`route_group_assistant.py`、`DebateAssistantPanel.tsx` 等代码仍存在，但方案与计划均标记暂停 | 不删除、不推进、不作为下一步验收口径 |

> 说明：上表的代码事实来自当前工作区文件扫描与行数核验；若文档与代码发生冲突，后续开发以代码事实为准，并在计划/完成度映射中留痕。

## 3. 与方案的对齐判断

1. 架构方案当前有效主线是 `Official Verdict Plane`：模块化单体、客户端只经 `chat_server`、AI 服务作为内部服务、官方裁决链强审计/强证据/强版本化。
2. 企业级 Agent 设计方案的 Phase 1 / Phase 2 / Phase 3 已完成到“本地参考闭环 + 产品桥接 + release/readiness 控制面 + real-env readiness 本地准备”的阶段。
3. Verifiable Trust Layer 已具备本地 artifact store、audit/public verify、challenge/review、healthcheck evidence CLI、preflight-only 门禁与 readiness input template；真实对象存储 roundtrip、真实样本与真实 provider/callback 仍是 C46。
4. Interactive Guidance Plane 的 `NPC Coach` / `Room QA` 只保留历史事实与未来复用资产，不进入当前开发计划。

## 4. 完成度与缺口矩阵

### 已完成/未完成矩阵

| 模块 | 目标 | 状态 | 说明 |
| --- | --- | --- | --- |
| `ai-judge-next-iteration-planning-current-state` | 生成下一轮完整开发计划并同步完成度映射 | 已完成 | 已根据当前代码、两份方案、B47/C46 与暂停边界生成本计划，并同步章节完成度映射 |
| Enterprise MVP | 维持 8 Agent 官方裁决主链与基础产品闭环 | 已完成 | 8 Agent 官方裁决主链、ledger、workflow、trace/replay、report、public verify、challenge/review 产品桥接均已形成 |
| Fairness Hardened | 维持公平门禁与 release/readiness 控制面 | 进行中 | fairness gate、panel disagreement、local reference benchmark/freeze、release gate 与 runtime readiness 控制面已具备；真实样本实跑后置 |
| Adaptive Judge Platform | 维持 gateway/registry/ops/readiness 平台能力 | 进行中 | gateway/registry/ops/readiness/release evidence/panel candidate/calibration decision log 已推进；auto-calibration、多模型生产切换与真实环境 pass 后置 |
| Verifiable Trust Layer | 维持本地参考可信外部化与 real-env readiness 输入门禁 | 进行中 | healthcheck evidence CLI、preflight-only、输入模板与证据门禁已完成；生产对象存储真实执行后置 |
| Interactive Guidance Plane | 保持暂停，不进入当前开发 | 阻塞 | `NPC Coach` / `Room QA` 不进入下一步，不做 executor、ready-state、成本/延迟 guard 或 Ops evidence |
| P0-A. ai-judge-official-verdict-contract-regression-pack | 保护官方裁决合同 | 已完成 | 官方 judge job / challenge 请求体已改为拒绝未知字段，防止 assistant/advisory 或直接 verdict mutation 字段被静默吞入官方裁决入口；targeted tests 与 full gate 通过 |
| P0-B. ai-judge-real-env-evidence-drift-guard-pack | 保护 local_reference / real-env pass 边界 | 已完成 | real-env preflight 不再接受缺 evidence 链接的 READY=true、缺 healthcheck evidence 的 artifact ready、local_reference 污染对象存储 evidence；当前 evidence 已刷新为 env_blocked |
| P1-C. ai-judge-runtime-ops-readiness-consistency-pack | 对齐 AI/chat/frontend readiness 展示 | 已完成 | AI -> chat -> frontend 现在保留 envBlockedComponents、realEnvEvidenceStatusCounts、artifact store 与 action status 等关键 readiness 状态；Ops Console 不再只显示 reasonCodes |
| P1-D. ai-judge-local-reference-regression-refresh-pack | 刷新本地参考回归证据 | 已完成 | 本地参考基线已刷新，runtime ops pack=local_reference_ready，real-env evidence closure=local_reference_ready，stage closure evidence=pass，real-env preflight=env_blocked；未触碰 NPC Coach / Room QA |

## 5. 下一轮开发模块拆分

### 下一开发模块建议

1. P1-D 已完成且本地参考证据稳定；若需要再做轻量第一跳热点审计可进入 P2-E
2. 否则可进入 stage closure；真实环境 pass 继续等待 C46

### P0-A. `ai-judge-official-verdict-contract-regression-pack`

目标：

1. 保护官方裁决链不被后续 readiness、assistant advisory 或 ops 控制面改动污染。
2. 固化 8 Agent 角色顺序、official verdict 输出边界、fact lock、公验与 challenge/review 只读/受控写入语义。
3. 在无真实环境下，用本地合同回归证明官方裁判主链仍可稳定运行。

执行范围：

1. AI 服务：`judge_command_routes.py`、`judge_dispatch_runtime.py`、`judge_mainline.py`、`judge_workflow_roles.py`、`final_report.py`、`public_verify_projection.py`、`trust_*` 合同文件。
2. chat_server：`debate_judge.rs` 里官方 judge job、report、final report、public verify、challenge 相关路由。
3. 前端/共享包：`debate-domain`、`OpsConsolePage` 中只读展示与官方裁决报告读取路径。

开发步骤：

1. 盘点现有 AI / Rust / frontend 测试，确认是否已有覆盖：8 Agent role runtime、final report fact lock、public verify、challenge request、report read permission。
2. 对缺口补最小合同测试，优先覆盖负向路径：非参与者读取、assistant/advisory 字段不得进入 official verdict、公验 projection 不暴露内部字段、review/challenge 不反向改写 locked verdict。
3. 若发现测试只能通过私有实现细节断言，改为通过公开 route/service/domain 合同触达。
4. 运行 targeted 测试，记录实际命令与结果；若环境阻塞，写清楚阻塞原因。

验收标准：

1. 官方 `pro / con / draw / review required / blocked failed` 语义不变。
2. `NPC Coach` / `Room QA`、assistant advisory、calibration advice 不具备官方裁决写权。
3. 关键合同有本地测试或可复现 evidence 保护。
4. 未引入长期兼容层、alias 字段或双写路径。

完成同步：

1. 已在 [types.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/types.rs) 为 `RequestJudgeJobInput` 与 `RequestJudgeChallengeInput` 增加未知字段拒绝，避免官方入口静默吞入 advisory/verdict mutation 字段。
2. 已在 [request_judge_job.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/tests/request_judge_job.rs) 增加两个负向合同测试，覆盖 `winner` 与 `verdictEffect` / `writesVerdictLedger` 这类不应进入官方请求体的字段。
3. 已通过 targeted tests 与 `post-module-test-guard --mode full`；本次未改变模块边界、主入口或第一跳定位，因此无需更新 [docs/architecture/README.md](/Users/panyihang/Documents/EchoIsle/docs/architecture/README.md)。

### P0-B. `ai-judge-real-env-evidence-drift-guard-pack`

目标：

1. 防止未来误把 `local_reference`、`local_reference_ready`、mock provider 或手工 ready 记成 real-env `pass`。
2. 让 real-env readiness 输入模板、healthcheck evidence、preflight-only 输出与完成度映射保持一致。

执行范围：

1. [ai_judge_real_env_window_closure.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_real_env_window_closure.sh)
2. [test_ai_judge_real_env_window_closure.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/tests/test_ai_judge_real_env_window_closure.sh)
3. [ai_judge_real_env_readiness_inputs.env.example](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_real_env_readiness_inputs.env.example)
4. [ai_judge_real_env_readiness_inputs_checklist.md](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_real_env_readiness_inputs_checklist.md)
5. [ai_judge_artifact_store_healthcheck.json](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_artifact_store_healthcheck.json) 与 real-env closure 输出。

开发步骤：

1. 增加或核验测试场景：本地 provider evidence 必须输出 `productionReady=false` 与 `env_blocked`。
2. 增加或核验测试场景：缺少 production artifact store evidence 时，`--preflight-only` 不接受手工 `PRODUCTION_ARTIFACT_STORE_READY=true`。
3. 增加或核验测试场景：只有 `productionReady=true` 且真实输入齐备时才允许进入 `preflight_ready`。
4. 若脚本输出、清单和完成度映射字段名称不一致，统一命名并更新文档。

验收标准：

1. `local_reference` 不能被任何脚本、文档或汇总 JSON 误判为 `pass`。
2. C46 的真实环境缺口能从 evidence、plan、mapping 三处同时反查。
3. `--preflight-only` 是真实环境窗口前的强制入口，不触发 P5/runtime ops 子阶段。

完成同步：

1. 已在 [ai_judge_real_env_window_closure.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_real_env_window_closure.sh) 强制校验 `*_READY=true` 必须具备对应 `*_EVIDENCE` 链接，避免只靠手工布尔值进入 `preflight_ready`。
2. 已收紧生产对象存储 healthcheck evidence：必须 `productionReady=true`、`provider!=local` 且 roundtrip 为 `pass`；污染的 `local_reference` evidence 即使写成 `productionReady=true` 也会 fail-closed。
3. 已在 [test_ai_judge_real_env_window_closure.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/tests/test_ai_judge_real_env_window_closure.sh) 增加缺 evidence 链接与污染 local reference healthcheck 两类负向回归。
4. 已刷新 [ai_judge_real_env_window_closure.env](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_real_env_window_closure.env) 与 [ai_judge_real_env_window_closure.md](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_real_env_window_closure.md)，当前仍为 `env_blocked`，并明确对象存储 evidence 为 `provider=local` / `production_artifact_store_local_reference`。

### P1-C. `ai-judge-runtime-ops-readiness-consistency-pack`

目标：

1. 保证 AI 服务 runtime readiness projection、chat_server proxy、frontend ops-domain resolver 与 Ops Console 呈现的阻塞状态一致。
2. 保证 release gate / fairness / panel / trust / artifact store / real-env evidence 的状态分类不会跨层漂移。

执行范围：

1. AI 服务：`release_readiness_projection.py`、`ops_trust_monitoring.py`、`runtime_readiness_public_projection.py`。
2. chat_server：runtime readiness ops projection/proxy 相关模型与 handler。
3. frontend：`frontend/packages/ops-domain/src/runtimeReadiness.ts`、相关 tests、`OpsConsolePage.tsx`。

开发步骤：

1. 对齐字段：`envBlockedComponents`、`realEnvEvidenceStatusCounts`、artifact store readiness、panel candidate blockers、calibration action status。
2. 通过固定 fixture 或现有本地 evidence 验证三层同一输入下的展示结论一致。
3. 若发现前端容错吞掉 blocker，改为显式展示 `env_blocked` 或 `local_reference`。
4. 仅在发生真实契约变化时同步 OpenAPI / DTO / SDK / tests。

验收标准：

1. Ops Console 不会把真实环境阻塞渲染成 ready/pass。
2. AI -> chat -> frontend 的字段含义单一，不保留未发布旧字段 alias。
3. 本地参考 evidence 在 UI 与 ops-domain 中都被视为参考态，不是生产就绪态。

完成同步：

1. 已在 [runtime_readiness_public_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/runtime_readiness_public_contract.py) 增加 `realEnvEvidenceStatusCounts` public payload 归一化，保留真实环境 evidence 状态计数。
2. 已在 [request_judge_report_query.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/tests/request_judge_report_query.rs) 固化 chat proxy 透传 `envBlockedComponents` 与 `realEnvEvidenceStatusCounts` 的合同回归。
3. 已在 [runtimeReadiness.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/ops-domain/src/runtimeReadiness.ts) 与 [OpsConsolePage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/OpsConsolePage.tsx) 显式展示 blocked components、evidence states、artifact store、challenge lag 与 action status，避免只显示 reasonCodes。
4. 已通过 AI targeted、chat targeted、frontend typecheck/lint/test 与 `post-module-test-guard --mode full`；本次不改变第一跳定位，因此无需更新 [docs/architecture/README.md](/Users/panyihang/Documents/EchoIsle/docs/architecture/README.md)。

### P1-D. `ai-judge-local-reference-regression-refresh-pack`

目标：

1. 在不具备真实环境时，刷新官方 Judge 本地参考回归证据。
2. 为后续进入 stage closure 或等待真实环境窗口提供可信本地基线。

执行范围：

1. AI targeted / full tests。
2. chat_server 官方 judge route targeted tests。
3. frontend debate-domain / ops-domain / app-shell targeted tests。
4. harness：real-env evidence closure、runtime ops pack、plan consistency gate、harness docs lint。

执行步骤：

1. 先跑最小 targeted gate，避免把环境问题扩散成大面积失败。
2. 若 targeted green，再跑 full 或接近 full 的本地参考回归。
3. 更新 evidence summary，不覆盖真实环境缺口。
4. 若出现失败，优先判断是产品/合同预期、真实 bug 还是环境缺失，再决定修实现、修测试或记录阻塞。

验收标准：

1. 本地参考回归通过，或失败原因被明确归类。
2. 证据文档只写本地参考结论，不写 real-env pass。
3. 当前计划、completed/todo、完成度映射保持一致。

完成同步：

1. 已刷新 [ai_judge_local_reference_regression_refresh.md](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_local_reference_regression_refresh.md) 与对应 `.env` 摘要，明确本地参考回归 `pass`，但 real-env pass ready 仍为 `false`。
2. 已刷新 runtime ops pack、real-env evidence closure、real-env window preflight 与 stage closure evidence：`runtime_ops_pack=local_reference_ready`、`real_env_evidence_closure=local_reference_ready`、`real_env_window=env_blocked`、`stage_closure_evidence=pass`。
3. 已补 [当前开发计划.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md) 的六项一致性检查，并通过 `ai_judge_plan_consistency_gate`。
4. 已通过 AI ruff/full pytest、chat judge job/report targeted、frontend debate-domain/ops-domain/app-shell test/typecheck/lint、harness evidence tests 与 `post-module-test-guard --mode full`；本轮只刷新证据与计划，不改变第一跳定位，因此无需更新 [docs/architecture/README.md](/Users/panyihang/Documents/EchoIsle/docs/architecture/README.md)。

### P2-E. `ai-judge-route-hotspot-map-audit-pack`

目标：

1. 在不启动大重构的前提下，识别下一轮最值得拆分的第一跳定位热点。
2. 只在影响“第一跳定位”时更新 [docs/architecture/README.md](/Users/panyihang/Documents/EchoIsle/docs/architecture/README.md)。

候选热点：

1. `app_factory.py`：route 装配与 wiring 聚合仍偏重。
2. `judge_command_routes.py`：phase/final dispatch route guard 与 payload 逻辑集中。
3. `debate_judge.rs`：官方 report/challenge/public verify 与 assistant advisory 历史入口同文件。

验收标准：

1. 输出轻量 hotspot map 或拆分建议。
2. 若不拆代码，只更新计划/说明；若拆代码，必须同步 architecture map 与测试。
3. 不借热点拆分继续推进 `NPC Coach` / `Room QA`。

## 6. 明确不做与阻塞项

1. 不执行 real-env pass：缺真实对象存储、真实样本 manifest、真实 provider、真实 callback 与真实服务窗口。
2. 不把 [ai_judge_artifact_store_healthcheck.json](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_artifact_store_healthcheck.json) 的本地结果写成生产通过。
3. 不继续 `ai-judge-p43-assistant-*`、`NPC Coach`、`Room QA`、用户辩论助手、低延迟交互型 Agent 或 assistant real LLM executor。
4. 不删除 `NPC Coach` / `Room QA` 历史实现；这些内容已暂停，未来是否复用等待独立 PRD 和模块设计。
5. 不进入 Protocol Expansion：Identity Proof、Constitution Registry、Reason Passport、第三方 review network、on-chain anchor 继续后置。

## 7. 推荐执行顺序

1. `ai-judge-official-verdict-contract-regression-pack` 已完成，官方裁决请求入口合同已有负向回归保护。
2. `ai-judge-real-env-evidence-drift-guard-pack` 已完成，`local_reference` / real-env `pass` 边界已有 preflight 证据门禁保护。
3. `ai-judge-runtime-ops-readiness-consistency-pack` 已完成，AI、chat、frontend 三层 readiness 阻塞信号与展示已对齐。
4. `ai-judge-local-reference-regression-refresh-pack` 已完成，本地参考证据已刷新且 real-env window 仍明确为 `env_blocked`。
5. 下一步可进入 stage closure；若需要先做轻量第一跳定位复核，再执行 `ai-judge-route-hotspot-map-audit-pack`。

## 8. 风险与控制

| 风险 | 控制方式 |
| --- | --- |
| 把本地参考证据误写成 real-env pass | P0-B 强化 preflight/evidence guard；所有计划与映射使用 `env_blocked` / `local_reference` 明确标注 |
| assistant 历史入口污染官方裁判 | P0-A 合同测试覆盖 forbidden official verdict output 与只读/受控写入边界 |
| readiness 三层字段漂移 | P1-C 使用固定 fixture 或现有 evidence 对齐 AI -> chat -> frontend |
| 热点文件继续膨胀 | P2-E 只做第一跳定位级拆分建议；不在无测试保护下大重构 |
| 真实环境突然开放 | 暂停本地维护包，按 C46 与 readiness checklist 先补证、healthcheck、`--preflight-only`，再进入 real-env window |

## 9. 一致性检查

1. 角色一致性：当前只推进官方 `Judge App` / `Official Verdict Plane`，8 Agent 官方裁决角色仍由 Clerk/Recorder/Claim/Evidence/Panel/Fairness/Arbiter/Opinion 主链承载；`NPC Coach` / `Room QA` 保持暂停且不具备官方裁决写权。
2. 数据一致性：本地参考证据统一使用 `local_reference` / `local_reference_ready` / `env_blocked` 口径，不把本地对象存储、mock provider、手工 ready 或 placeholder 结果写成 real-env `pass`。
3. 门禁一致性：P0-B 已强化 real-env preflight/evidence guard；P1-D 只刷新本地参考回归、runtime ops pack、stage closure evidence 与计划一致性 gate，真实环境窗口仍需 C46 输入和 production artifact store roundtrip 证据。
4. 边界一致性：官方裁决、public verify、challenge/review 与 Ops readiness 继续走 AI service -> chat_server -> frontend 的既有边界；本轮不新增 assistant executor、不扩展用户辩论助手、不引入 Protocol Expansion。
5. 跨层一致性：P1-C 已对齐 AI public payload、chat proxy 与 frontend Ops Console 的 readiness 阻塞展示；P1-D 通过 AI/chat/frontend/harness 本地回归刷新验证这些字段不跨层漂移。
6. 收口一致性：若 P1-D 本地参考回归与证据门禁通过，下一步可在仍无真实环境时进入 P2-E hotspot audit 或 stage closure；真实对象存储、真实样本、真实 provider/callback 与 real-env pass 继续后置。

## 10. 模块完成同步历史

### 模块完成同步历史

- 2026-05-01：推进 `ai-judge-real-env-readiness-prep-stage-closure`；完成官方 AI Judge real-env readiness 本地准备阶段收口，活动计划已归档并重置，真实环境 pass 后置到 `todo.md` C46。
- 2026-05-01：完成 `ai-judge-next-iteration-planning-current-state`；基于当前代码事实、两份方案、B47/C46、真实环境状态与 `NPC Coach` / `Room QA` 暂停边界，生成 `ai-judge-official-verdict-plane-local-stability-pack` 下一轮开发计划。
- 2026-05-01：推进 `P0-A. ai-judge-official-verdict-contract-regression-pack`；完成官方裁决请求合同回归补强：RequestJudgeJobInput 与 RequestJudgeChallengeInput 拒绝未知裁决/挑战写入字段，新增负向合同测试并通过 full test gate；未触碰 NPC Coach / Room QA
- 2026-05-02：推进 `P0-B. ai-judge-real-env-evidence-drift-guard-pack`；完成 real-env evidence drift guard：preflight 强制 *_READY 对应 evidence 链接，生产对象存储 healthcheck 必须 provider!=local 且 roundtrip=pass，污染的 local_reference productionReady=true 会 fail-closed；当前工作区 preflight 输出仍为 env_blocked
- 2026-05-02：推进 `P1-C. ai-judge-runtime-ops-readiness-consistency-pack`；完成 runtime readiness 三层一致性补强：AI public payload 暴露 realEnvEvidenceStatusCounts，chat proxy 回归保证 realEnv blockers/counts 透传，frontend Ops Console 显示 blocked components、evidence states、artifact store/challenge lag/action status；未触碰 NPC Coach / Room QA
- 2026-05-02：推进 `P1-D. ai-judge-local-reference-regression-refresh-pack`；完成官方 AI Judge 本地参考回归刷新：AI ruff/full pytest、chat judge job/report targeted、frontend debate-domain/ops-domain/app-shell test/typecheck/lint、runtime ops pack、real-env evidence/window closure、stage closure evidence、plan consistency gate 与 full Rust gate 均通过；real-env window 仍为 env_blocked

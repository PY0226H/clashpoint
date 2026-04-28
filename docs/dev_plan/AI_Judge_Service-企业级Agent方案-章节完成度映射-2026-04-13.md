# AI_Judge_Service 企业级 Agent 方案章节完成度映射（2026-04-13）

更新时间：2026-04-28
状态：已更新（对齐 P40 stage closure；P41 runtime readiness、calibration decision log、panel shadow candidate contract 与 release readiness ops evidence 已落地）
映射对象：[AI_judge_service 企业级 Agent 服务设计方案（2026-04-13）](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/AI_Judge_Service-企业级Agent服务设计方案-2026-04-13.md)

## 1. 判定口径

1. 已落地：主链代码已存在，且可通过当前测试、收口证据或本地参考回归验证。
2. 基本落地：主链已闭环，仍有运营化、真实环境、生产对象存储或平台化增强项。
3. 部分落地：主链能力已出现，但仍缺关键子能力、持久化事实源、产品门面或治理闭环。
4. 未落地：当前仅为设计目标，仓库内无对应主链实现。
5. 环境阻塞：实现入口存在，但最终验收依赖真实环境、真实样本、真实对象存储或 on-env 窗口。

## 2. 当前总进度判断

| 维度 | 当前阶段 | 结论 |
| --- | --- | --- |
| Enterprise MVP（方案 Phase 1） | 基本落地 | 8 Agent 官方裁决主链、六对象 ledger、durable workflow、trace/replay、review/audit、富裁决报告、public verification、受约束 challenge/review 产品桥接与本地回归闭环已形成 |
| Fairness Hardened（方案 Phase 2） | 基本落地（环境阻塞项除外） | Fairness gate、panel disagreement、local reference benchmark/freeze、真实样本 benchmark readiness、panel shadow evaluation、normalized fairness/panel evidence、citation verifier evidence gate、release gate 输入、runtime readiness Ops 产品面与 panel candidate 安全合同已完成；真实样本实跑与真实环境 pass 仍待窗口 |
| Adaptive Judge Platform（方案 Phase 3） | 部分落地（高） | gateway core、policy/prompt/tool registry、ops read model、registry release gate、release readiness artifact、panel runtime readiness、runtime ops closure backfill、chat/frontend runtime readiness 控制面、calibration decision log、panel shadow candidate contract 与 P41 release evidence 已推进；auto-calibration、多模型 panel 生产切换与 domain-specific judge families 仍后置 |
| Verifiable Trust Layer（方案第15章 Phase A/B） | 基本落地（本地参考 + 产品桥接） | Trust registry、artifact store、audit anchor、public verification、challenge/review registry、chat proxy、client read model、challenge ops queue 与 review decision sync 已接入主业务面；生产对象存储真实验收与 real-env pass 仍待窗口 |
| Protocol Expansion Layer（方案第15章 Phase C-D） | 未进入主线 | Identity Proof、Constitution Registry、Reason Passport、第三方 review network、on-chain anchor 均不属于当前 P41 主线；在 Fairness/Adaptive Ops 控制面稳定前不得进入单场官方裁决输入 |
| 真实环境闭环 | 环境阻塞 | 当前证据仍为 `local_reference_ready` / `env_blocked`；缺真实样本、真实 provider/callback、生产对象存储与真实服务窗口，不得宣称 real-env `pass` |

一句话结论：

`截至当前 P41 交付，AI Judge 已完成“制度化裁判庭 + 本地可信外部化 + public verification 产品面 + 受约束 challenge/review 用户与 Ops 基础桥接 + runtime readiness Ops 控制面首屏 + calibration recommendation 人工决策日志 + panel shadow candidate 安全合同 + P41 release evidence 归一”。下一步从“证据能否串联”转为“热点拆分、本地参考回归与阶段收口”。真实环境 pass 与远期协议扩展继续后置。`

## 3. 章节级完成度总览

| 方案章节 | 目标摘要 | 当前完成度 | 核心证据 | 结论 |
| --- | --- | --- | --- | --- |
| 1. 一句话结论 | 从“评分器”升级为“裁判庭系统” | 基本落地 | [P40 归档](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260428T065429Z-ai-judge-stage-closure-execute.md), [completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md) | 裁判庭主链、可信制度层、公验、challenge/review 产品桥接均已成型；P41 转向 runtime/fairness/adaptive Ops 控制面 |
| 2. 产品目标重新定义 | 丰富判决展示、公正、可运营 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [debate_judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_judge.rs), [DebateRoomPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/DebateRoomPage.tsx), [OpsConsolePage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/OpsConsolePage.tsx) | 用户报告、公验、challenge 状态/request、review decision sync、Ops challenge queue、runtime readiness 首屏、calibration decision log 与 panel candidate 摘要已具备；下一步补 release evidence 收口 |
| 3. 为什么必须是 Agent | 分工、状态、工具、门禁 | 基本落地 | [judge_workflow_roles.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_workflow_roles.py), [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py) | 8 Agent role runtime 与 advisory shell 均已出现；P41 不改官方裁决链，只补治理控制面 |
| 4. 总体设计理念 | 公平优先、事实先锁定、可回放 | 基本落地 | [trace_store_boundaries.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/trace_store_boundaries.py), [ai_judge_stage_closure_evidence.md](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_stage_closure_evidence.md) | locked verdict、opinion fact lock、trace/replay/audit、public verification 与 challenge/review 本地参考闭环已接通；real-env 仍阻塞 |
| 5. 推荐架构总览 | 法庭式流水线 + Ops/Replay/Audit | 基本落地 | [app/](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app), [route_group_trust.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_trust.py), [request_report_query.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/request_report_query.rs) | 模块化单体、route group、chat proxy 与 ops projection 架构稳定；P41 继续将 runtime readiness 下沉为薄装配 |
| 6. 法庭式 Agent 分工 | 8 类 Agent 职责闭环 | 基本落地 | 见“第4节 Agent 子项映射” | 官方裁决链角色齐备；多模型 panel 生产化、真实样本 benchmark 与 auto-calibration 仍是增强项 |
| 7. 企业级核心数据对象 | Case/Claim/Evidence/Verdict/Fairness/Opinion | 基本落地 | [ledger_objects.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/ledger_objects.py), [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py), [s3_store.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/artifacts/s3_store.py) | 六对象 typed snapshot、Artifact refs/manifest、S3-compatible adapter 与 release artifact 已落地；生产对象存储 roundtrip 待环境 |
| 8. 丰富判决内容 | 用户层/高级层/Ops 层展示 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [debate-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/debate-domain/src/index.ts), [OpsConsolePage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/OpsConsolePage.tsx) | 用户报告、公验、challenge/review 状态、review sync 与 runtime readiness Ops 面板已展示；后续补人工治理动作闭环 |
| 9. 公平性保证机制 | 盲化、镜像、扰动、复核、benchmark | 基本落地（环境阻塞项除外） | [fairness_analysis.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_analysis.py), [runtime_readiness_public_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/runtime_readiness_public_contract.py), [OpsConsolePage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/OpsConsolePage.tsx), [registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py) | 本地 reference freeze、真实样本 readiness、panel shadow evaluation、normalized evidence、citation verifier、release gate 输入、panel candidate blockers 与 Ops 控制面已达成；真实样本实跑待环境 |
| 10. 企业级工程架构 | Gateway/Orchestrator/Runtime/Ledger/Ops | 基本落地 | [orchestrator.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/core/workflow/orchestrator.py), [route_group_ops_read_model_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_ops_read_model_pack.py), [debate_ops.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_ops.rs), [ops-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/ops-domain/src/index.ts) | Postgres workflow、gateway core、ledger/read model、artifact store、ops pack、release evidence、chat/frontend runtime readiness productization、durable calibration decision log、panel candidate contract 与 P41 control-plane evidence 已出现 |
| 11. Agent Runtime 设计 | Prompt/Tool/Policy Registry + Model Gateway | 部分落地（高） | [policy_registry.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/policy_registry.py), [registry_product_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_product_runtime.py), [route_group_registry.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_registry.py), [registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py) | registry、gateway trace、publish/activate/rollback、release readiness artifact、panel shadow readiness 与 candidate contract 已进入内部主链；auto-calibration、多模型 production rollout 仍后置 |
| 12. 企业级可靠性要求 | 幂等、callback、trace、replay、观测 | 基本落地 | [callback_client.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/callback_client.py), [replay_audit_ops.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/replay_audit_ops.py), [ops_trust_monitoring.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_trust_monitoring.py) | 本地可靠性、证据脚本、artifact refs/manifest、audit anchor、healthcheck、ops monitoring 与 chat proxy no-secret 防线已补；真实 provider/callback 稳定性待真实环境 |
| 13. 对外接口模型 | cases/trace/replay/fairness/review/policies | 基本落地（内部 + 主业务代理扩展中） | [route_group_case_read.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_case_read.py), [route_group_ops_read_model_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_ops_read_model_pack.py), [debate_judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_judge.rs), [debate_ops.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_ops.rs) | public verification、challenge/review、challenge ops queue、runtime readiness 与 AI 内部 calibration decision log 已完成；后续按需要补 decision log 的 chat 产品代理 |
| 14. 继承映射表 | 从旧逻辑到新架构的继承策略 | 已落地 | [completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md), [当前开发计划.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md) | 旧 pipeline 资产已迁移到六对象/role runtime/gateway core/trust layer；P41 是对 Fairness/Adaptive 运营面的继续外化 |
| 15. 可验证信任层与协议化扩展 | commitment/attestation/challenge/protocol | 基本落地（本地参考 + 产品桥接） | [trust_phasea.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_phasea.py), [trust_public_verify_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_public_verify_contract.py), [trust_challenge_public_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_challenge_public_contract.py), [trust_challenge_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_challenge_runtime_routes.py) | Phase A/B 在本地参考和产品桥接口径下基本闭环；Phase C/D 不进 P41 |
| 16. 不推荐设计边界 | 不做画像污染、不过早 memory 主链等 | 基本守住 | [assistant_agent_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_agent_routes.py), [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py) | NPC/Room QA 仍为 advisory-only；topic memory/Reason Passport/Identity Proof/Constitution Registry/第三方 jury/on-chain 均未进入单场裁决主链 |
| 17. 推荐落地路线 | Phase1/2/3 路线图 | Phase1 基本完成，Phase2/3 进入治理动作闭环阶段 | [P40 归档](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260428T065429Z-ai-judge-stage-closure-execute.md), [当前开发计划.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md) | P41 runtime readiness contract、chat proxy、frontend Ops Console、calibration decision log、panel shadow candidate contract 与 release evidence 已落地；下一步是热点拆分、本地回归与阶段收口 |
| 18. 最后产品判断 | 企业级裁判系统目标态 | 方向成立，未完全完成 | 同上 | 已具备“制度化裁判庭 + 本地可信外部化 + 公验 + challenge/review 产品桥接”的形态；距离完整目标态还差 Fairness/Adaptive Ops 控制面、真实环境与远期协议扩展 |

## 4. Agent 子项映射（方案第6章）

| Agent 子项 | 目标 | 当前完成度 | 证据 | 主要缺口 |
| --- | --- | --- | --- | --- |
| 6.1 Clerk Agent | 收案、盲化、准入门禁 | 基本落地 | [judge_workflow_roles.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_workflow_roles.py), [judge_app_domain.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_app_domain.py) | 语义级盲化策略仍可结合真实样本校准 |
| 6.2 Recorder Agent | 时间线重建与结构化 transcript | 基本落地 | [judge_workflow_roles.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_workflow_roles.py), [trace_store_boundaries.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/trace_store_boundaries.py), [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py) | transcript/replay snapshot 已具备 artifact refs；生产对象存储 roundtrip 待真实环境 |
| 6.3 Claim Graph Agent | 争点图谱构建 | 基本落地 | [claim_graph.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/claim_graph.py), [judge_mainline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_mainline.py) | 深层 claim graph 运营检索与可视化仍可增强 |
| 6.4 Evidence Agent | 检索与证据核验 | 基本落地 | [evidence_ledger.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/evidence_ledger.py), [runtime_rag.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/runtime_rag.py), [registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py) | Evidence pack artifact refs、citation verifier 与 release gate 输入已补；真实样本 evidence normalization 待环境 |
| 6.5 Judge Panel Agent | 多法官独立判定 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [panel_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/panel_runtime_routes.py), [panel_runtime_profile_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/panel_runtime_profile_contract.py) | panel shadow evaluation、readiness 与 candidate model/product readiness 合同已出现；多模型 panel 生产实跑仍后置 |
| 6.6 Fairness Sentinel Agent | 稳定性与公平门禁 | 部分落地（高） | [fairness_analysis.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_analysis.py), [fairness_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_runtime_routes.py), [fairness_panel_evidence.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_panel_evidence.py), [fairness_calibration_decision_log.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_calibration_decision_log.py) | fairness calibration advisor、人工 decision log 与 panel shadow candidate blockers 已内部化；真实样本实跑待环境 |
| 6.7 Chief Arbiter Agent | 汇总裁决与状态决策 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [judge_mainline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_mainline.py), [trust_challenge_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_challenge_runtime_routes.py), [registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py) | durable trust registry、challenge/review 状态机、review decision sync 与产品桥接已补；release readiness Ops 控制面待 P41 |
| 6.8 Opinion Writer Agent | 生成可读裁决书 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [trust_artifact_summary.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_artifact_summary.py), [DebateRoomPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/DebateRoomPage.tsx) | 裁决书、公验、challenge/review 状态展示已补；多模型/校准不会反向改写 opinion fact lock |

## 5. 关键结论（当前真实状态）

1. 当前阶段已完成 P40 stage closure，P35/P36/P37/P38/P39 主体成果仍作为底座：
   - 六对象 typed ledger snapshot 与 durable workflow mainline。
   - Clerk/Recorder/Claim/Evidence/Panel/Fairness/Arbiter/Opinion role runtime 主链。
   - LLM/Knowledge Gateway core convergence。
   - trace/replay/audit store boundary split。
   - durable trust registry、artifact store、audit anchor、public verification 与 release readiness artifact。
   - Fairness benchmark readiness、panel shadow readiness、citation verifier evidence gate 与 registry release gate。
2. P40 主体成果是把“受约束 challenge/review”推进到主业务产品面：
   - AI 服务已形成 `trust_challenge_public_contract.py` 与 `/trust/challenges/public-status`。
   - `chat_server` 已新增 `/api/debate/sessions/{id}/judge-report/challenge` 与 `/challenge/request`。
   - `frontend/packages/debate-domain` 与 `DebateRoomPage` 已具备 challenge typed read model、request action 与 review sync 展示。
   - `chat_server` 与 Ops Console 已具备 `/api/debate/ops/judge-challenge-queue` 的基础桥接。
3. P41 已完成的控制面能力：
   - AI 服务新增 `runtime_readiness_public_contract.py` 与 `/internal/judge/ops/runtime-readiness`，从内部 ops pack 提炼 public-safe readiness 合同。
   - `chat_server` 新增 `/api/debate/ops/judge-runtime-readiness`，复用 `judge_review` RBAC、AI internal key、timeout 与 no-secret 二次校验。
   - `frontend/packages/ops-domain` 与 `OpsConsolePage` 已展示 release gate、fairness calibration、panel runtime、trust/challenge 与 real-env readiness。
   - calibration advisor 的 recommended actions 已支持人工 decision log，写入 durable facts repository，并进入 advisor/runtime readiness summary。
   - panel runtime readiness 已冻结 candidate model/profile、成本、时延、agreement、drift、switch blockers 与 release gate signals；多模型 panel 仍是 shadow/readiness，不是生产切换。
   - release readiness evidence、artifact summary、runtime ops pack 与 stage closure evidence 已输出 P41 control-plane 摘要；当前为 `local_reference_ready` + `p41_control_plane_status=env_blocked`，不宣称 real-env pass。
4. 所有真实环境结论必须等 `REAL_CALIBRATION_ENV_READY=true`、真实样本、真实服务窗口、生产对象存储与 P41 readiness 输入具备后再写入；不得把 `local_reference_ready` 写成 real-env `pass`。
5. 远期 Protocol Expansion 仍不进入主线：Identity Proof、Constitution Registry、Reason Passport、第三方 review network、on-chain anchor 均等待产品控制面和真实环境闭环稳定后再评估。

## 6. 下一步优先级

1. 执行 `ai-judge-p41-route-hotspot-split-pack`，继续下沉 AI projection、chat proxy helper 与 frontend resolver，控制热点文件膨胀。
2. 执行 `ai-judge-p41-local-reference-regression-pack` 与 `ai-judge-p41-stage-closure-execute`，刷新本地参考证据并完成阶段收口。
3. 阶段收口前决定是否需要把 calibration decision log 继续代理到 chat/frontend 独立操作面；当前 AI 内部 route、advisor 与 runtime readiness summary 已具备。
4. 等真实环境具备后执行 `ai-judge-real-env-pass-window-execute-on-env` 或后续等价 real-env pass window，补齐真实环境 `pass` 证据；在此之前继续保持 `env_blocked`。

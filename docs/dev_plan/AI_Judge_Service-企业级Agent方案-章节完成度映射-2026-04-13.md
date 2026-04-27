# AI_Judge_Service 企业级 Agent 方案章节完成度映射（2026-04-13）

更新时间：2026-04-26
状态：已更新（对齐 P39 stage closure；P40 已启动 Bounded Challenge Product Bridge + Review Sync 主线）
映射对象：[AI_judge_service 企业级 Agent 服务设计方案（2026-04-13）](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/AI_Judge_Service-企业级Agent服务设计方案-2026-04-13.md)

## 1. 判定口径

1. 已落地：主链代码已存在，且可通过当前测试或收口证据验证。
2. 基本落地：主链已闭环，仍有运营化、真实环境或平台化增强项。
3. 部分落地：主链能力已出现，但仍缺关键子能力、持久化事实源或治理闭环。
4. 未落地：当前仅为设计目标，仓库内无对应主链实现。
5. 环境阻塞：实现入口存在，但最终验收依赖真实环境、真实样本、真实对象存储或 on-env 窗口。

## 2. 当前总进度判断

| 维度 | 当前阶段 | 结论 |
| --- | --- | --- |
| Enterprise MVP（方案 Phase 1） | 基本落地 | 8 Agent 官方裁决主链、六对象 ledger、durable workflow、trace/replay、review/audit、富裁决报告、受保护复核语义、public verification 产品代理与本地回归闭环已形成 |
| Fairness Hardened（方案 Phase 2） | 部分落地（高） | Fairness gate、panel disagreement、local reference benchmark/freeze、真实样本 benchmark readiness、panel shadow evaluation、normalized fairness/panel evidence 与 citation verifier evidence gate 已完成；真实样本实跑与 real-env pass 仍待窗口 |
| Adaptive Judge Platform（方案 Phase 3） | 部分落地（高） | gateway core、policy/prompt/tool registry、ops read model、release gate、release readiness artifact、panel shadow readiness、runtime ops closure backfill 已推进；auto-calibration、多模型 panel 生产化与 domain-specific judge families 仍后置 |
| Verifiable Trust Layer（方案第15章 Phase A/B 局部） | 基本落地（本地参考） | Trust registry、artifact store、audit anchor、public verification visibility/redaction/readiness、chat_server 公验代理、client read model、release readiness artifact export 与 ops trust projection 已形成本地参考闭环；challenge/review 产品桥接与生产对象存储真实验收仍待 P40/真实环境 |
| Protocol Expansion Layer（方案第15章 Phase C-D） | 未进入主线 | Identity Proof、Constitution Registry、Reason Passport、第三方 review network、on-chain anchor 均不属于当前 P40 主线；在 challenge/review 产品桥接稳定前不得进入单场官方裁决输入 |
| 真实环境闭环 | 环境阻塞 | 当前证据为 `local_reference_ready` / `env_blocked`；缺真实样本、真实 provider/callback、生产对象存储与真实服务窗口，不得宣称 real-env `pass` |

一句话结论：

`截至 P39 stage closure，AI Judge 已从“内部可运营、可回填、可发布门禁化的可信裁判平台”推进到“public verification 已可通过主业务门面和产品端安全读取”的阶段：chat_server 公验代理、前端/共享 domain 公验 read model、citation verifier、release readiness artifact export、registry/trust projection split 与 P39 local reference regression 均已落地；P40 应优先把受约束 challenge / review 从 AI 服务内部 Trust Registry 推进到 chat_server 门面、用户可执行路径与 ops 追踪闭环，真实环境 pass 继续等待环境窗口。`

## 3. 章节级完成度总览

| 方案章节 | 目标摘要 | 当前完成度 | 核心证据 | 结论 |
| --- | --- | --- | --- | --- |
| 1. 一句话结论 | 从“评分器”升级为“裁判庭系统” | 基本落地 | [P39 归档](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260426T104553Z-ai-judge-stage-closure-execute.md), [completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md) | 裁判庭主链、本地可信制度层、release readiness artifact 与 public verification 产品代理均已成型；真实环境 pass 与 bounded challenge 产品桥接仍待推进 |
| 2. 产品目标重新定义 | 丰富判决展示、公正、可运营 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [ops_read_model_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_read_model_pack.py), [debate_judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_judge.rs), [DebateRoomPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/DebateRoomPage.tsx) | 富展示、review/draw/blocked、ops monitoring、public verification 产品面与 release readiness artifact 已具备；受约束 challenge 用户流程待 P40 |
| 3. 为什么必须是 Agent | 分工、状态、工具、门禁 | 基本落地 | [judge_workflow_roles.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_workflow_roles.py), [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py) | 8 Agent role runtime 与 advisory shell 均已出现；P40 不改官方裁决链，仅把 challenge/review 作为 Trust Layer 与主业务后续流程产品化 |
| 4. 总体设计理念 | 公平优先、事实先锁定、可回放 | 基本落地 | [trace_store_boundaries.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/trace_store_boundaries.py), [ai_judge_runtime_ops_pack.md](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_runtime_ops_pack.md), [ai_judge_stage_closure_evidence.md](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_stage_closure_evidence.md) | locked verdict、opinion fact lock、trace/replay/audit、runtime ops closure backfill、public verification 与 local reference regression 均已接通；real-env 仍后置 |
| 5. 推荐架构总览 | 法庭式流水线 + Ops/Replay/Audit | 基本落地 | [app/](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app), [route_group_trust.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_trust.py), [request_report_query.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/request_report_query.rs), [ops_read_model_trust_projection.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_read_model_trust_projection.py) | 模块化单体、route group、chat proxy 与 ops projection 架构稳定；P40 继续将 challenge/review 产品桥接下沉为薄装配 |
| 6. 法庭式 Agent 分工 | 8 类 Agent 职责闭环 | 基本落地 | 见“第4节 Agent 子项映射” | 官方裁决链角色齐备；challenge/review 产品桥接、真实样本 benchmark 与多模型 panel 生产实跑仍是增强项 |
| 7. 企业级核心数据对象 | Case/Claim/Evidence/Verdict/Fairness/Opinion | 基本落地 | [ledger_objects.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/ledger_objects.py), [repository.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/facts/repository.py), [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py), [s3_store.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/artifacts/s3_store.py) | 六对象 typed snapshot、Artifact refs/manifest、S3-compatible adapter、release readiness artifact 与 no-secret healthcheck 已落地；生产对象存储 roundtrip 待环境 |
| 8. 丰富判决内容 | 用户层/高级层/Ops 层展示 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [case_read_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/case_read_routes.py), [trust_artifact_summary.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_artifact_summary.py), [debate-domain index.ts](/Users/panyihang/Documents/EchoIsle/frontend/packages/debate-domain/src/index.ts) | 用户报告、ops summary、case overview、trust/artifact summary 与 public verification 产品面已具备；challenge/review 用户动作与状态展示待 P40 |
| 9. 公平性保证机制 | 盲化、镜像、扰动、复核、benchmark | 部分落地（高） | [fairness_analysis.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_analysis.py), [fairness_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_runtime_routes.py), [fairness_panel_evidence.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_panel_evidence.py), [registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py) | 本地 reference freeze、真实样本 readiness、panel shadow evaluation、normalized evidence、citation verifier 与 release gate 输入已达成；真实样本实跑与 on-env pass 待环境 |
| 10. 企业级工程架构 | Gateway/Orchestrator/Runtime/Ledger/Ops | 基本落地 | [orchestrator.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/core/workflow/orchestrator.py), [gateway_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/gateway_runtime.py), [repository.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/trust/repository.py), [bootstrap_trust_ops_dependencies.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/bootstrap_trust_ops_dependencies.py), [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py) | Postgres workflow、gateway core、ledger/read model、trust registry、route dependency split、本地和 S3-compatible artifact store、artifact healthcheck 与 release artifact 均已出现 |
| 11. Agent Runtime 设计 | Prompt/Tool/Policy Registry + Model Gateway | 部分落地（高） | [policy_registry.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/policy_registry.py), [registry_product_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_product_runtime.py), [registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py), [release_readiness_projection.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/release_readiness_projection.py) | registry、gateway trace、release readiness artifact 与 citation verifier 已进入主链；auto-calibration、多模型 panel 生产化仍后置 |
| 12. 企业级可靠性要求 | 幂等、callback、trace、replay、观测 | 基本落地 | [callback_client.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/callback_client.py), [replay_audit_ops.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/replay_audit_ops.py), [ops_trust_monitoring.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_trust_monitoring.py), [request_report_query.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/models/judge/request_report_query.rs) | 本地可靠性、证据脚本、artifact refs/manifest、audit anchor、healthcheck、ops monitoring 与 chat proxy no-secret 防线已补；真实 provider/callback 稳定性待真实环境 |
| 13. 对外接口模型 | cases/trace/replay/fairness/review/policies | 基本落地（内部 + 主业务代理） | [route_group_case_read.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_case_read.py), [route_group_replay.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_replay.py), [route_group_trust.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_trust.py), [debate_judge.rs](/Users/panyihang/Documents/EchoIsle/chat/chat_server/src/handlers/debate_judge.rs), [trust_public_verify_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_public_verify_contract.py) | 内部接口层与 public verification chat proxy 已覆盖大多数设计面；bounded challenge / review 产品代理仍待 P40，客户端仍禁止直连 AI 服务 |
| 14. 继承映射表 | 从旧逻辑到新架构的继承策略 | 已落地 | [P35 归档](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260425T022246Z-ai-judge-stage-closure-execute.md), [P39 归档](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260426T104553Z-ai-judge-stage-closure-execute.md) | 旧 pipeline 资产已迁移到六对象/role runtime/gateway core；P39 把公验产品面、证据核验、release artifact 与可信外部化合同继续接入主线 |
| 15. 可验证信任层与协议化扩展 | commitment/attestation/challenge/protocol | 基本落地（本地参考 + 公验产品代理） | [trust_phasea.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_phasea.py), [trust_public_verify_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_public_verify_contract.py), [trust_audit_anchor_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_audit_anchor_contract.py), [trust_challenge_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_challenge_runtime_routes.py), [public_verify_projection.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/public_verify_projection.py), [repository.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/trust/repository.py) | Phase A 在本地参考口径下基本闭环，Public Verification 已通过 chat/frontend 产品化；bounded challenge 产品桥接、生产对象存储真实验收与 real-env pass 待 P40/真实环境 |
| 16. 不推荐设计边界 | 不做画像污染、不过早 memory 主链等 | 基本守住 | [assistant_agent_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_agent_routes.py), [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py) | NPC/Room QA 已标注 advisory-only；topic memory/Reason Passport/Identity Proof/Constitution Registry/第三方 jury/on-chain 均未进入单场裁决主链 |
| 17. 推荐落地路线 | Phase1/2/3 路线图 | Phase1 基本完成，Phase2/3 本地参考完成关键可信层 | [P39 归档](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260426T104553Z-ai-judge-stage-closure-execute.md), [completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md), [todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md), [当前开发计划.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md) | 当前已进入 P40：bounded challenge eligibility、chat challenge proxy、client challenge read model、review sync、ops bridge 与热点拆分 |
| 18. 最后产品判断 | 企业级裁判系统目标态 | 方向成立，未完全完成 | 同上 | 已具备“制度化裁判庭 + 本地可信外部化 + 公验产品面 + 发布门禁证据自动化”的形态；距离完整目标态还差受约束 challenge 产品桥接、真实环境与远期协议扩展 |

## 4. Agent 子项映射（方案第6章）

| Agent 子项 | 目标 | 当前完成度 | 证据 | 主要缺口 |
| --- | --- | --- | --- | --- |
| 6.1 Clerk Agent | 收案、盲化、准入门禁 | 基本落地 | [judge_workflow_roles.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_workflow_roles.py), [judge_app_domain.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_app_domain.py) | 语义级盲化策略仍可结合真实样本校准 |
| 6.2 Recorder Agent | 时间线重建与结构化 transcript | 基本落地 | [judge_workflow_roles.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_workflow_roles.py), [trace_store_boundaries.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/trace_store_boundaries.py), [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py), [s3_store.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/artifacts/s3_store.py) | transcript/replay snapshot 已具备 artifact refs、healthcheck 与 S3-compatible store 边界；生产对象存储 roundtrip 待真实环境 |
| 6.3 Claim Graph Agent | 争点图谱构建 | 基本落地 | [claim_graph.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/claim_graph.py), [judge_mainline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_mainline.py) | 深层 claim graph 运营检索与可视化仍可增强 |
| 6.4 Evidence Agent | 检索与证据核验 | 基本落地 | [evidence_ledger.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/evidence_ledger.py), [runtime_rag.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/runtime_rag.py), [rag_retriever.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/rag_retriever.py), [registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py) | Evidence pack artifact refs、citation verifier 与 release/ops evidence 输入已补；真实样本 evidence normalization 待环境 |
| 6.5 Judge Panel Agent | 多法官独立判定 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [panel_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/panel_runtime_routes.py), [panel_runtime_profile_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/panel_runtime_profile_contract.py), [fairness_panel_evidence.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_panel_evidence.py) | panel shadow evaluation 与 normalized evidence 已作为观测与 release gate 输入出现；多模型 panel 生产实跑待真实环境 |
| 6.6 Fairness Sentinel Agent | 稳定性与公平门禁 | 部分落地（高） | [fairness_analysis.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_analysis.py), [fairness_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_runtime_routes.py), [registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py), [fairness_panel_evidence.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_panel_evidence.py) | 真实样本 benchmark readiness、normalized release evidence 与 citation verifier 已有；真实样本实跑与 on-env pass 待环境 |
| 6.7 Chief Arbiter Agent | 汇总裁决与状态决策 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [judge_mainline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_mainline.py), [repository.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/trust/repository.py), [trust_challenge_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_challenge_runtime_routes.py), [registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py) | durable trust registry、challenge/review 状态机、artifact refs、release readiness artifact 与 release gate 已补；challenge/review 产品桥接待 P40 |
| 6.8 Opinion Writer Agent | 生成可读裁决书 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [ops_read_model_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_read_model_pack.py), [trust_artifact_summary.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_artifact_summary.py), [DebateRoomPage.tsx](/Users/panyihang/Documents/EchoIsle/frontend/packages/app-shell/src/pages/DebateRoomPage.tsx) | 裁决书 artifact refs、audit export manifest、artifact healthcheck、ops trust/artifact summary 与公验产品面已补；review decision sync 待 P40 |

## 5. 关键结论（当前真实状态）

1. 当前阶段已完成 `P39 stage closure`，P35/P36/P37/P38 主体成果仍作为底座：
   - 六对象 typed ledger snapshot 与 `judge_ledger_snapshots` 表。
   - durable workflow mainline 与 ordered events。
   - Clerk/Recorder/Claim/Evidence/Panel/Fairness/Arbiter/Opinion role runtime 主链。
   - Opinion Writer ledger-driven fact lock。
   - LLM/Knowledge Gateway core convergence。
   - trace/replay/audit store boundary split。
   - durable trust registry store、phase/final write-through 与 challenge/review 状态机。
   - Artifact Store port、local adapter、S3-compatible adapter 边界与 manifest hash。
   - Public Verification visibility/redaction/readiness contract、chat proxy 与 client read model。
   - citation verifier evidence gate、release readiness artifact export 与 ops trust monitoring。
   - NPC/Room QA advisory-only shell。
2. P39 主体成果是把 P38 的“公验代理合同与发布证据自动化”推进为“主业务门面可安全读取的可信裁判产品面”：
   - `chat_server` 已新增 `/api/debate/sessions/{id}/judge-report/public-verify`，复用 judge report 权限与 no-secret 防线。
   - `frontend/packages/debate-domain` 与 `DebateRoomPage` 已具备 public verification typed read model 和最小展示。
   - Evidence Ledger 已输出 `citationVerification`，final guard、release gate 与 ops monitoring 均可引用 citation verifier 状态。
   - release readiness evidence 已归档为 artifact ref / manifest hash，可被 audit anchor、ops monitoring、runtime ops 与 stage closure evidence 引用。
   - `release_readiness_projection.py`、`public_verify_projection.py` 与 `ops_read_model_trust_projection.py` 已继续下沉 registry/trust/read-model 热点逻辑。
   - P39 local reference regression 已刷新 AI service、chat、frontend 与 runtime ops，本地参考为 `local_reference_ready`，真实 readiness 仍为 `env_blocked`。
3. 方案第15章已有多项合同和路由进入主链：
   - [trust_commitment_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_commitment_contract.py)
   - [trust_verdict_attestation_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_verdict_attestation_contract.py)
   - [trust_challenge_review_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_challenge_review_contract.py)
   - [trust_public_verify_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_public_verify_contract.py)
   - [trust_audit_anchor_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_audit_anchor_contract.py)
   - [trust_kernel_version_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_kernel_version_contract.py)
4. 当前最核心的未完成项已从“可信能力能不能通过主业务门面安全读取”转为“受约束 challenge / review 能不能通过主业务门面安全执行并被用户和 ops 追踪”：
   - challenge eligibility/status public-safe 合同仍待稳定。
   - `chat_server` 参与者侧 challenge status/request 代理尚未落地。
   - Web/Desktop 共享 challenge read model 与最小 UI 尚未落地。
   - AI review decision 到主业务裁决视图的同步语义仍需收敛。
   - chat ops review 与 AI trust challenge ops queue 仍需桥接。
   - 真实样本、真实 AI provider/callback 环境、生产对象存储真实验收与真实服务窗口仍不可用。
5. 所有真实环境结论必须等 `REAL_CALIBRATION_ENV_READY=true`、真实样本、真实服务窗口、生产对象存储与 P40 readiness 输入具备后再写入；不得把 `local_reference_ready` 写成 real-env `pass`。

## 6. 下一步优先级

1. 执行 `ai-judge-p40-challenge-eligibility-contract-pack`，在 AI 服务内部形成 public-safe challenge eligibility/status 合同，稳定 allowed actions、blockers、状态枚举与 no-secret 校验。
2. 执行 `ai-judge-p40-chat-challenge-proxy-pack`，在 `chat_server` 落地参与者侧 challenge status/request 代理接口，复用权限、限流、phone bind 与公验代理 no-secret 防线。
3. 执行 `ai-judge-p40-client-challenge-read-model-pack`，让 Web/Desktop 共享 domain 能消费 challenge eligibility、open/review/closed 状态、blockers 与 request action。
4. 执行 `ai-judge-p40-review-decision-sync-contract-pack`，收敛 `verdict_upheld / verdict_overturned / draw_after_review / review_retained` 到主业务裁决视图的同步语义。
5. 执行 `ai-judge-p40-challenge-ops-read-model-bridge-pack`，桥接 AI trust challenge ops queue 与 chat ops review 视图，让 ops 能追踪用户 challenge、SLA、priority 与公开安全摘要。
6. 执行 `ai-judge-p40-challenge-route-hotspot-split-pack`，继续下沉 challenge/read-model projection helper，控制 `ops_read_model_pack.py`、`registry_routes.py`、chat judge handler/model 热点膨胀。
7. 执行 `ai-judge-p40-local-reference-regression-pack` 与 `ai-judge-p40-stage-closure-execute`，刷新本地参考证据并完成阶段收口。
8. 等真实环境具备后执行 `ai-judge-p37-real-env-pass-window-execute-on-env` 或后续等价 real-env pass window，补齐真实环境 `pass` 证据；在此之前继续保持 `env_blocked`。

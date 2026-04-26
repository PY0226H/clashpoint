# AI_Judge_Service 企业级 Agent 方案章节完成度映射（2026-04-13）

更新时间：2026-04-26
状态：已更新（对齐 P38 stage closure；P39 已启动 Public Verification Proxy 与 Evidence Verifier Hardening 主线）
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
| Enterprise MVP（方案 Phase 1） | 基本落地 | 8 Agent 官方裁决主链、六对象 ledger、durable workflow、trace/replay、review/audit、富裁决报告、受保护复核语义与本地回归闭环已形成 |
| Fairness Hardened（方案 Phase 2） | 部分落地（高） | Fairness gate、panel disagreement、local reference benchmark/freeze、真实样本 benchmark readiness、panel shadow evaluation 与 normalized fairness/panel evidence 已完成；真实样本实跑与 real-env pass 仍待窗口 |
| Adaptive Judge Platform（方案 Phase 3） | 部分落地（高） | gateway core、policy/prompt/tool registry、ops read model、release gate、release readiness evidence、panel shadow readiness、runtime ops closure backfill 已推进；auto-calibration、多模型 panel 生产化与 domain-specific judge families 仍后置 |
| Verifiable Trust Layer（方案第15章 Phase A） | 基本落地（本地参考） | P38 已在 P36/P37 trust registry、artifact store、public verification 与 audit anchor 基础上补齐 release readiness evidence、public verification proxy-facing contract、artifact healthcheck、fairness/panel evidence normalization 与 ops trust projection；chat_server 公验代理、生产对象存储真实验收与 real-env pass 仍待 P39/真实环境 |
| Protocol Expansion Layer（方案第15章 Phase B-D） | 部分落地（仅内部公验合同） | Public Verification 内部合同、visibility/redaction、cache profile 与 proxyRequired 已落地；Identity Proof、Constitution Registry、Reason Passport、第三方 review network、on-chain anchor 均不属于当前 P39 主线 |
| 真实环境闭环 | 环境阻塞 | 当前证据为 `local_reference_ready` / `env_blocked`；缺真实样本、真实 provider/callback、生产对象存储与真实服务窗口，不得宣称 real-env `pass` |

一句话结论：

`截至 P38 stage closure，AI Judge 已从“本地参考口径下的生产可信外部化准备”推进到“内部可运营、可回填、可发布门禁化的可信裁判平台”：runtime ops closure backfill、release readiness evidence、public verification proxy-facing contract、artifact store no-secret healthcheck、fairness/panel normalized evidence、ops trust projection 与 P38 local reference regression 均已落地；P39 应优先把 public verification 通过 chat_server 代理给产品面，并补齐 citation verifier / release readiness artifact export，真实环境 pass 继续等待环境窗口。`

## 3. 章节级完成度总览

| 方案章节 | 目标摘要 | 当前完成度 | 核心证据 | 结论 |
| --- | --- | --- | --- | --- |
| 1. 一句话结论 | 从“评分器”升级为“裁判庭系统” | 基本落地 | [P38 归档](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260426T004547Z-ai-judge-stage-closure-execute.md), [completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md) | 裁判庭主链、本地可信制度层、release readiness evidence 与 public verification 内部合同均已成型；真实环境 pass 与 chat proxy 仍待推进 |
| 2. 产品目标重新定义 | 丰富判决展示、公正、可运营 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [ops_read_model_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_read_model_pack.py), [ops_trust_monitoring.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_trust_monitoring.py), [registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py) | 富展示、review/draw/blocked、ops monitoring、release readiness 与本地证据回归已具备；产品面公验代理待 P39 |
| 3. 为什么必须是 Agent | 分工、状态、工具、门禁 | 基本落地 | [judge_workflow_roles.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_workflow_roles.py), [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py) | 8 Agent role runtime 与 advisory shell 均已出现；P39 不改官方裁决链，仅增强证据核验与公验代理 |
| 4. 总体设计理念 | 公平优先、事实先锁定、可回放 | 基本落地 | [trace_store_boundaries.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/trace_store_boundaries.py), [ai_judge_runtime_ops_pack.md](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_runtime_ops_pack.md), [ai_judge_stage_closure_evidence.md](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_stage_closure_evidence.md) | locked verdict、opinion fact lock、trace/replay/audit、runtime ops closure backfill 与 local reference regression 均已接通；real-env 仍后置 |
| 5. 推荐架构总览 | 法庭式流水线 + Ops/Replay/Audit | 基本落地 | [app/](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app), [route_group_trust.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_trust.py), [ops_read_model_trust_projection.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_read_model_trust_projection.py) | 模块化单体、route group 与 ops projection 架构稳定；P39 继续将公验代理与 release artifact 推向主业务门面 |
| 6. 法庭式 Agent 分工 | 8 类 Agent 职责闭环 | 基本落地 | 见“第4节 Agent 子项映射” | 官方裁决链角色齐备；citation verifier、多模型 panel 生产实跑与真实样本 benchmark 仍是增强项 |
| 7. 企业级核心数据对象 | Case/Claim/Evidence/Verdict/Fairness/Opinion | 基本落地 | [ledger_objects.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/ledger_objects.py), [repository.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/facts/repository.py), [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py), [s3_store.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/artifacts/s3_store.py) | 六对象 typed snapshot、Artifact refs/manifest、S3-compatible adapter 与 no-secret healthcheck 已落地；生产对象存储 roundtrip 待环境 |
| 8. 丰富判决内容 | 用户层/高级层/Ops 层展示 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [case_read_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/case_read_routes.py), [trust_artifact_summary.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_artifact_summary.py) | 用户报告、ops summary、case overview 与 trust/artifact summary 已具备；public verification 产品面展示待 chat/frontend 同步 |
| 9. 公平性保证机制 | 盲化、镜像、扰动、复核、benchmark | 部分落地（高） | [fairness_analysis.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_analysis.py), [fairness_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_runtime_routes.py), [fairness_panel_evidence.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_panel_evidence.py), [panel_runtime_profile_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/panel_runtime_profile_contract.py) | 本地 reference freeze、真实样本 readiness、panel shadow evaluation 与 normalized evidence 已达成；真实样本实跑与 on-env pass 待环境 |
| 10. 企业级工程架构 | Gateway/Orchestrator/Runtime/Ledger/Ops | 基本落地 | [orchestrator.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/core/workflow/orchestrator.py), [gateway_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/gateway_runtime.py), [repository.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/trust/repository.py), [bootstrap_trust_ops_dependencies.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/bootstrap_trust_ops_dependencies.py), [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py) | Postgres workflow、gateway core、ledger/read model、trust registry、route dependency split、本地和 S3-compatible artifact store、artifact healthcheck 均已出现 |
| 11. Agent Runtime 设计 | Prompt/Tool/Policy Registry + Model Gateway | 部分落地（高） | [policy_registry.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/policy_registry.py), [registry_product_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_product_runtime.py), [registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py), [fairness_panel_evidence.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_panel_evidence.py) | registry 与 gateway trace 已进入主链；release readiness evidence 已落地，artifact export 与 citation verifier 待 P39 |
| 12. 企业级可靠性要求 | 幂等、callback、trace、replay、观测 | 基本落地 | [callback_client.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/callback_client.py), [replay_audit_ops.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/replay_audit_ops.py), [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py), [ops_trust_monitoring.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_trust_monitoring.py) | 本地可靠性、证据脚本、artifact refs/manifest、audit anchor、healthcheck 与 ops monitoring 已补；真实 provider/callback 稳定性待真实环境 |
| 13. 对外接口模型 | cases/trace/replay/fairness/review/policies | 基本落地（内部接口） | [route_group_case_read.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_case_read.py), [route_group_replay.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_replay.py), [route_group_trust.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_trust.py), [trust_public_verify_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_public_verify_contract.py) | 内部接口层已覆盖大多数设计面；public verification proxy-facing contract 已稳定，P39 需要由 chat_server 提供产品代理，仍禁止客户端直连 AI 服务 |
| 14. 继承映射表 | 从旧逻辑到新架构的继承策略 | 已落地 | [P35 归档](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260425T022246Z-ai-judge-stage-closure-execute.md), [P38 归档](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260426T004547Z-ai-judge-stage-closure-execute.md) | 旧 pipeline 资产已迁移到六对象/role runtime/gateway core；P38 把证据自动化、release readiness 与可信外部化合同继续接入主线 |
| 15. 可验证信任层与协议化扩展 | commitment/attestation/challenge/protocol | 基本落地（本地参考） | [trust_phasea.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_phasea.py), [trust_public_verify_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_public_verify_contract.py), [trust_audit_anchor_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_audit_anchor_contract.py), [trust_challenge_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_challenge_runtime_routes.py), [repository.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/trust/repository.py), [ops_read_model_trust_projection.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_read_model_trust_projection.py) | Phase A 在本地参考口径下基本闭环；chat proxy、release readiness artifact export、生产对象存储真实验收与 real-env pass 待 P39/真实环境 |
| 16. 不推荐设计边界 | 不做画像污染、不过早 memory 主链等 | 基本守住 | [assistant_agent_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_agent_routes.py), [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py) | NPC/Room QA 已标注 advisory-only；topic memory/Reason Passport/Identity Proof/Constitution Registry 未进入单场裁决主链 |
| 17. 推荐落地路线 | Phase1/2/3 路线图 | Phase1 基本完成，Phase2/3 本地参考完成关键可信层 | [P38 归档](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260426T004547Z-ai-judge-stage-closure-execute.md), [completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md), [todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md), [当前开发计划.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md) | 当前已进入 P39：public verification chat proxy、client read model、citation verifier、release readiness artifact export 与热点拆分 |
| 18. 最后产品判断 | 企业级裁判系统目标态 | 方向成立，未完全完成 | 同上 | 已具备“制度化裁判庭 + 本地可信外部化 + 发布门禁证据自动化”的形态；距离完整目标态还差 chat proxy、公验产品面、citation verifier、真实环境与协议扩展 |

## 4. Agent 子项映射（方案第6章）

| Agent 子项 | 目标 | 当前完成度 | 证据 | 主要缺口 |
| --- | --- | --- | --- | --- |
| 6.1 Clerk Agent | 收案、盲化、准入门禁 | 基本落地 | [judge_workflow_roles.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_workflow_roles.py), [judge_app_domain.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_app_domain.py) | 语义级盲化策略仍可结合真实样本校准 |
| 6.2 Recorder Agent | 时间线重建与结构化 transcript | 基本落地 | [judge_workflow_roles.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_workflow_roles.py), [trace_store_boundaries.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/trace_store_boundaries.py), [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py), [s3_store.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/artifacts/s3_store.py) | transcript/replay snapshot 已具备 artifact refs、healthcheck 与 S3-compatible store 边界；生产对象存储 roundtrip 待真实环境 |
| 6.3 Claim Graph Agent | 争点图谱构建 | 基本落地 | [claim_graph.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/claim_graph.py), [judge_mainline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_mainline.py) | 深层 claim graph 运营检索与可视化仍可增强 |
| 6.4 Evidence Agent | 检索与证据核验 | 基本落地 | [evidence_ledger.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/evidence_ledger.py), [runtime_rag.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/runtime_rag.py), [rag_retriever.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/rag_retriever.py), [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py) | Evidence pack artifact refs 已补；citation verifier 与 evidence gate 输入是 P39 优先缺口，真实样本 evidence normalization 待环境 |
| 6.5 Judge Panel Agent | 多法官独立判定 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [panel_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/panel_runtime_routes.py), [panel_runtime_profile_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/panel_runtime_profile_contract.py), [fairness_panel_evidence.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_panel_evidence.py) | panel shadow evaluation 与 normalized evidence 已作为观测与 release gate 输入出现；多模型 panel 生产实跑待真实环境 |
| 6.6 Fairness Sentinel Agent | 稳定性与公平门禁 | 部分落地（高） | [fairness_analysis.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_analysis.py), [fairness_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_runtime_routes.py), [registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py), [fairness_panel_evidence.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_panel_evidence.py) | 真实样本 benchmark readiness 与 normalized release evidence 已有；真实样本实跑与 on-env pass 待环境 |
| 6.7 Chief Arbiter Agent | 汇总裁决与状态决策 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [judge_mainline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_mainline.py), [repository.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/trust/repository.py), [trust_challenge_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_challenge_runtime_routes.py), [registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py) | durable trust registry、challenge/review 状态机、artifact refs、release readiness evidence 与 release gate 已补；release readiness artifact export 待 P39 |
| 6.8 Opinion Writer Agent | 生成可读裁决书 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [ops_read_model_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_read_model_pack.py), [trust_artifact_summary.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_artifact_summary.py), [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py) | 裁决书 artifact refs、audit export manifest、artifact healthcheck 与 ops trust/artifact summary 已补；公验产品面展示待 P39 |

## 5. 关键结论（当前真实状态）

1. 当前阶段已完成 `P38 stage closure`，P35/P36/P37 主体成果仍作为底座：
   - 六对象 typed ledger snapshot 与 `judge_ledger_snapshots` 表。
   - durable workflow mainline 与 ordered events。
   - Clerk/Recorder/Claim/Evidence/Panel/Fairness/Arbiter/Opinion role runtime 主链。
   - Opinion Writer ledger-driven fact lock。
   - LLM/Knowledge Gateway core convergence。
   - trace/replay/audit store boundary split。
   - durable trust registry store、phase/final write-through 与 challenge/review 状态机。
   - Artifact Store port、local adapter、S3-compatible adapter 边界与 manifest hash。
   - Public Verification visibility/redaction/readiness contract。
   - ops read model readContract、lifecycle overview 与 ops trust monitoring。
   - NPC/Room QA advisory-only shell。
2. P38 主体成果是把 P37 的“生产可信外部化准备”推进为“证据自动化与发布门禁可运营化”：
   - runtime ops pack 与 stage closure evidence 已能自动识别最新 archive、completed/todo linkage 与 real-env debt。
   - Registry release gate 已输出统一 `releaseReadinessEvidence`，并被 governance overview、policy gate simulation 与 ops trust monitoring 复用。
   - Public Verification 合同已新增 `cacheProfile` 与 `proxyRequired`，ready/not-ready 响应均有稳定合法结构，仍要求 chat proxy 代理访问。
   - Artifact Store 已输出 no-secret healthcheck evidence；S3 readiness 只暴露配置布尔值，真实 roundtrip 仅显式开启。
   - Fairness benchmark、real sample manifest 与 panel shadow evidence 已归一为 `fairness-panel-evidence-normalized-v1`。
   - `ops_read_model_trust_projection.py` 已拆出 trust/public verification/artifact coverage 与 release gate rows projection。
   - P38 local reference regression 已刷新 runtime ops 与 real-env closure，本地参考为 `local_reference_ready`，真实 readiness 仍为 `env_blocked`。
3. 方案第15章已有多项合同和路由进入主链：
   - [trust_commitment_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_commitment_contract.py)
   - [trust_verdict_attestation_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_verdict_attestation_contract.py)
   - [trust_challenge_review_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_challenge_review_contract.py)
   - [trust_public_verify_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_public_verify_contract.py)
   - [trust_audit_anchor_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_audit_anchor_contract.py)
   - [trust_kernel_version_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_kernel_version_contract.py)
4. 当前最核心的未完成项已从“AI 服务内部能不能可信输出”转为“可信能力能不能通过主业务门面安全给产品使用”：
   - public verification chat_server 代理尚未落地。
   - Web/Desktop 共享公验 read model 尚未落地。
   - Evidence Agent citation verifier / evidence gate 输入仍待 P39。
   - release readiness evidence 仍需进一步归档为 artifact/manifest 可引用证据。
   - 真实样本、真实 AI provider/callback 环境、生产对象存储真实验收与真实服务窗口仍不可用。
5. 所有真实环境结论必须等 `REAL_CALIBRATION_ENV_READY=true`、真实样本、真实服务窗口、生产对象存储与 P39 readiness 输入具备后再写入；不得把 `local_reference_ready` 写成 real-env `pass`。

## 6. 下一步优先级

1. 执行 `ai-judge-p39-public-verification-chat-proxy-pack`，在不开放 AI 服务直连的前提下，让 `chat_server` 代理 AI 内部 public verification 合同，并处理权限、缓存、错误码与 no-secret redaction。
2. 执行 `ai-judge-p39-public-verification-client-read-model-pack`，让 Web/Desktop 共享 domain 能消费 `verificationReadiness`、`cacheProfile` 与公开验证摘要。
3. 执行 `ai-judge-p39-citation-verifier-evidence-gate-pack`，补齐 Evidence Agent 的 citation verifier、missing/weak citation reason code 与 release/ops evidence 输入。
4. 执行 `ai-judge-p39-release-readiness-artifact-export-pack`，将 `releaseReadinessEvidence` 归档为 artifact ref / manifest hash，可供 runtime ops、stage closure 与 audit anchor 引用。
5. 执行 `ai-judge-p39-registry-trust-route-hotspot-split-pack`，继续下沉 public verify / release readiness / ops projection helper，保持顶层合同稳定。
6. 执行 `ai-judge-p39-local-reference-regression-pack` 与 `ai-judge-p39-stage-closure-execute`，刷新本地参考证据并完成阶段收口。
7. 等真实环境具备后执行 `ai-judge-p37-real-env-pass-window-execute-on-env` 或后续等价 real-env pass window，补齐真实环境 `pass` 证据；在此之前继续保持 `env_blocked`。

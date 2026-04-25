# AI_Judge_Service 企业级 Agent 方案章节完成度映射（2026-04-13）

更新时间：2026-04-25
状态：已更新（对齐 P36 stage closure；P36 已完成 verifiable trust registry、artifact store local adapter、audit anchor export、ops trust/artifact coverage、route dependency split 与 local reference regression）
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
| Enterprise MVP（方案 Phase 1） | 基本落地 | 8 Agent 官方裁决主链、六对象 ledger、workflow、trace/replay、review/audit 已形成本地闭环 |
| Fairness Hardened（方案 Phase 2） | 部分落地（高） | Fairness gate、panel disagreement、local reference benchmark/freeze 已完成；真实样本 benchmark 与 real-env pass 待窗口 |
| Adaptive Judge Platform（方案 Phase 3） | 部分落地 | gateway core、policy/prompt/tool registry、ops read model 已推进；auto-calibration、多模型 panel 生产化仍未完成 |
| Verifiable Trust Layer（方案第15章 Phase A） | 基本落地（本地参考） | commitment/attestation/challenge/audit/public verify 合同与路由已出现；P36 已完成 durable trust registry store/write-through、public verify redaction、challenge review durable state machine、本地 artifact store adapter、audit anchor manifest export、ops trust/artifact coverage 与 local reference regression；外部公开验证、生产对象存储与 real-env pass 仍待后续 |
| Protocol Expansion Layer（方案第15章 Phase B-D） | 未落地（按计划后置） | Public verification 外部化、Identity Proof、Constitution Registry、Reason Passport、on-chain anchor 均不属于当前主线 |
| 真实环境闭环 | 环境阻塞 | 当前证据为 `local_reference_ready`，不得宣称 real-env `pass` |

一句话结论：

`截至 P36 stage closure，AI Judge 已从“评分器/大 prompt 服务”推进到“本地可验证的裁判庭主链”：durable trust registry、主链 write-through、公开字段红线、challenge/review 状态机、本地 artifact refs、audit anchor manifest、ops trust/artifact coverage 与 local reference regression 均已闭环；下一步只应在真实环境窗口具备后补 real-env pass，或进入下一轮规划。`

## 3. 章节级完成度总览

| 方案章节 | 目标摘要 | 当前完成度 | 核心证据 | 结论 |
| --- | --- | --- | --- | --- |
| 1. 一句话结论 | 从“评分器”升级为“裁判庭系统” | 基本落地 | [P36 归档](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260425T073224Z-ai-judge-stage-closure-execute.md), [P35 归档](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260425T022246Z-ai-judge-stage-closure-execute.md) | 裁判庭主链与本地可信制度层已落地，生产化证据仍依赖真实环境窗口 |
| 2. 产品目标重新定义 | 丰富判决展示、公正、可运营 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [ops_read_model_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_read_model_pack.py) | 富展示、review/draw/blocked 语义与 ops 读面已成型；真实环境可运营性待补 |
| 3. 为什么必须是 Agent | 分工、状态、工具、门禁 | 基本落地 | [judge_workflow_roles.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_workflow_roles.py), [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py) | 8 Agent role runtime 与 advisory shell 均已出现；交互型 Agent 仍只做外壳 |
| 4. 总体设计理念 | 公平优先、事实先锁定、可回放 | 基本落地 | [trace_store_boundaries.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/trace_store_boundaries.py), [ai_judge_runtime_ops_pack.md](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_runtime_ops_pack.md) | locked verdict、opinion fact lock、trace/replay/audit 均已接通；real-env 仍后置 |
| 5. 推荐架构总览 | 法庭式流水线 + Ops/Replay/Audit | 基本落地 | [app/](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app), [route_group_trust.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_trust.py) | 模块化单体与 route group 架构已稳定；P36 继续补 trust/artifact core |
| 6. 法庭式 Agent 分工 | 8 类 Agent 职责闭环 | 基本落地 | 见“第4节 Agent 子项映射” | 官方裁决链角色齐备；运行 profile、多模型与生产校准仍可增强 |
| 7. 企业级核心数据对象 | Case/Claim/Evidence/Verdict/Fairness/Opinion | 基本落地 | [ledger_objects.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/ledger_objects.py), [repository.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/facts/repository.py), [20260424_0008_judge_ledger_snapshots.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/alembic/versions/20260424_0008_judge_ledger_snapshots.py), [models.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/artifacts/models.py) | 六对象 typed snapshot 与 `judge_ledger_snapshots` 已落地；artifact refs/manifest 已有本地基础，并已被 audit anchor manifest hash 引用 |
| 8. 丰富判决内容 | 用户层/高级层/Ops 层展示 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [case_read_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/case_read_routes.py) | 用户报告、ops summary、case overview 已具备；高级可视化仍可继续产品化 |
| 9. 公平性保证机制 | 盲化、镜像、扰动、复核、benchmark | 部分落地（高） | [fairness_analysis.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_analysis.py), [ai_judge_fairness_benchmark_freeze.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_fairness_benchmark_freeze.sh) | 本地 reference freeze 已达成；真实样本 benchmark、style/swap 生产数据闭环待 on-env |
| 10. 企业级工程架构 | Gateway/Orchestrator/Runtime/Ledger/Ops | 基本落地 | [orchestrator.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/core/workflow/orchestrator.py), [gateway_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/gateway_runtime.py), [repository.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/trust/repository.py), [bootstrap_trust_ops_dependencies.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/bootstrap_trust_ops_dependencies.py), [local_store.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/artifacts/local_store.py), [ai_judge_audit_anchor_export_local.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_audit_anchor_export_local.sh) | Postgres workflow、gateway core、ledger/read model、trust registry store/write-through、route dependency split、本地 Artifact Store adapter 与本地 audit anchor export 已形成；生产对象存储待真实环境 |
| 11. Agent Runtime 设计 | Prompt/Tool/Policy Registry + Model Gateway | 部分落地（高） | [policy_registry.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/policy_registry.py), [registry_product_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_product_runtime.py) | registry 与 gateway trace 已进入主链；多模型 panel 与 shadow rollout 生产化待后续 |
| 12. 企业级可靠性要求 | 幂等、callback、trace、replay、观测 | 基本落地 | [callback_client.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/callback_client.py), [replay_audit_ops.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/replay_audit_ops.py), [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py), [scripts/harness/](/Users/panyihang/Documents/EchoIsle/scripts/harness) | 本地可靠性与证据脚本充足；artifact refs/manifest 与 audit anchor 本地导出已补，真实环境稳定性待补 |
| 13. 对外接口模型 | cases/trace/replay/fairness/review/policies | 基本落地 | [route_group_case_read.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_case_read.py), [route_group_replay.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_replay.py), [route_group_trust.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_trust.py), [trust_public_verify_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_public_verify_contract.py), [trust_artifact_summary.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_artifact_summary.py) | 内部接口层已覆盖大多数设计面；public verify visibility/redaction 与 ops trust/artifact coverage 已稳定，本轮仍不开放客户端直连 AI 服务 |
| 14. 继承映射表 | 从旧逻辑到新架构的继承策略 | 已落地 | [P35 归档](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260425T022246Z-ai-judge-stage-closure-execute.md) | P35 已完成从旧 pipeline 资产到六对象/role runtime/gateway core 的迁移主线 |
| 15. 可验证信任层与协议化扩展 | commitment/attestation/challenge/protocol | 基本落地（本地参考） | [trust_phasea.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_phasea.py), [trust_public_verify_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_public_verify_contract.py), [trust_audit_anchor_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_audit_anchor_contract.py), [trust_challenge_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_challenge_runtime_routes.py), [repository.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/trust/repository.py), [trust_artifact_summary.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_artifact_summary.py), [models.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/artifacts/models.py), [local_store.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/artifacts/local_store.py), [ai_judge_audit_anchor_export_local.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_audit_anchor_export_local.sh), [20260425_0009_judge_trust_registry_snapshots.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/alembic/versions/20260425_0009_judge_trust_registry_snapshots.py) | Phase A 在本地参考口径下已闭环：trust 合同、路由、durable registry、write-through、public verify 红线、challenge 状态机、artifact refs/manifest、audit anchor export 与 ops trust/artifact summary 均已落地；外部验证与 real-env pass 待后续 |
| 16. 不推荐设计边界 | 不做画像污染、不过早 memory 主链等 | 基本守住 | [assistant_agent_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_agent_routes.py), [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py) | NPC/Room QA 已标注 advisory-only；topic memory/Reason Passport 未进入单场裁决主链 |
| 17. 推荐落地路线 | Phase1/2/3 路线图 | Phase1 基本完成，Phase2/3 本地参考完成关键可信层 | [P36 归档](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260425T073224Z-ai-judge-stage-closure-execute.md), [completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md), [todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md) | 当前已完成 P36 本地可信层收口，下一轮应规划真实环境补证或生产化公开验证 |
| 18. 最后产品判断 | 企业级裁判系统目标态 | 方向成立，未完全完成 | 同上 | 已具备“制度化裁判庭”的本地形态；距离完整目标态还差真实环境、生产对象存储、公开验证外部化与协议扩展 |

## 4. Agent 子项映射（方案第6章）

| Agent 子项 | 目标 | 当前完成度 | 证据 | 主要缺口 |
| --- | --- | --- | --- | --- |
| 6.1 Clerk Agent | 收案、盲化、准入门禁 | 基本落地 | [judge_workflow_roles.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_workflow_roles.py), [judge_app_domain.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_app_domain.py) | 语义级盲化策略仍可继续结合真实样本校准 |
| 6.2 Recorder Agent | 时间线重建与结构化 transcript | 基本落地 | [judge_workflow_roles.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_workflow_roles.py), [trace_store_boundaries.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/trace_store_boundaries.py), [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py) | transcript/replay snapshot 已具备本地 artifact refs，audit anchor 可通过 manifest hash 引用；生产对象存储待真实环境 |
| 6.3 Claim Graph Agent | 争点图谱构建 | 基本落地 | [claim_graph.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/claim_graph.py), [judge_mainline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_mainline.py) | 深层 claim graph 运营检索与可视化仍可增强 |
| 6.4 Evidence Agent | 检索与证据核验 | 基本落地 | [evidence_ledger.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/evidence_ledger.py), [runtime_rag.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/runtime_rag.py), [rag_retriever.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/rag_retriever.py), [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py) | Evidence pack artifact refs 本地基础已补；citation verifier 产品化待后续 |
| 6.5 Judge Panel Agent | 多法官独立判定 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [panel_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/panel_runtime_routes.py) | 多模型 panel 与策略版本生产化仍待后续 |
| 6.6 Fairness Sentinel Agent | 稳定性与公平门禁 | 部分落地（高） | [fairness_analysis.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_analysis.py), [fairness_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_runtime_routes.py) | 真实样本 benchmark 与 on-env pass 待环境 |
| 6.7 Chief Arbiter Agent | 汇总裁决与状态决策 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [judge_mainline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_mainline.py), [repository.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/trust/repository.py), [trust_challenge_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_challenge_runtime_routes.py), [route_group_judge_command.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_judge_command.py), [models.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/artifacts/models.py) | durable trust registry store、phase/final write-through、challenge/review 状态机、artifact refs 与 audit anchor manifest export 已补 |
| 6.8 Opinion Writer Agent | 生成可读裁决书 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [ops_read_model_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_read_model_pack.py), [trust_artifact_summary.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_artifact_summary.py), [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py) | 裁决书 artifact refs、audit export manifest 与 ops trust/artifact summary 已补；高级展示仍可继续 |

## 5. 关键结论（当前真实状态）

1. 当前阶段已完成 `P36 stage closure`，P35 主体成果仍作为底座：
   - 六对象 typed ledger snapshot 与 `judge_ledger_snapshots` 表。
   - durable workflow mainline 与 ordered events。
   - Clerk/Recorder/Claim/Evidence/Panel/Fairness/Arbiter/Opinion role runtime 主链。
   - Opinion Writer ledger-driven fact lock。
   - LLM/Knowledge Gateway core convergence。
   - trace/replay/audit store boundary split。
   - ops read model readContract 与 lifecycle overview。
   - NPC/Room QA advisory-only shell。
   - local reference regression pack，状态为 `local_reference_ready`。
2. P36 主体成果是把可信制度层从“合同与路由雏形”推进为本地参考闭环：
   - durable trust registry store 与 phase/final write-through。
   - public verify redaction / visibility contract。
   - challenge & review durable state machine。
   - Artifact Store port + local adapter + manifest hash。
   - audit anchor local export。
   - ops/case/replay trust artifact summary。
   - route dependency hotspot split。
   - P36 local reference regression，状态为 `local_reference_ready`。
3. 方案第15章已有多项合同和路由进入主链：
   - [trust_commitment_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_commitment_contract.py)
   - [trust_verdict_attestation_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_verdict_attestation_contract.py)
   - [trust_challenge_review_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_challenge_review_contract.py)
   - [trust_public_verify_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_public_verify_contract.py)
4. 当前最核心的未完成项不是“能不能判”或“本地能不能验证”，而是生产化外部条件：真实样本、真实 AI provider / callback 环境、生产对象存储、公开验证外部化与 real-env pass window。
5. 所有真实环境结论必须等 `REAL_CALIBRATION_ENV_READY=true` 与真实样本窗口具备后再写入，不得把 `local_reference_ready` 写成 real-env `pass`。

## 6. 下一步优先级

1. 下一轮先生成新活动计划：`ai-judge-next-iteration-planning`。
2. 在真实环境具备后执行 `ai-judge-p36-real-env-pass-window-execute-on-env`，补齐真实环境 `pass` 证据。
3. 若继续推进产品化，应优先评估生产对象存储、公开验证外部化、真实样本 fairness benchmark 与多模型 panel 生产化。

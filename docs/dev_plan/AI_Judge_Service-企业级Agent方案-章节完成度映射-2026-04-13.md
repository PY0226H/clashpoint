# AI_Judge_Service 企业级 Agent 方案章节完成度映射（2026-04-13）

更新时间：2026-04-25
状态：已更新（对齐 P37 stage closure；P38 已启动 runtime ops evidence automation 与 public verification proxy readiness 主线）
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
| Enterprise MVP（方案 Phase 1） | 基本落地 | 8 Agent 官方裁决主链、六对象 ledger、workflow、trace/replay、review/audit、富裁决报告与受保护复核语义已形成本地闭环 |
| Fairness Hardened（方案 Phase 2） | 部分落地（高） | Fairness gate、panel disagreement、local reference benchmark/freeze、真实样本 benchmark readiness 与 panel shadow evaluation 已完成；真实样本实跑与 real-env pass 待窗口 |
| Adaptive Judge Platform（方案 Phase 3） | 部分落地 | gateway core、policy/prompt/tool registry、ops read model、release gate、panel shadow readiness 已推进；auto-calibration、多模型 panel 生产化与统一 release readiness evidence 待 P38 |
| Verifiable Trust Layer（方案第15章 Phase A） | 基本落地（本地参考） | P37 已在 P36 durable trust registry 基础上补齐生产 Artifact Store readiness、Public Verification boundary、audit anchor manifest、ops trust monitoring、release gate hardening 与 local reference regression；外部代理验证、生产对象存储真实验收与 real-env pass 仍待后续 |
| Protocol Expansion Layer（方案第15章 Phase B-D） | 未落地（按计划后置） | Identity Proof、Constitution Registry、Reason Passport、第三方 review network、on-chain anchor 均不属于当前主线 |
| 真实环境闭环 | 环境阻塞 | 当前证据为 `local_reference_ready` / `env_blocked`；缺真实样本、真实 provider/callback、生产对象存储与真实服务窗口，不得宣称 real-env `pass` |

一句话结论：

`截至 P37 stage closure，AI Judge 已从“本地可验证的裁判庭主链”推进到“本地参考口径下的生产可信外部化准备”：Artifact Store 生产配置、Public Verification readiness、real-env evidence readiness、fairness real sample benchmark 入口、panel shadow evaluation、registry release gate hardening、ops trust monitoring 与 local reference regression 均已落地；P38 应优先推进 runtime ops 自动回填、release readiness evidence、public verification chat proxy contract 与生产 artifact healthcheck，真实环境 pass 继续等待环境窗口。`

## 3. 章节级完成度总览

| 方案章节 | 目标摘要 | 当前完成度 | 核心证据 | 结论 |
| --- | --- | --- | --- | --- |
| 1. 一句话结论 | 从“评分器”升级为“裁判庭系统” | 基本落地 | [P37 归档](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260425T111521Z-ai-judge-stage-closure-execute.md), [completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md) | 裁判庭主链、本地可信制度层与生产可信外部化准备均已成型；真实环境 pass 仍依赖窗口 |
| 2. 产品目标重新定义 | 丰富判决展示、公正、可运营 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [ops_read_model_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_read_model_pack.py), [ops_trust_monitoring.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_trust_monitoring.py) | 富展示、review/draw/blocked、ops trust monitoring 与 release readiness 读面已出现；真实环境可运营性待补 |
| 3. 为什么必须是 Agent | 分工、状态、工具、门禁 | 基本落地 | [judge_workflow_roles.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_workflow_roles.py), [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py) | 8 Agent role runtime 与 advisory shell 均已出现；P37 继续保持 shadow/ops 能力不污染官方裁决链 |
| 4. 总体设计理念 | 公平优先、事实先锁定、可回放 | 基本落地 | [trace_store_boundaries.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/trace_store_boundaries.py), [ai_judge_runtime_ops_pack.md](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_runtime_ops_pack.md), [ai_judge_real_env_window_closure.md](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_real_env_window_closure.md) | locked verdict、opinion fact lock、trace/replay/audit 与 local reference regression 均已接通；real-env 仍后置 |
| 5. 推荐架构总览 | 法庭式流水线 + Ops/Replay/Audit | 基本落地 | [app/](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app), [route_group_trust.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_trust.py), [registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py) | 模块化单体与 route group 架构稳定；P37 已补 release gate 与 ops trust monitoring，P38 继续补 evidence automation |
| 6. 法庭式 Agent 分工 | 8 类 Agent 职责闭环 | 基本落地 | 见“第4节 Agent 子项映射” | 官方裁决链角色齐备；panel shadow、真实样本 benchmark 与多模型生产化仍是增强项 |
| 7. 企业级核心数据对象 | Case/Claim/Evidence/Verdict/Fairness/Opinion | 基本落地 | [ledger_objects.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/ledger_objects.py), [repository.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/facts/repository.py), [models.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/artifacts/models.py), [s3_store.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/artifacts/s3_store.py) | 六对象 typed snapshot 与 Artifact refs/manifest 已落地；S3 compatible adapter 已有本地边界，真实对象存储验收待环境 |
| 8. 丰富判决内容 | 用户层/高级层/Ops 层展示 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [case_read_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/case_read_routes.py), [trust_artifact_summary.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_artifact_summary.py) | 用户报告、ops summary、case overview 与 trust/artifact summary 已具备；高级可视化仍可继续产品化 |
| 9. 公平性保证机制 | 盲化、镜像、扰动、复核、benchmark | 部分落地（高） | [fairness_analysis.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_analysis.py), [fairness_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_runtime_routes.py), [panel_runtime_profile_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/panel_runtime_profile_contract.py) | 本地 reference freeze、真实样本 readiness 与 panel shadow evaluation 已达成；真实样本实跑与 on-env pass 待环境 |
| 10. 企业级工程架构 | Gateway/Orchestrator/Runtime/Ledger/Ops | 基本落地 | [orchestrator.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/core/workflow/orchestrator.py), [gateway_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/gateway_runtime.py), [repository.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/trust/repository.py), [bootstrap_trust_ops_dependencies.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/bootstrap_trust_ops_dependencies.py), [s3_store.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/artifacts/s3_store.py) | Postgres workflow、gateway core、ledger/read model、trust registry、route dependency split、本地和 S3-compatible artifact store 边界均已出现；生产健康检查待 P38 |
| 11. Agent Runtime 设计 | Prompt/Tool/Policy Registry + Model Gateway | 部分落地（高） | [policy_registry.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/policy_registry.py), [registry_product_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_product_runtime.py), [registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py) | registry 与 gateway trace 已进入主链；release gate 已绑定 benchmark/trust/artifact readiness，统一 evidence export 待 P38 |
| 12. 企业级可靠性要求 | 幂等、callback、trace、replay、观测 | 基本落地 | [callback_client.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/callback_client.py), [replay_audit_ops.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/replay_audit_ops.py), [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py), [ops_trust_monitoring.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_trust_monitoring.py) | 本地可靠性、证据脚本、artifact refs/manifest、audit anchor 与 ops monitoring 已补；真实 provider/callback 稳定性待真实环境 |
| 13. 对外接口模型 | cases/trace/replay/fairness/review/policies | 基本落地 | [route_group_case_read.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_case_read.py), [route_group_replay.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_replay.py), [route_group_trust.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/route_group_trust.py), [trust_public_verify_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_public_verify_contract.py) | 内部接口层已覆盖大多数设计面；public verification readiness 已稳定，P38 需要推进 chat proxy contract，仍不开放客户端直连 AI 服务 |
| 14. 继承映射表 | 从旧逻辑到新架构的继承策略 | 已落地 | [P35 归档](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260425T022246Z-ai-judge-stage-closure-execute.md), [P37 归档](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260425T111521Z-ai-judge-stage-closure-execute.md) | 旧 pipeline 资产已迁移到六对象/role runtime/gateway core；P37 把可信外部化准备接入该主线 |
| 15. 可验证信任层与协议化扩展 | commitment/attestation/challenge/protocol | 基本落地（本地参考） | [trust_phasea.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_phasea.py), [trust_public_verify_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_public_verify_contract.py), [trust_audit_anchor_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_audit_anchor_contract.py), [trust_challenge_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_challenge_runtime_routes.py), [repository.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/trust/repository.py), [trust_artifact_summary.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_artifact_summary.py), [s3_store.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/artifacts/s3_store.py), [ops_trust_monitoring.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_trust_monitoring.py) | Phase A 在本地参考口径下基本闭环；public verification 外部代理、生产 artifact healthcheck 与 real-env pass 待 P38/真实环境 |
| 16. 不推荐设计边界 | 不做画像污染、不过早 memory 主链等 | 基本守住 | [assistant_agent_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/assistant_agent_routes.py), [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py) | NPC/Room QA 已标注 advisory-only；topic memory/Reason Passport 未进入单场裁决主链 |
| 17. 推荐落地路线 | Phase1/2/3 路线图 | Phase1 基本完成，Phase2/3 本地参考完成关键可信层 | [P37 归档](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260425T111521Z-ai-judge-stage-closure-execute.md), [completed.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md), [todo.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md), [当前开发计划.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md) | 当前已进入 P38：runtime ops evidence automation、release readiness evidence、public verification proxy readiness 与 artifact healthcheck |
| 18. 最后产品判断 | 企业级裁判系统目标态 | 方向成立，未完全完成 | 同上 | 已具备“制度化裁判庭 + 本地可信外部化准备”的形态；距离完整目标态还差真实环境、外部代理公验、生产对象存储真实验收与协议扩展 |

## 4. Agent 子项映射（方案第6章）

| Agent 子项 | 目标 | 当前完成度 | 证据 | 主要缺口 |
| --- | --- | --- | --- | --- |
| 6.1 Clerk Agent | 收案、盲化、准入门禁 | 基本落地 | [judge_workflow_roles.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_workflow_roles.py), [judge_app_domain.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_app_domain.py) | 语义级盲化策略仍可继续结合真实样本校准 |
| 6.2 Recorder Agent | 时间线重建与结构化 transcript | 基本落地 | [judge_workflow_roles.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_workflow_roles.py), [trace_store_boundaries.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/trace_store_boundaries.py), [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py), [s3_store.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/artifacts/s3_store.py) | transcript/replay snapshot 已具备 artifact refs 与 S3-compatible store 边界；生产对象存储 roundtrip 待真实环境 |
| 6.3 Claim Graph Agent | 争点图谱构建 | 基本落地 | [claim_graph.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/claim_graph.py), [judge_mainline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_mainline.py) | 深层 claim graph 运营检索与可视化仍可增强 |
| 6.4 Evidence Agent | 检索与证据核验 | 基本落地 | [evidence_ledger.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/evidence_ledger.py), [runtime_rag.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/runtime_rag.py), [rag_retriever.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/rag_retriever.py), [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py) | Evidence pack artifact refs 已补；citation verifier 与真实样本 evidence normalization 待后续 |
| 6.5 Judge Panel Agent | 多法官独立判定 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [panel_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/panel_runtime_routes.py), [panel_runtime_profile_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/panel_runtime_profile_contract.py) | panel shadow evaluation 已作为观测与 release gate 输入出现；多模型 panel 生产实跑待真实环境 |
| 6.6 Fairness Sentinel Agent | 稳定性与公平门禁 | 部分落地（高） | [fairness_analysis.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_analysis.py), [fairness_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_runtime_routes.py), [registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py) | 真实样本 benchmark readiness 已有；真实样本实跑、release readiness evidence 统一化与 on-env pass 待后续 |
| 6.7 Chief Arbiter Agent | 汇总裁决与状态决策 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [judge_mainline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/judge_mainline.py), [repository.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/trust/repository.py), [trust_challenge_runtime_routes.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_challenge_runtime_routes.py), [registry_release_gate.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_release_gate.py) | durable trust registry、challenge/review 状态机、artifact refs 与 release gate 已补；release readiness evidence export 待 P38 |
| 6.8 Opinion Writer Agent | 生成可读裁决书 | 基本落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [ops_read_model_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_read_model_pack.py), [trust_artifact_summary.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_artifact_summary.py), [artifact_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/artifact_pack.py) | 裁决书 artifact refs、audit export manifest 与 ops trust/artifact summary 已补；高级展示仍可继续 |

## 5. 关键结论（当前真实状态）

1. 当前阶段已完成 `P37 stage closure`，P35/P36 主体成果仍作为底座：
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
2. P37 主体成果是把 P36 的“本地可信制度层”推进为生产可信外部化准备：
   - production Artifact Store readiness 配置与 fail-closed 边界。
   - Public Verification boundary：verificationVersion、requestKey、verificationReadiness 与 chat proxy required 语义。
   - Real-env evidence readiness：真实窗口输入、blocker codes、local reference 与 real evidence links。
   - Fairness real sample benchmark readiness 与 pending_real_samples 防假 pass。
   - Panel shadow evaluation：shadowEnabled、decisionAgreement、drift/release-gate 信号。
   - Registry release gate hardening：dependency、fairness benchmark、panel shadow、artifact/public verification/trust registry readiness 统一门禁。
   - Ops trust monitoring：artifact、公验、challenge、registry、panel shadow 与 real-env evidence 状态聚合。
   - Route/test hotspot continuation 与 P37 local reference regression。
3. 方案第15章已有多项合同和路由进入主链：
   - [trust_commitment_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_commitment_contract.py)
   - [trust_verdict_attestation_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_verdict_attestation_contract.py)
   - [trust_challenge_review_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_challenge_review_contract.py)
   - [trust_public_verify_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_public_verify_contract.py)
   - [trust_audit_anchor_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_audit_anchor_contract.py)
4. 当前最核心的未完成项不是“能不能判”或“本地能不能验证”，而是生产化外部条件与证据自动化：真实样本、真实 AI provider/callback 环境、生产对象存储真实验收、public verification chat proxy、release readiness evidence 与 real-env pass window。
5. 所有真实环境结论必须等 `REAL_CALIBRATION_ENV_READY=true`、真实样本、真实服务窗口、生产对象存储与 P37/P38 readiness 输入具备后再写入；不得把 `local_reference_ready` 写成 real-env `pass`。

## 6. 下一步优先级

1. 执行 `ai-judge-p38-runtime-ops-pack-phase2-auto-backfill`，让 runtime ops pack、stage closure evidence、completed/todo 与最新 archive 自动形成闭环，减少人工修补。
2. 执行 `ai-judge-p38-release-readiness-evidence-export-pack`，把 registry release gate 组件状态沉淀为统一 evidence artifact。
3. 执行 `ai-judge-p38-public-verification-chat-proxy-contract-pack`，在不开放 AI 服务直连的前提下稳定 public verification 代理合同。
4. 执行 `ai-judge-p38-production-artifact-healthcheck-pack`，补齐 S3-compatible 对象存储 no-secret healthcheck 与 readiness evidence。
5. 等真实环境具备后执行 `ai-judge-p37-real-env-pass-window-execute-on-env`，补齐真实环境 `pass` 证据；在此之前继续保持 `env_blocked`。

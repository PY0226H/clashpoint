# AI_Judge_Service 企业级 Agent 方案章节完成度映射（2026-04-13）

更新时间：2026-04-19  
状态：已更新（对齐 P22-M1~M5：courtroom 角色契约 + app_factory 拆分 + read-model 契约冻结 + ops 导出对齐 + 本地回归包 v4 已完成）  
映射对象：[AI_judge_service 企业级 Agent 服务设计方案（2026-04-13）](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/AI_Judge_Service-企业级Agent服务设计方案-2026-04-13.md)

## 1. 判定口径

1. 已落地：主链代码已存在，且可通过当前测试或收口证据验证。
2. 部分落地：主链能力已上线，但仍缺关键子能力或治理闭环。
3. 未落地：当前仅为设计目标，仓库内无对应主链实现。
4. 环境阻塞：实现入口存在，但最终验收依赖真实环境或真实样本。

## 2. 章节级完成度总览

| 方案章节 | 目标摘要 | 当前完成度 | 核心证据 | 结论 |
| --- | --- | --- | --- | --- |
| 1. 一句话结论 | 从“评分器”升级为“裁判庭系统” | 部分落地（高） | [当前开发计划](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) | 裁判主链已平台化并具备 challenge/fairness/replay 能力，但多 Agent 平台入口仍在下一阶段 |
| 2. 产品目标重新定义 | 丰富判决展示、公正、可运营 | 部分落地（高） | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [AI_Judge_Fairness_Benchmark_冻结口径-2026-04-15.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/AI_Judge_Fairness_Benchmark_冻结口径-2026-04-15.md), [AI_Judge_Runtime_SLA_冻结口径-2026-04-15.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/AI_Judge_Runtime_SLA_冻结口径-2026-04-15.md) | 富展示和公平治理主链已成型；真实环境 pass 与运营化治理仍待收口 |
| 3. 为什么必须是 Agent | 具备分工、状态、工具、门禁 | 部分落地 | [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py), [test_agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/tests/test_agent_runtime.py) | 已具备 runtime 壳与分工映射，但 NPC/Room QA 等新 Agent 入口尚未落地 |
| 4. 总体设计理念 | 公平优先、事实先锁定、可回放 | 部分落地（高） | [trace_store.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/trace_store.py), [ai_judge_runtime_ops_pack.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_runtime_ops_pack.sh), [ai_judge_real_env_window_closure.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_real_env_window_closure.sh) | trace/replay/failed callback/challenge/fairness 收口已接通；real-env 仍是最后阻塞 |
| 5. 推荐架构总览 | 法庭式流水线 | 部分落地（高） | [app/](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app), [infra/db/models.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/db/models.py), [ops_read_model_pack.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/ops_read_model_pack.py) | 分层架构与六对象主链已稳定，Prompt/Tool Registry 产品化治理读面已落地；后续仍需继续降低 `app_factory` 集中复杂度 |
| 6. 法庭式 Agent 分工 | 8 类 Agent 职责闭环 | 部分落地 | 见“第3节 Agent 子项映射” | Clerk/Recorder/Fairness/Arbiter/Opinion 已有主链；Evidence 深化与 Agent 入口扩展待后续阶段 |
| 7. 企业级核心数据对象 | Case/Claim/Evidence/Verdict/Fairness/Opinion | 部分落地（高） | [models.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/db/models.py), [facts/models.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/facts/models.py), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) | 六对象落库 + case 级 courtroom read model 已连通；真实环境口径冻结仍待窗口 |
| 8. 丰富判决内容 | 用户层/高级层/Ops 层三层展示 | 部分落地（高） | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py), [ai_judge_ops_read_model_export.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_ops_read_model_export.sh) | 用户展示主字段稳定，Ops read model 已升级 v5（新增 registry prompt/tool governance、evidence claim queue、courtroom drilldown）；高级解释仍可继续增强 |
| 9. 公平性保证机制 | 盲化、镜像、扰动、复核、benchmark | 部分落地（高） | [models.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/models.py), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py), [ai_judge_fairness_benchmark_freeze.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_fairness_benchmark_freeze.sh) | 盲化 + panel gate + review/challenge + drift governance v1 + shadow-linked release gate 已落地；real-env pass 待完成 |
| 10. 企业级工程架构 | Gateway/Orchestrator/Runtime/Ledger/Ops | 部分落地 | [core/workflow/orchestrator.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/core/workflow/orchestrator.py), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) | 模块化单体满足当前阶段目标，后续不阻塞业务情况下再评估拆分 |
| 11. Agent Runtime 设计 | Prompt/Tool/Policy Registry + Model Gateway | 部分落地（高） | [policy_registry.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/policy_registry.py), [registry_product_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/registry_product_runtime.py), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) | policy/prompt/tool 主链与 prompt-tool governance 读面已落地，运行时治理闭环可用；真实环境窗口验证仍待完成 |
| 12. 企业级可靠性要求 | 可靠性/安全/观测/变更安全 | 部分落地（高） | [callback_client.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/callback_client.py), [trace_store.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/trace_store.py), [scripts/harness/](/Users/panyihang/Documents/EchoIsle/scripts/harness) | 幂等、重放、告警、收口自动化已具备；真实环境稳定性结论仍待验证 |
| 13. 对外接口模型 | cases/trace/replay/fairness/review/policies | 部分落地（高） | [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py), [test_app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/tests/test_app_factory.py) | 已新增 `registries/prompt-tool/governance`、`evidence-claim/ops-queue`、`courtroom/drilldown-bundle`，并完成 `ops/read-model/pack v5` 聚合；剩余缺口集中在真实环境验收 |
| 14. 继承映射表 | 从旧逻辑到新架构的继承策略 | 已落地（文档+实现一致） | [当前开发计划](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md), [AI_Judge_Service-企业级Agent服务设计方案-2026-04-13.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/AI_Judge_Service-企业级Agent服务设计方案-2026-04-13.md) | 当前开发轨迹与继承策略一致 |
| 15. 可验证信任层与协议化扩展 | commitment/attestation/challenge/protocol | 部分落地（高） | [trust_attestation.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_attestation.py), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) | attestation + verify + challenge phaseB 已落地；公开可验证承诺与协议层扩展未进入主线 |
| 16. 不推荐设计边界 | 不做画像污染、不过早 memory 主链等 | 部分落地 | [models.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/models.py), [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py) | 已守住主要边界，后续继续防止 NPC/Room QA 侵入官方裁决链 |
| 17. 推荐落地路线 | Phase1/2/3 路线图 | 部分落地（Phase3 主线进行中） | [当前开发计划](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md), [20260419T225103Z-ai-judge-stage-closure-execute.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260419T225103Z-ai-judge-stage-closure-execute.md) | Phase1/2 主链已收敛，当前进入 Phase3 的 P22 执行段（M1~M5 已完成） |
| 18. 最后产品判断 | 企业级裁判系统目标态 | 部分落地（明确推进） | 同上 | 方向正确，工程主链已显著成型；距离“完整目标态”仍有运营化与平台化差距 |

## 3. Agent 子项映射（方案第6章）

| Agent 子项 | 目标 | 当前完成度 | 证据 | 主要缺口 |
| --- | --- | --- | --- | --- |
| 6.1 Clerk Agent | 收案、盲化、准入门禁 | 已落地（核心） | [models.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/models.py), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) | 语义级盲化策略仍可继续细化 |
| 6.2 Recorder Agent | 时间线重建与结构化 transcript | 部分落地（高） | [phase_pipeline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/phase_pipeline.py), [claim_graph.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/claim_graph.py), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) | case 级 courtroom read model 已落地，timeline 细粒度运营检索仍可增强 |
| 6.3 Claim Graph Agent | 争点图谱构建 | 部分落地（高） | [claim_graph.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/claim_graph.py), [models.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/db/models.py), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) | 已有 claim ledger v3，且 courtroom list/ops pack v5 已纳入 claim 轻摘要；claim graph 深层运营检索仍可增强 |
| 6.4 Evidence Agent | 检索与证据核验 | 部分落地（高） | [runtime_rag.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/runtime_rag.py), [rag_retriever.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/rag_retriever.py), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) | 已补齐 evidence/claim ops queue 批量治理入口；证据核验策略与工具注册表仍可继续产品化 |
| 6.5 Judge Panel Agent | 多法官独立判定 | 部分落地（高） | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py) | A/B/C 结构已独立，运行 profile 独立化与策略版本治理待继续深化 |
| 6.6 Fairness Sentinel Agent | 稳定性与公平门禁 | 部分落地（高） | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py), [ai_judge_fairness_benchmark_freeze.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_fairness_benchmark_freeze.sh), [ai_judge_real_env_window_closure.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_real_env_window_closure.sh) | drift governance v1 与 ingest 已落地，且 release gate v2 已接入 shadow；real-env pass 待完成 |
| 6.7 Chief Arbiter Agent | 汇总裁决与状态决策 | 部分落地（高） | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) | 复核/挑战主链已具备，仍需与 registry triple 主链完全绑定 |
| 6.8 Opinion Writer Agent | 生成可读裁决书 | 部分落地（高） | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) | 基础裁决书稳定，Ops v5 输出已纳入 courtroom/review/trust/evidence/registry 摘要；高级解释仍可增强 |

## 4. 关键结论（当前真实状态）

1. 当前阶段已进入 `P22`，且 `M1~M5` 已完成，主链继续向“角色契约显式化 + 结构拆分可持续 + 契约冻结可验证 + 本地证据稳态”推进。
2. 截至 2026-04-19 已完成：
   - `courtroom role contract v1`：在 [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py) 显式冻结 8 角色 stage/input/output/activation 契约，并在 `judgeTrace.agentRuntime` 透出版本字段。
   - `app_factory split v5`：新增 [fairness_case_scan.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/fairness_case_scan.py)，下沉 fairness dashboard/calibration/advisor 的分页扫描逻辑。
   - `read-model contract freeze v4`：新增 [review_queue_contract.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/review_queue_contract.py)，并在 `/internal/judge/courtroom/drilldown-bundle`、`/internal/judge/evidence-claim/ops-queue` 接入契约校验与失败语义。
   - `ops-export-and-artifact-hygiene v2`：增强 [ai_judge_ops_read_model_export.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_ops_read_model_export.sh) 对 drilldown/evidence-claim 冻结字段检查，且 [test_ai_judge_artifact_prune.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/tests/test_ai_judge_artifact_prune.sh) 持续通过。
   - `local regression bundle v4`：完成 `ruff + pytest + runtime_ops_pack(local_reference)` 全量回归，最新工件为 [20260419T231353Z-ai-judge-runtime-ops-pack.summary.json](/Users/panyihang/Documents/EchoIsle/artifacts/harness/20260419T231353Z-ai-judge-runtime-ops-pack.summary.json)。
3. 当前主要阻塞项仍是 `real-env pass window`；本地侧 P22 主链处于可持续迭代状态。

## 5. 下一步优先级（收口后）

1. 完成 `ai-judge-p22-enterprise-consistency-refresh-v5` 文档一致性收口并回写当前计划。
2. 在真实环境窗口可用后执行 `ai-judge-p22-real-env-pass-window-execute-on-env`，补齐 `pass` 证据。
3. 执行 `ai-judge-p22-stage-closure-execute`，归档 P22 阶段计划与证据快照。

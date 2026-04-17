# AI_Judge_Service 企业级 Agent 方案章节完成度映射（2026-04-13）

更新时间：2026-04-17  
状态：已更新（对齐 P13 执行中：baseline freeze 完成 + shadow eval ledger v1 落地）  
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
| 5. 推荐架构总览 | 法庭式流水线 | 部分落地（高） | [app/](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app), [infra/db/models.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/db/models.py) | 分层架构已落地，Claim Ledger 与 Registry 主链可用；Prompt/Tool Registry 仍待产品化 |
| 6. 法庭式 Agent 分工 | 8 类 Agent 职责闭环 | 部分落地 | 见“第3节 Agent 子项映射” | Clerk/Recorder/Fairness/Arbiter/Opinion 已有主链；Evidence 深化与 Agent 入口扩展待后续阶段 |
| 7. 企业级核心数据对象 | Case/Claim/Evidence/Verdict/Fairness/Opinion | 部分落地（高） | [models.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/db/models.py), [facts/models.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/facts/models.py) | `claim_ledger_records`、`fairness_benchmark_runs`、`fairness_shadow_runs`、registry release/audit 等已落库；统一 read model 仍待完善 |
| 8. 丰富判决内容 | 用户层/高级层/Ops 层三层展示 | 部分落地 | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py) | 用户展示主字段已硬切并稳定；高级解释与 Ops read model 还需补齐 |
| 9. 公平性保证机制 | 盲化、镜像、扰动、复核、benchmark | 部分落地（高） | [models.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/models.py), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py), [ai_judge_fairness_benchmark_freeze.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_fairness_benchmark_freeze.sh) | 盲化 + panel gate + review/challenge + drift governance v1 + ingest 已落地；release gate v2 与 real-env pass 待完成 |
| 10. 企业级工程架构 | Gateway/Orchestrator/Runtime/Ledger/Ops | 部分落地 | [core/workflow/orchestrator.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/core/workflow/orchestrator.py), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) | 模块化单体满足当前阶段目标，后续不阻塞业务情况下再评估拆分 |
| 11. Agent Runtime 设计 | Prompt/Tool/Policy Registry + Model Gateway | 部分落地（高） | [policy_registry.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/policy_registry.py), [runtime_policy.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/runtime_policy.py), [当前开发计划](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md) | policy/prompt/tool 主链已具备；下一步聚焦发布治理、门禁联动与外部核验读模型 |
| 12. 企业级可靠性要求 | 可靠性/安全/观测/变更安全 | 部分落地（高） | [callback_client.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/callback_client.py), [trace_store.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/trace_store.py), [scripts/harness/](/Users/panyihang/Documents/EchoIsle/scripts/harness) | 幂等、重放、告警、收口自动化已具备；真实环境稳定性结论仍待验证 |
| 13. 对外接口模型 | cases/trace/replay/fairness/review/policies | 部分落地（高） | [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) | cases/challenges/review/replay/fairness benchmark + shadow runs 已有主链；prompt/tool registry 与 fairness dashboard 导出 API 待补 |
| 14. 继承映射表 | 从旧逻辑到新架构的继承策略 | 已落地（文档+实现一致） | [当前开发计划](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md), [AI_Judge_Service-企业级Agent服务设计方案-2026-04-13.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/AI_Judge_Service-企业级Agent服务设计方案-2026-04-13.md) | 当前开发轨迹与继承策略一致 |
| 15. 可验证信任层与协议化扩展 | commitment/attestation/challenge/protocol | 部分落地（高） | [trust_attestation.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/trust_attestation.py), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) | attestation + verify + challenge phaseB 已落地；公开可验证承诺与协议层扩展未进入主线 |
| 16. 不推荐设计边界 | 不做画像污染、不过早 memory 主链等 | 部分落地 | [models.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/models.py), [agent_runtime.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/applications/agent_runtime.py) | 已守住主要边界，后续继续防止 NPC/Room QA 侵入官方裁决链 |
| 17. 推荐落地路线 | Phase1/2/3 路线图 | 部分落地（Phase2 在途） | [当前开发计划](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md), [archive/20260415T011924Z-ai-judge-plan-reset-archive.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260415T011924Z-ai-judge-plan-reset-archive.md) | Phase1 主要目标已完成，当前在 Phase2 的 P12 收口段 |
| 18. 最后产品判断 | 企业级裁判系统目标态 | 部分落地（明确推进） | 同上 | 方向正确，工程主链已显著成型；距离“完整目标态”仍有运营化与平台化差距 |

## 3. Agent 子项映射（方案第6章）

| Agent 子项 | 目标 | 当前完成度 | 证据 | 主要缺口 |
| --- | --- | --- | --- | --- |
| 6.1 Clerk Agent | 收案、盲化、准入门禁 | 已落地（核心） | [models.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/models.py), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) | 语义级盲化策略仍可继续细化 |
| 6.2 Recorder Agent | 时间线重建与结构化 transcript | 部分落地（高） | [phase_pipeline.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/phase_pipeline.py), [claim_graph.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/claim_graph.py) | timeline/read model 的查询体验仍需增强 |
| 6.3 Claim Graph Agent | 争点图谱构建 | 部分落地（高） | [claim_graph.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/claim_graph.py), [models.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/infra/db/models.py) | 已有 claim ledger v3；需补 challenge/ops 侧专用读模型 |
| 6.4 Evidence Agent | 检索与证据核验 | 部分落地 | [runtime_rag.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/runtime_rag.py), [rag_retriever.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/rag_retriever.py) | 证据核验策略与工具注册表仍需产品化 |
| 6.5 Judge Panel Agent | 多法官独立判定 | 部分落地（高） | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py) | A/B/C 结构已独立，运行 profile 独立化与策略版本治理待继续深化 |
| 6.6 Fairness Sentinel Agent | 稳定性与公平门禁 | 部分落地（高） | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py), [ai_judge_fairness_benchmark_freeze.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_fairness_benchmark_freeze.sh), [ai_judge_real_env_window_closure.sh](/Users/panyihang/Documents/EchoIsle/scripts/harness/ai_judge_real_env_window_closure.sh) | drift governance v1 与 ingest 已落地；release gate v2 与 real-env pass 待完成 |
| 6.7 Chief Arbiter Agent | 汇总裁决与状态决策 | 部分落地（高） | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py), [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) | 复核/挑战主链已具备，仍需与 registry triple 主链完全绑定 |
| 6.8 Opinion Writer Agent | 生成可读裁决书 | 部分落地（高） | [final_report.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/domain/judge/final_report.py) | 基础裁决书稳定，Ops 高级解释与可运营层输出待增强 |

## 4. 关键结论（当前真实状态）

1. 当前阶段已经进入 `P13`：从“P12 收口”转向“Fairness Hardened 工程化”，主线是 baseline 冻结 + shadow 评测主链。
2. 截至 2026-04-17：
   - 已完成 `public verification endpoint v1`、`opinion-pack timeline v2`、`evidence-ledger reliability guard v2` 的基线冻结与回归验证。
   - 已完成 `fairness-shadow-eval-ledger v1`：新增 `fairness_shadow_runs` 事实源与 `/internal/judge/fairness/shadow-runs` 写读接口。
   - 已完成 `fairness cases` 读模型增强：`shadowSummary`、`has_shadow_breach` 过滤与聚合计数已接通。
3. 当前主要阻塞项仍是 `real-env pass window`（环境窗口型阻塞）；非环境模块已继续向运营化读模型推进。

## 5. 下一步优先级（与 P13 一致）

1. 推进 `ai-judge-p13-fairness-dashboard-export-v1`，补齐 `overview/trends/top_risk_cases/gate_distribution` 聚合导出。
2. 推进 `ai-judge-p13-policy-release-gate-shadow-link`，把 shadow 漂移结论接入 policy 发布门禁。
3. 维持 `ai-judge-p13-real-env-pass-window-execute-on-env` 的窗口冲刺准备，窗口到来后一次性推进 `pass`。

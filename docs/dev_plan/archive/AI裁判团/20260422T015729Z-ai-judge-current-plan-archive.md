# 当前开发计划

关联 slot：`default`  
更新时间：2026-04-21  
当前主线：`AI_judge_service P31（Judge 主链工程化收敛 + 架构一致性补齐 + real-env pass 准备）`  
当前状态：执行中（已完成 `ai-judge-next-iteration-planning`、`ai-judge-p31-six-object-contract-hardening-v1`、`ai-judge-p31-policy-kernel-binding-hardening-v1`、`ai-judge-p31-ops-read-model-pack-v7`、`ai-judge-p31-local-regression-bundle-v1` 与 `ai-judge-p31-enterprise-consistency-refresh-v1`；`ai-judge-p31-app-factory-hotspot-split-v2` 进行中，已完成 fairness、ops/read-model/pack 与 trust 读面/挑战热点路由下沉前二十七批）

---

## 1. 计划定位

1. 本计划承接阶段归档：`/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260421T070425Z-ai-judge-stage-closure-execute.md`。
2. 当前计划已先行归档：`/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260421T071648Z-ai-judge-current-plan-archive.md`。
3. P30 已完成主链收口：Judge workflow role nodes 完整性、registry/panel/review-alert 路由下沉、ops pack v6、本地回归包、文档一致性门禁。
4. P31 目标是把“已可用主链”推进到“更可维护、更可审计、可进入 real-env pass 窗口”的工程态。
5. 当前前提不变：仅本地环境可用；真实环境结论统一标记 `on-env`，本地结果只可标记 `local_reference_ready`。

---

## 2. 当前代码状态快照（P31 起点）

截至 2026-04-21，`ai_judge_service` 当前状态：

1. Judge 主链骨架已就位并稳定可测：
   - `judge_app_domain`、`judge_dispatch_runtime`、`judge_trace_replay_routes`、`judge_trace_summary`、`judge_workflow_roles` 均已落地。
   - `fairness gate` 主语义已统一为 `pass_through/blocked_to_draw`。
2. 路由结构拆分已推进到中后段：
   - `registry_routes.py`、`panel_runtime_routes.py`、`review_alert_routes.py` 已接管主要装配逻辑。
3. 当前主要缺口：
   - `app_factory.py` 仍有部分高耦合路由与组装热点，后续维护成本偏高。
   - 六对象主链（`case_dossier/claim_graph/evidence_bundle/verdict_ledger/fairness_report/opinion_pack`）虽已贯通，但对象级合同一致性还可继续硬化。
   - `policy/prompt/tool` 与 Judge Kernel/公平门禁的绑定策略仍需强化“可审计可追溯”闭环。
   - `real-env pass window` 仍是唯一阻塞项（`env_blocked`）。

---

## 3. P31 总目标

1. 继续降低 `app_factory` 复杂度，把剩余热点路由进一步下沉到 `app/applications`。
2. 对齐企业方案第 7/9/11/12 章：强化六对象合同、fairness/policy 运行时一致性与审计可追踪性。
3. 对齐架构方案第 5/6/13 章：保持 8 Agent 角色边界与 `NPC/Room QA advisory-only` 边界，不污染官方裁决链。
4. 完成本地可执行收口（回归包 + 文档一致性），并为后续 real-env 窗口提供可直接执行的入口。

---

## 4. P31 模块执行矩阵

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 本轮目标 | DoD（完成定义） | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| `ai-judge-next-iteration-planning` | P0 | 已完成（2026-04-21） | 阶段收口后生成 P31 完整计划 | 当前计划切换到 P31，模块矩阵/顺序/门禁口径完整 | `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p31-app-factory-hotspot-split-v2` | P0 | 执行中 | 继续下沉 `app_factory` 热点路由 | 已完成二十七批（2026-04-21）：前三批 fairness 路由下沉 + 第四批 `ops/read-model/pack` 路由编排下沉到 `app/applications/ops_read_model_pack.py` + 第五批 trust 读面 `report_context/phaseA_bundle` 组装下沉到 `app/applications/trust_read_routes.py` + 第六批 trust challenge `request/decision` 业务编排下沉到 `app/applications/trust_challenge_runtime_routes.py` + 第七批 trust 读面通用合同校验与 payload 组装下沉（`commitment/verdict/challenges/kernel/audit/public`）到 `app/applications/trust_read_routes.py` + 第八批 trust challenge `ops-queue` 扫描/过滤/排序编排下沉到 `app/applications/trust_challenge_ops_queue_routes.py` + 第九批 attestation/replay 读路由编排下沉到 `app/applications/trust_read_routes.py` 与 `app/applications/judge_trace_replay_routes.py` + 第十批 trace 读路由编排下沉到 `app/applications/judge_trace_replay_routes.py` + 第十一批 replay 路由前置分支（`dispatch_type 归一化/receipt 选择/traceId 解析`）下沉到 `app/applications/judge_trace_replay_routes.py` + 第十二批 replay 落库与响应组装尾段下沉到 `app/applications/judge_trace_replay_routes.py` + 第十三批 replay 路由 `final/phase` report 重算编排下沉到 `app/applications/judge_trace_replay_routes.py` + 第十四批 replay 路由依赖装配热点下沉，`app_factory` replay 路由收敛到 helper 调度 + 第十五批 replay 路由改为统一 dependency pack（`ReplayReportDependencyPack/ReplayFinalizeDependencyPack`）驱动 + 第十六批 replay 错误映射统一收敛到 guard helper，减少重复 try/except 样板 + 第十七批 replay POST 路由级 orchestrator 下沉到 `app/applications/judge_trace_replay_routes.py`（新增 `ReplayContextDependencyPack/build_replay_post_route_payload`），`app_factory` replay 路由收敛为依赖装配与 guard 调用 + 第十八批 trust 读面 `TrustReadRouteError` 映射统一收敛到 `_run_trust_read_guard/_run_trust_read_guard_sync`，`app_factory` trust 路由清理重复 try/except 样板 + 第十九批 trust challenge `TrustChallengeRouteError/TrustChallengeOpsQueueRouteError` 映射统一收敛到 `_run_trust_challenge_guard`，`app_factory` challenge 路由清理重复 try/except 样板 + 第二十批 fairness 路由 `FairnessRouteError` 映射统一收敛到 `_run_fairness_route_guard`，`app_factory` fairness 路由清理重复 try/except 样板 + 第二十一批 review/registry 路由错误映射收敛（新增 `_run_review_route_guard/_run_registry_route_guard`），替换 `review decision + alert ack/resolve + registry publish/activate` 的重复 try/except 样板 + 第二十二批请求体 JSON 解析收敛（新增 `_read_json_object_or_raise_422`），统一 `registry publish / case create / phase|final dispatch / fairness benchmark|shadow upsert` 的 `invalid_json + invalid_payload` 语义 + 第二十三批 alert 路由装配收敛（新增 `_transition_judge_alert_status`），统一 `alerts/{alert_id}/ack|resolve` 重复装配逻辑 + 第二十四批 registry `ValueError` 映射收敛（新增 `_raise_registry_value_error`），统一 `publish/activate/rollback/audits/releases` 路由中的 409/422 分支判定与默认错误语义 + 第二十五批通用 `ValueError/LookupError` 映射收敛（新增 `_raise_http_422_from_value_error/_raise_http_404_from_lookup_error`），替换 `registry publish parse`、`review cases`、`review decision`、`alert ops view`、`alert outbox delivery` 等路由重复样板 + 第二十六批合同违例 500 映射收敛（新增 `_raise_http_500_contract_violation`），统一 `case_overview/courtroom_read_model/courtroom_drilldown_bundle/evidence_claim_ops_queue/ops_read_model_pack/panel_runtime_profile` 的 contract violation 返回结构 + 第二十七批 policy-registry 已知错误映射收敛（新增 `_raise_http_422_for_known_value_error/_raise_policy_registry_not_found_lookup_error`），统一 `dependency health` 与 `gate simulation` 路由的 `invalid_* / policy_registry_not_found` 分支样板，未知错误继续原样抛出 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py tests/test_ops_read_model_pack.py tests/test_fairness_dashboard_contract.py tests/test_trust_read_routes.py tests/test_trust_challenge_runtime_routes.py tests/test_trust_challenge_ops_queue_routes.py tests/test_judge_trace_replay_routes.py -k \"ops_read_model_pack or (fairness and (dashboard or calibration or advisor)) or trust or replay or trace\"` + `cd ai_judge_service && ../scripts/py -m ruff check app/app_factory.py app/applications/fairness_runtime_routes.py app/applications/ops_read_model_pack.py app/applications/trust_read_routes.py app/applications/trust_challenge_runtime_routes.py app/applications/trust_challenge_ops_queue_routes.py app/applications/judge_trace_replay_routes.py tests/test_trust_read_routes.py tests/test_trust_challenge_runtime_routes.py tests/test_trust_challenge_ops_queue_routes.py tests/test_judge_trace_replay_routes.py` |
| `ai-judge-p31-six-object-contract-hardening-v1` | P0 | 已完成（2026-04-21） | 强化六对象主链合同一致性 | 已完成：`judge_app_domain` 增加六对象必需键/类型与 `fairnessGate↔verdict` 一致性约束（含 final reviewRequired→winner=draw）；新增失败语义用例并修复相关 trace/workflow fixture | `cd ai_judge_service && ../scripts/py -m pytest -q tests -k "claim_graph or evidence or verdict or fairness or opinion"` |
| `ai-judge-p31-policy-kernel-binding-hardening-v1` | P1 | 已完成（2026-04-21） | 强化 registry/policy 与 Judge Kernel 绑定闭环 | 已完成：新增 `policyKernel(version/kernelHash/kernelVector)` 稳定快照，贯通 `dependency_health + governance_overview`；`dependencyOverview` 增加 `latestGateDecision/latestGateSource/overrideApplied/overrideActor` 等可审计字段 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_policy_registry_runtime.py tests/test_app_factory.py -k "policy_registry_dependency_health_route or registry_governance_overview_route"` + `cd ai_judge_service && ../scripts/py -m ruff check app/app_factory.py app/applications/policy_registry.py app/applications/registry_product_runtime.py app/applications/registry_routes.py tests/test_policy_registry_runtime.py tests/test_app_factory.py` |
| `ai-judge-p31-ops-read-model-pack-v7` | P1 | 已完成（2026-04-21） | 升级 ops 聚合可运维性 | 已完成：`ops/read-model/pack` 新增 `caseChainCoverage/fairnessGateOverview/policyKernelBinding` 三个聚合段，并为 courtroom item 增加 policy-kernel/gate/override 可观测字段；contract 与路由测试已同步 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_ops_read_model_pack.py tests/test_app_factory.py -k "ops_read_model_pack"` + `cd ai_judge_service && ../scripts/py -m ruff check app/applications/ops_read_model_pack.py app/app_factory.py tests/test_ops_read_model_pack.py tests/test_app_factory.py` |
| `ai-judge-p31-local-regression-bundle-v1` | P2 | 已完成（2026-04-21） | 固化 P31 本地回归包 | 已完成：`ruff + pytest -q + runtime_ops_pack(local_reference_ready)`，并产出 `20260421T215207Z-ai-judge-runtime-ops-pack.summary.{json,md}` | `cd ai_judge_service && ../scripts/py -m ruff check app tests` + `cd ai_judge_service && ../scripts/py -m pytest -q` + `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference` |
| `ai-judge-p31-enterprise-consistency-refresh-v1` | P2 | 已完成（2026-04-21） | 企业方案/架构方案/计划口径一致性刷新 | 已完成：回写章节完成度映射与当前计划，并通过 `harness_docs_lint + plan_consistency_gate` | `bash scripts/quality/harness_docs_lint.sh` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p31-real-env-pass-window-execute-on-env` | P0（环境阻塞） | 阻塞（待真实环境窗口） | 真实环境 pass 冲刺 | `AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=pass` 且 `REAL_PASS_READY=true` | `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p31-stage-closure-execute` | P2 | 待执行 | 阶段收口执行 | 归档活动计划，`completed/todo` 同步，计划重置到下一轮入口 | `bash scripts/harness/ai_judge_stage_closure_execute.sh --root /Users/panyihang/Documents/EchoIsle` |

### 下一开发模块建议

1. `ai-judge-p31-app-factory-hotspot-split-v2`
2. `ai-judge-p31-real-env-pass-window-execute-on-env`
3. `ai-judge-p31-stage-closure-execute`

---

## 5. 延后事项（不阻塞 P31）

1. `real-env pass` 相关能力（严格 `on-env`）。
2. `NPC Coach / Room QA` 正式业务策略与主链接入（等待你冻结 PRD 后推进）。
3. 协议化扩展（链上锚定 / ZK / ZKML）继续后置，不进入当前官方裁决主链。

---

## 6. 执行顺序与依赖

1. 先做 `app-factory-hotspot-split-v2`，先降低结构复杂度并稳定装配边界。
2. 再做 `six-object-contract-hardening-v1`，把企业方案数据主链合同进一步硬化。
3. 然后做 `policy-kernel-binding-hardening-v1` 与 `ops-read-model-pack-v7`，补齐运行态治理与运维可观测性。
4. 最后执行 `local-regression-bundle-v1` 与 `enterprise-consistency-refresh-v1`。
5. 真实环境窗口可用时推进 `on-env pass`，否则执行阶段收口。

---

## 7. 本阶段明确不做

1. 不推进 `NPC Coach / Room QA` 正式业务开发（仅保持架构边界与入口占位，不入裁决链）。
2. 不为未上线能力保留长期兼容层（alias/双写/灰度并行）。
3. 不把 `local_reference_*` 或 `env_blocked` 结论表达为 `pass`。

---

## 8. 测试与验收基线

1. `bash skills/python-venv-guard/scripts/assert_venv.sh --project /Users/panyihang/Documents/EchoIsle/ai_judge_service --venv /Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv`
2. `cd ai_judge_service && ../scripts/py -m ruff check app tests`
3. `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py tests/test_judge_trace_summary.py tests/test_judge_workflow_roles.py`
4. `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_policy_registry_runtime.py tests/test_registry_runtime.py tests/test_ops_read_model_pack.py`
5. `cd ai_judge_service && ../scripts/py -m pytest -q`
6. `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`
7. `bash scripts/quality/harness_docs_lint.sh`
8. `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle`

---

## 9. 风险与对策

1. 风险：继续拆分 `app_factory` 可能引入行为回归。  
   对策：保持路由输入输出与错误码语义不变，先 helper 化后替换，回归 `test_app_factory.py`。
2. 风险：六对象合同硬化过严导致历史样本回放失败。  
   对策：优先约束新生成/新回放路径，历史样本通过 replay 重算收敛。
3. 风险：policy/kernel 绑定强化引发跨层字段漂移。  
   对策：先冻结 contract + fixtures，再同步 read-model 与 docs，不保留长期双轨字段。
4. 风险：无真实环境导致“工程完成”与“可上线”口径混淆。  
   对策：持续分层表达 `local_reference_ready` 与 `pass`，`on-env` 单独收口。

---

## 10. 模块完成同步历史

### 模块完成同步历史

1. 2026-04-21：完成 `ai-judge-stage-closure-execute`，阶段计划归档到 `/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260421T070425Z-ai-judge-stage-closure-execute.md`，并重置当前计划文档。
2. 2026-04-21：按你的要求先归档当前计划到 `/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260421T071648Z-ai-judge-current-plan-archive.md`。
3. 2026-04-21：完成 `ai-judge-next-iteration-planning`，当前计划切换为 `P31`。
4. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第一批，下沉 `fairness/benchmark-runs` 与 `fairness/shadow-runs` 路由组装到 `app/applications/fairness_runtime_routes.py`，并通过 fairness 相关回归与 lint。
5. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第二批，下沉 `fairness/cases/{case_id}` 与 `fairness/cases` 路由组装到 `app/applications/fairness_runtime_routes.py`，并通过 fairness 回归测试与 lint。
6. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第三批，下沉 `fairness/dashboard`、`fairness/calibration-pack` 与 `fairness/policy-calibration-advisor` 路由组装到 `app/applications/fairness_runtime_routes.py`，并通过 fairness 回归测试与 lint。
7. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第四批，下沉 `ops/read-model/pack` 路由主编排到 `app/applications/ops_read_model_pack.py`（新增 route builder），并通过 ops/fairness 回归测试与 lint。
8. 2026-04-21：完成 `ai-judge-p31-six-object-contract-hardening-v1`，在 `judge_app_domain` 增加六对象合同硬约束与跨对象一致性校验，并补齐 `test_judge_app_domain` 失败语义测试，修复 `test_judge_workflow_roles/test_judge_trace_summary` 的最小合法样本后通过回归。
9. 2026-04-21：完成 `ai-judge-p31-policy-kernel-binding-hardening-v1`，在 policy dependency health 增加 `policyKernel(version/kernelHash/kernelVector)`，并在 dependency overview 增加 `latestGateDecision/latestGateSource/overrideApplied/overrideActor/overrideReason` 审计字段；通过 `test_policy_registry_runtime` 与 `test_app_factory` 针对性回归及 ruff 校验。
10. 2026-04-21：完成 `ai-judge-p31-ops-read-model-pack-v7`，在 `ops/read-model/pack` 新增 `caseChainCoverage/fairnessGateOverview/policyKernelBinding` 聚合段，并扩展 courtroom item 的 `policyVersion/policyKernelVersion/policyKernelHash/policyGateDecision/policyGateSource/policyOverrideApplied` 字段；补齐 `test_ops_read_model_pack` 与 `test_app_factory` 集成断言并通过回归。
11. 2026-04-21：完成 `ai-judge-p31-local-regression-bundle-v1`，通过 `ruff check app tests` 与 `pytest -q` 全量回归，并执行 `ai_judge_runtime_ops_pack.sh --allow-local-reference` 产出 `20260421T215207Z-ai-judge-runtime-ops-pack.summary.{json,md}`。
12. 2026-04-21：完成 `ai-judge-p31-enterprise-consistency-refresh-v1`，回写 `/docs/dev_plan/AI_Judge_Service-企业级Agent方案-章节完成度映射-2026-04-13.md` 与当前计划口径，执行 `harness_docs_lint`（PASS，2 条既有 warning）和 `ai_judge_plan_consistency_gate`（PASS，工件 `20260421T215612Z`）。
13. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第五批，将 trust 读面中的 `resolve_report_context` 与 `phaseA_bundle` 编排下沉到 `app/applications/trust_read_routes.py`（新增 `TrustReadRouteError/build_trust_phasea_bundle_for_case/resolve_trust_report_context_for_case`），`app_factory` 收敛为 HTTP 映射；通过 `test_trust_read_routes.py` 与 `test_app_factory.py -k trust` 回归及 ruff 校验。
14. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第六批，将 trust challenge mutation 路由中的 `request/decision` 主编排下沉到 `app/applications/trust_challenge_runtime_routes.py`（新增 `TrustChallengeRouteError/build_trust_challenge_request_payload/build_trust_challenge_decision_payload`），`app_factory` 收敛为 HTTP 映射与错误转换；新增 `test_trust_challenge_runtime_routes.py` 并通过 `test_app_factory.py -k trust_challenge` 与 `test_app_factory.py -k trust` 回归及 ruff 校验。
15. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第七批，将 trust 读面 `commitment/verdict/challenges/kernel/audit/public` 的通用 payload 组装与合同校验下沉到 `app/applications/trust_read_routes.py`（新增 `build_validated_trust_item_route_payload/build_trust_audit_anchor_route_payload/build_trust_public_verify_bundle_payload`）；`app_factory` 路由收敛为参数透传与 `TrustReadRouteError -> HTTPException` 映射；通过 `test_trust_read_routes.py` 与 `test_app_factory.py -k trust` 回归及 ruff 校验。
16. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第八批，将 trust challenge `ops-queue` 的扫描/过滤/排序主编排下沉到 `app/applications/trust_challenge_ops_queue_routes.py`（新增 `TrustChallengeOpsQueueRouteError/build_trust_challenge_ops_queue_route_payload`），`app_factory` 路由收敛为参数透传与错误转换；新增 `test_trust_challenge_ops_queue_routes.py` 并通过 `test_app_factory.py -k trust_challenge_ops_queue` 与 `test_app_factory.py -k trust` 回归及 ruff 校验。
17. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第九批，将 `attestation/verify + replay/report(s)` 路由编排下沉到 `app/applications/trust_read_routes.py` 与 `app/applications/judge_trace_replay_routes.py`（新增 `build_trust_attestation_verify_payload/ReplayReadRouteError/build_replay_report_route_payload/build_replay_reports_route_payload`），`app_factory` 路由收敛为参数透传与 `TrustReadRouteError/ReplayReadRouteError -> HTTPException` 映射；补齐 `test_trust_read_routes.py` 与 `test_judge_trace_replay_routes.py`，并通过 `test_app_factory.py -k \"attestation or replay_report\"` 回归及 ruff 校验。
18. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第十批，将 `/cases/{case_id}/trace` 读路由主编排下沉到 `app/applications/judge_trace_replay_routes.py`（新增 `build_trace_route_read_payload`），`app_factory` 路由收敛为参数透传与 `ReplayReadRouteError -> HTTPException` 映射；补齐 `test_judge_trace_replay_routes.py`，并通过 `test_app_factory.py -k trace` 与 `test_judge_trace_replay_routes.py` 回归及 ruff 校验。
19. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第十一批，将 `POST /cases/{case_id}/replay` 前置分支（`dispatch_type` 归一化、auto/final/phase receipt 选择、`traceId` 解析与错误语义）下沉到 `app/applications/judge_trace_replay_routes.py`（新增 `resolve_replay_dispatch_context_for_case`），`app_factory` 回放路由收敛为参数透传与 `ReplayReadRouteError -> HTTPException` 映射；补齐 `test_judge_trace_replay_routes.py` 并通过 `test_app_factory.py -k \"replay or trace\"` 回归及 ruff 校验。
20. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第十二批，将 replay 路由尾段的“claim ledger 写入、winner/needsDrawVote 归一化、trace/replay 标记、replay history 记录、响应组装”下沉到 `app/applications/judge_trace_replay_routes.py`（新增 `finalize_replay_route_payload`），`app_factory` 回放路由进一步收敛；补齐 `test_judge_trace_replay_routes.py` 并通过 `test_app_factory.py -k \"replay or trace\"` 回归及 ruff 校验。
21. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第十三批，将 replay 路由 `final/phase` report 重算编排下沉到 `app/applications/judge_trace_replay_routes.py`（新增 `build_replay_report_payload_for_dispatch`），并在 `app_factory` 用统一 builder 替换原分支细节；补齐 `test_judge_trace_replay_routes.py`（final 成功与 phase 参数错误分支）并通过 `test_app_factory.py -k \"replay or trace\"` 回归及 ruff 校验。
22. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第十四批，将 replay 路由的依赖装配热点（多层 lambda 透传）收敛为 `app_factory` 内部 helper（`_resolve_replay_context_for_case/_build_replay_report_payload_for_case/_finalize_replay_payload_for_case` 等），保持行为不变前提下显著压缩路由主体复杂度；通过 `test_app_factory.py -k \"replay or trace\"` 与 `test_judge_trace_replay_routes.py` 回归及 ruff 校验。
23. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第十五批，将 replay 主链改为 dependency pack 传递（`ReplayReportDependencyPack/ReplayFinalizeDependencyPack`），替代长参数列表，统一 applications 编排接口；同步更新 `app_factory` 绑定与 `test_judge_trace_replay_routes.py`，并通过 `test_app_factory.py -k \"replay or trace\"` 回归及 ruff 校验。
24. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第十六批，将 replay 相关 `ReplayReadRouteError -> HTTPException` 映射统一收敛为 `_run_replay_read_guard`，并替换 `_resolve_replay_context_for_case`、`_build_replay_report_payload_for_case`、`/cases/{case_id}/trace` 与 `/cases/{case_id}/replay/report` 中重复 try/except；通过 `test_app_factory.py -k \"replay or trace\"` 与 `test_judge_trace_replay_routes.py` 回归及 ruff 校验。
25. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第十七批，在 `app/applications/judge_trace_replay_routes.py` 新增 replay 路由级 orchestrator（`ReplayContextDependencyPack/build_replay_post_route_payload`），串联 `context -> report recompute -> finalize`；`app_factory` 的 `POST /internal/judge/cases/{case_id}/replay` 收敛为依赖 pack 装配 + `_run_replay_read_guard` 单点调用；补齐 `test_judge_trace_replay_routes.py` orchestrator happy/error 用例，并通过 `test_app_factory.py -k \"replay or trace\"` 回归及 ruff 校验。
26. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第十八批，将 trust 读面中的 `TrustReadRouteError -> HTTPException` 映射统一收敛为 `_run_trust_read_guard/_run_trust_read_guard_sync`，并替换 `_resolve_report_context_for_case`、`_build_trust_phasea_bundle`、`/trust/*` 与 `/attestation/verify` 路由里的重复 try/except 样板；通过 `test_app_factory.py -k \"trust or replay or trace\"`、`test_judge_trace_replay_routes.py` 回归及 ruff 校验。
27. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第十九批，将 trust challenge 相关错误映射统一收敛到 `_run_trust_challenge_guard`（覆盖 `ops-queue/request/decision` 三条路由），清理 `TrustChallengeRouteError/TrustChallengeOpsQueueRouteError -> HTTPException` 的重复 try/except 样板；通过 `test_app_factory.py -k \"trust_challenge or trust or replay or trace\"`、`test_judge_trace_replay_routes.py` 回归及 ruff 校验。
28. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第二十批，将 fairness 路由中的 `FairnessRouteError -> HTTPException` 映射统一收敛到 `_run_fairness_route_guard`，并替换 `benchmark-runs/shadow-runs/cases/dashboard` 路由里的重复 try/except 样板；通过 `test_app_factory.py -k \"fairness or trust or replay or trace\"`、`test_judge_trace_replay_routes.py` 回归及 ruff 校验。
29. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第二十一批，将 `review/registry` 路由中的 `ReviewRouteError/RegistryRouteError -> HTTPException` 映射统一收敛到 `_run_review_route_guard/_run_registry_route_guard`，并替换 `review/cases/{case_id}/decision`、`alerts/{alert_id}/ack|resolve`、`registries/{registry_type}/publish|activate` 的重复 try/except 样板；通过 `test_app_factory.py -k \"review or registry or alert\"` 回归及 ruff 校验。
30. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第二十二批，将请求体解析样板统一收敛到 `_read_json_object_or_raise_422`，并替换 `registries/{registry_type}/publish`、`cases create`、`v3/phase|final dispatch`、`fairness benchmark|shadow upsert` 的重复 `request.json + dict 检查` 逻辑，保持 `invalid_json/invalid_payload` 语义不变；通过 `test_app_factory.py -k \"registry or fairness or case_create or phase_dispatch or final_dispatch\"` 回归及 ruff 校验。
31. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第二十三批，将 `alerts/{alert_id}/ack|resolve` 的重复 transition 装配收敛到 `_transition_judge_alert_status`，统一参数透传与 review guard 调用，保持状态迁移语义不变；通过 `test_app_factory.py -k \"review or alert\"` 回归及 ruff 校验。
32. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第二十四批，将 registry 路由里的 `ValueError` 分类映射收敛到 `_raise_registry_value_error`，统一 `publish/activate/rollback/audits/releases` 的 `409/422` 分支与默认错误码语义，减少重复分支样板；通过 `test_app_factory.py -k \"registry\"` 回归及 ruff 校验。
33. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第二十五批，新增 `_raise_http_422_from_value_error/_raise_http_404_from_lookup_error`，收敛 `registry publish parse`、`review cases`、`review decision`、`alert ops view`、`alert outbox delivery` 等路由中重复的 `ValueError/LookupError -> HTTPException` 样板映射，保持错误语义不变；通过 `test_app_factory.py -k \"registry or review or alert\"` 回归及 ruff 校验。
34. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第二十六批，新增 `_raise_http_500_contract_violation`，收敛 `case_overview/courtroom_read_model/courtroom_drilldown_bundle/evidence_claim_ops_queue/ops_read_model_pack/panel_runtime_profile` 等路由的合同违例 `500` 响应组装样板，保持 `code/message` 语义不变；通过 `test_app_factory.py -k \"ops_read_model_pack or courtroom or evidence_claim_ops_queue or panel_runtime\"` 回归及 ruff 校验。
35. 2026-04-21：推进 `ai-judge-p31-app-factory-hotspot-split-v2` 第二十七批，新增 `_raise_http_422_for_known_value_error/_raise_policy_registry_not_found_lookup_error`，收敛 policy registry 路由中 `invalid_trend_status/invalid_policy_version/policy_registry_not_found` 的重复分支翻译样板（未知错误保持原样抛出）；通过 `test_app_factory.py -k \"policy_registry_dependency_health_route or policy_gate_simulation_route\"` 回归及 ruff 校验。

---

## 11. 本轮启动检查清单

1. 开发前运行 `pre-module-prd-goal-guard`（按模块执行）。
2. 涉及 API/DTO/错误码变更时，同轮同步调用方、测试与文档。
3. 与真实环境有关结论必须标注 `on-env`，本地阶段不得宣称 `pass`。
4. 每完成一个模块都回写当前计划矩阵与同步历史。

---

## 12. 架构方案第13章一致性校验（计划生成前置）

1. **角色一致性**：8 Agent 职责必须完整映射，不能被错误合并或绕过。  
2. **数据一致性**：`case_dossier/claim_graph/evidence_bundle/verdict_ledger/fairness_report/opinion_pack` 保持唯一主链语义。  
3. **门禁一致性**：`Fairness Sentinel` 仍在终判前，override/阻断必须可审计。  
4. **边界一致性**：`NPC/Room QA` 继续保持 `advisory_only`，不写官方裁决链。  
5. **跨层一致性**：契约变更同轮同步调用方、测试与文档，不保留长期双轨 alias。  
6. **收口一致性**：real-env 项继续区分 `local_reference_ready` 与 `pass`，不混淆口径。

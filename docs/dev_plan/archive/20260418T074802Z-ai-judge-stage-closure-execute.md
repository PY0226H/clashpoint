# 当前开发计划

关联 slot：`default`  
更新时间：2026-04-18  
当前主线：`AI_judge_service P16（Courtroom Read Model + Review/Priority + Registry Simulation + Ops v3）`  
当前状态：执行中（`ai-judge-next-iteration-planning`、`ai-judge-p16-courtroom-read-model-v1`、`ai-judge-p16-review-queue-risk-prioritization-v1`、`ai-judge-p16-policy-gate-simulation-v1`、`ai-judge-p16-ops-pack-and-export-v3`、`ai-judge-p16-enterprise-architecture-consistency-refresh` 已完成；P16-M6 待执行；real-env 仍为窗口阻塞）

---

## 1. 计划定位

1. 本计划承接 `P15` 阶段收口（`M1~M6` 已归档），进入下一轮可本地推进的企业级主线开发。
2. 继续执行“未上线产品硬切原则”：不保留长期兼容层、双写链路、灰度旧路径。
3. 本轮聚焦 `官方裁决链可运营化` 与 `治理仿真能力`，不推进未冻结 PRD 的 `NPC Coach / Room QA` 业务实现。
4. 计划生成输入保持三元一致：
   - 企业方案：`AI_Judge_Service-企业级Agent服务设计方案-2026-04-13.md`
   - 架构方案：`AI_Judge_Service-架构与技术栈决策方案-2026-04-13.md`
   - 当前代码状态：`P15` 收口归档 + `completed/todo` + 当前主线代码

---

## 2. 当前代码状态快照（P16 起点）

截至 2026-04-18，以下能力已确认落地：

1. 裁判主链稳定：`phase/final dispatch + trace + replay + review + failed callback` 全链可追踪。
2. 六对象主链可用：`case_dossier / claim_graph / evidence_ledger / verdict_ledger / fairness_report / opinion_pack`。
3. 公平治理主链可用：`benchmark-runs + shadow-runs + fairness/cases + fairness/dashboard`。
4. P15 新增已落地：
   - `GET /internal/judge/fairness/policy-calibration-advisor`
   - `GET /internal/judge/panels/runtime/readiness`
   - `GET /internal/judge/registries/policy/domain-families`
   - `GET /internal/judge/ops/read-model/pack` v2（含 calibration/panel/adaptive 汇总）
5. registry 三元治理可用：`publish/activate/rollback/audits/releases` + `fairness gate` + `dependency health` + `domain family`。
6. 当前主要缺口：
   - 剩余 `stage-closure` 收口动作与 `real-env` 窗口验收。
7. P16-M1 已完成：
   - 新增 `GET /internal/judge/cases/{case_id}/courtroom-read-model`，按 case 聚合 `Recorder/Claim/Evidence/Panel/Fairness/Opinion/Governance` 一体化只读视图。
   - 已覆盖路由注册、聚合返回与缺失 case 分支测试。

---

## 3. P16 总目标（下一阶段）

1. 对齐企业方案第 6/7/8/11/13 章：把“法庭式 Agent 分工”转为可查询、可运营、可审计的 read model。
2. 对齐架构方案第 5/5.3/5.4：强化 `Official Verdict Plane` 的治理与观测，不让交互型能力侵入裁决写链。
3. 完成 registry 的“发布前仿真”闭环：先模拟再发布，降低策略变更风险。
4. 将 ops 导出升级到 v3：为第三方看板接入提供稳定 JSON/MD/ENV 证据面。
5. 保持边界：`NPC Coach / Room QA` 仍为 `advisory_only`，不进入官方 verdict 写链。

---

## 4. P16 模块执行矩阵

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 本轮目标 | DoD（完成定义） | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| `ai-judge-next-iteration-planning` | P0 | 已完成（2026-04-18） | 基于企业方案 + 架构方案 + 当前代码状态生成下一轮计划 | 当前计划已重写为 `P16`，矩阵/顺序/门禁口径完整 | `bash scripts/quality/harness_docs_lint.sh` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p16-courtroom-read-model-v1` | P1 | 已完成（2026-04-18） | 建立法庭式一体化 read model（Recorder/Claim/Evidence/Panel/Fairness/Opinion） | 新增 `GET /internal/judge/cases/{case_id}/courtroom-read-model`，支持按 case 聚合主链对象与关键证据/争点摘要；不新增 verdict 写入口 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "courtroom or claim or evidence or fairness"` |
| `ai-judge-p16-review-queue-risk-prioritization-v1` | P1 | 已完成（2026-04-18） | 升级 review 队列风险优先级与 SLA 维度 | `/internal/judge/review/cases` 增加 `riskLevel/slaBucket/sortBy/sortOrder/scanLimit`，返回 `riskProfile`（score/level/tags/ageMinutes/slaBucket）并支持风险排序与过滤 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "review or fairness"` |
| `ai-judge-p16-policy-gate-simulation-v1` | P1 | 已完成（2026-04-18） | 新增 policy 发布前仿真入口 | 新增 `GET /internal/judge/registries/policy/gate-simulation`，聚合 `fairness gate + dependency health + domain judge family`，严格只读无副作用 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "registry and (simulation or fairness)"` |
| `ai-judge-p16-ops-pack-and-export-v3` | P1 | 已完成（2026-04-18） | 升级 ops pack + 导出脚本为 v3 口径 | `ops/read-model/pack` 新增 `courtroomReadModel/reviewQueue/policyGateSimulation`，并把 `adaptiveSummary` 扩展到 review/simulation/courtroom 指标；导出脚本与脚本测试同步升级 | `bash scripts/harness/tests/test_ai_judge_ops_read_model_export.sh` + `bash scripts/harness/tests/test_ai_judge_fairness_calibration_pack_local.sh` + `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "ops or review or registry"` |
| `ai-judge-p16-enterprise-architecture-consistency-refresh` | P1 | 已完成（2026-04-18） | 刷新企业方案章节映射与架构一致性文档 | 章节完成度映射升级到 P16 口径，补齐 M1~M4 能力映射与剩余阻塞边界 | `bash scripts/quality/harness_docs_lint.sh` |
| `ai-judge-p16-stage-closure-execute` | P2 | 待执行 | 执行阶段收口 | 活动计划归档、`completed/todo` 同步、当前计划重置为下一轮模板 | `bash scripts/harness/ai_judge_stage_closure_execute.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p16-real-env-pass-window-execute-on-env` | P0（环境阻塞） | 阻塞（待真实环境窗口） | 真实环境窗口 pass 冲刺 | `AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=pass` 且 `REAL_PASS_READY=true` | `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle` |

---

## 5. 延后事项（不阻塞本阶段）

1. 真实环境样本驱动的阈值冻结、容量规划、成本路由优化（`on-env`）。
2. `NPC Coach / Room QA` 正式业务实现（等待你冻结模块 PRD）。
3. 链上协议化扩展（ZK/ZKML/链上锚定）继续保持接口预留、实现后置。
4. 基础设施替换类评估（如 Temporal/向量后端重选）继续等待真实运维样本。

### 下一开发模块建议

1. `ai-judge-p16-stage-closure-execute`

---

## 6. 执行顺序与依赖

1. 先做 `courtroom-read-model-v1`，把法庭式主链对象收敛到可运营读面。
2. 再做 `review-queue-risk-prioritization-v1`，把复核分发从“列表”升级为“优先级队列”。
3. 然后做 `policy-gate-simulation-v1`，形成“先仿真后发布”的治理闭环。
4. 基于前三项升级 `ops-pack-and-export-v3`，统一导出运营证据面。
5. 最后刷新章节映射并执行 `stage-closure-execute`。
6. 真实环境窗口就绪后，再单独推进 `real-env-pass-window`。

---

## 7. 本阶段明确不做

1. 不把 `NPC Coach / Room QA` 接入官方裁决写链。
2. 不为未上线能力引入长期兼容双轨（alias/双写/灰度并行）。
3. 不提前拆 Judge/NPC/QA 为独立微服务。
4. 不把本地结果描述为 `real-env pass`。
5. 不在未冻结产品需求前推进 NPC/Room QA 业务策略细节。

---

## 8. 测试与验收基线

1. 全量回归：`cd ai_judge_service && ../scripts/py -m pytest -q`
2. 主链回归：`cd ai_judge_service && ../scripts/py -m pytest -q tests/test_judge_mainline.py tests/test_phase_final_contract_models.py tests/test_app_factory.py tests/test_evidence_ledger.py`
3. fairness + registry + adaptive：`cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "fairness or registry or panel or review"`
4. 质量门禁：
   - `cd ai_judge_service && ../scripts/py -m ruff check app tests`
   - `bash scripts/quality/harness_docs_lint.sh`
   - `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle`
5. 本地收口基线（非 real-env pass）：
   - `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`
   - `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`

---

## 9. 风险与对策

1. 风险：read model 变重，影响查询性能。  
   对策：先做聚合最小闭环，控制字段规模；若出现性能压力再引入分页/索引专项。
2. 风险：simulation 被误用为自动发布。  
   对策：接口强制 `advisory-only`，不触发 publish/activate 副作用。
3. 风险：review priority 改造导致跨层契约漂移。  
   对策：同轮同步 API/DTO/测试/文档，不保留长期 alias。
4. 风险：domain/family 规则过严导致策略发布受阻。  
   对策：保留 allowlist 可观测输出与明确信息错误码，先治理再扩域。
5. 风险：计划与实现节奏再次断层。  
   对策：每个模块完成后即时回写当前计划与章节映射。

---

## 10. 模块完成同步历史

### 模块完成同步历史

1. 2026-04-18：完成 `ai-judge-next-iteration-planning`，基于企业方案+架构方案+当前代码状态生成 `P16` 完整计划。
2. 2026-04-18：完成 `ai-judge-p16-courtroom-read-model-v1`，新增 `GET /internal/judge/cases/{case_id}/courtroom-read-model` 聚合读模型，并通过 `tests/test_app_factory.py -k "create_app_should_expose_v3_routes_only or courtroom_read_model_route"` 与 `-k "courtroom or claim or evidence or fairness"` 回归。
3. 2026-04-18：完成 `ai-judge-p16-review-queue-risk-prioritization-v1`，升级 `/internal/judge/review/cases` 风险优先级与 SLA 过滤排序，新增 `riskProfile`；通过 `tests/test_app_factory.py -k "review_routes_should_list_detail_and_decide_review_job or review_cases_route_should_support_risk_filter_and_sorting"`、`-k "review or fairness"` 与 `ruff check` 回归。
4. 2026-04-18：完成 `ai-judge-p16-policy-gate-simulation-v1`，新增 `GET /internal/judge/registries/policy/gate-simulation` 并补齐“只读无副作用”回归；通过 `tests/test_app_factory.py -k "create_app_should_expose_v3_routes_only or policy_gate_simulation_route"`、`-k "registry and (simulation or fairness)"` 与 `ruff check` 回归。
5. 2026-04-18：完成 `ai-judge-p16-ops-pack-and-export-v3`，升级 `ops/read-model/pack` 为 v3 输出并同步导出脚本字段；通过 `tests/test_app_factory.py -k "create_app_should_expose_v3_routes_only or policy_gate_simulation_route or ops_read_model_pack_route_should_join_fairness_registry_and_trust"`、`tests/test_app_factory.py -k "ops or review or registry"`、`scripts/harness/tests/test_ai_judge_ops_read_model_export.sh`、`scripts/harness/tests/test_ai_judge_fairness_calibration_pack_local.sh` 与 `ruff check` 回归。
6. 2026-04-18：完成 `ai-judge-p16-enterprise-architecture-consistency-refresh`，更新章节完成度映射文档并切换到 P16 状态表达；通过 `harness docs lint` 与计划一致性门禁验证。

---

## 11. 本轮启动检查清单

1. 开发前先跑 `pre-module-prd-goal-guard` 与 `python-venv-guard`。
2. 任何 API/DTO/错误码变更，同轮检查跨层调用方与契约测试。
3. 与 `real-env` 相关结论必须显式标记 `on-env`，禁止把本地结论写成 pass。
4. 新增能力不得改变官方 winner 主语义，除非经审计化治理路径显式授权。
5. 每完成一个模块就回写本计划矩阵与同步历史。

---

## 12. 架构方案第13章一致性校验（计划生成前置）

1. **角色一致性**：继续沿用法庭式 8 Agent 职责，不新增绕过 Sentinel/Arbiter 的捷径路径。
2. **数据一致性**：六对象主链仍是唯一裁决事实源，不引入平行 verdict 写链。
3. **门禁一致性**：fairness/review/registry gate 不弱化；新增 simulation 必须是只读无副作用。
4. **边界一致性**：`NPC/Room QA` 继续 `advisory_only`，不写官方裁决链。
5. **跨层一致性**：契约变更同轮同步调用方和测试，不保留长期双轨 alias。
6. **收口一致性**：真实环境结论与本地参考结论继续分层表达，未获窗口前不宣称 `pass`。

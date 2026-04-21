# 当前开发计划

关联 slot：`default`  
更新时间：2026-04-20  
当前主线：`AI_judge_service P30（Judge 主链 8 Agent 可观察性深化 + app_factory 路由结构继续拆分）`  
当前状态：执行中（已完成 `ai-judge-next-iteration-planning` / `ai-judge-p30-judge-workflow-role-node-completeness-v1` / `ai-judge-p30-ops-read-model-pack-v6` / `ai-judge-p30-panel-readiness-route-split-v1` / `ai-judge-p30-registry-route-structure-split-v1` / `ai-judge-p30-review-alert-route-split-v1` / `ai-judge-p30-local-regression-bundle-v1` / `ai-judge-p30-enterprise-consistency-refresh-v1`；待执行 `stage-closure`）

---

## 1. 计划定位

1. 本计划承接阶段归档：`/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260420T064142Z-ai-judge-stage-closure-execute.md`。
2. P29 已完成主链收口：judge command/runtime 下沉、trace/replay 路由拆分、fairness 读面硬切、judge workflow 合同断言、本地回归包与企业方案一致性刷新。
3. P30 目标从“主链可用”推进到“8 Agent 角色链路可观察 + app_factory 结构继续降复杂度 + Ops 读面可运营性增强”。
4. 当前前提不变：仅本地环境可用，真实环境窗口不可用；`pass` 继续严格区分 `on-env`。
5. 继续执行预发布硬切原则：不保留长期兼容层、灰度并行、双写或 alias。

---

## 2. 当前代码状态快照（P30 起点）

截至 2026-04-20，`ai_judge_service` 当前状态：

1. 已具备 Judge 主链核心骨架：
   - `judge_app_domain`、`judge_workflow_roles`、`judge_trace_summary`、`judge_dispatch_runtime`、`judge_trace_replay_routes` 已落地。
   - `fairness gate` 主语义已统一为 `pass_through/blocked_to_draw`。
2. 企业方案核心对象与路由已可用：
   - `case / claim-ledger / courtroom-read-model / trust / review / fairness / replay / ops pack` 全链已连通。
3. 当前主要缺口：
   - `app_factory.py` 仍承载部分高耦合路由装配逻辑，维护成本偏高（P30 目标范围内的 registry/panel/review-alert 已完成下沉）。
   - 8 Agent 角色节点虽已进入 trace summary，但“角色完整覆盖”与“运营读面聚合”仍可继续硬化。
   - `real-env pass window` 仍是唯一环境阻塞项（`env_blocked`）。

---

## 3. P30 总目标

1. 强化 Judge 8 Agent 主链可观察性：把 `roleNodes` 从“存在”升级到“完整覆盖可校验”。
2. 继续下沉 `app_factory` 热点路由，把 registry/panel/review-alert 路由组装迁移到 `app/applications`。
3. 升级 `ops/read-model/pack` 到 v6，新增 Judge workflow 覆盖度聚合，服务运维诊断。
4. 在本地完成完整回归与文档一致性收口，不误报真实环境 `pass`。

---

## 4. P30 模块执行矩阵

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 本轮目标 | DoD（完成定义） | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| `ai-judge-next-iteration-planning` | P0 | 已完成（2026-04-20） | 阶段收口后生成 P30 完整计划 | 当前计划切换到 P30，矩阵/顺序/门禁口径完整 | `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p30-judge-workflow-role-node-completeness-v1` | P0 | 已完成（2026-04-20） | 强化 8 Agent 角色节点完整覆盖校验 | `judge_trace_summary` 对 phase/final 的 `roleNodes` 增加“角色集合完整 + 顺序稳定”断言；`roleNodes` 缺失/错序直接合同失败 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_judge_trace_summary.py tests/test_judge_workflow_roles.py tests/test_app_factory.py -k "role_nodes or judge_workflow"` + `cd ai_judge_service && ../scripts/py -m ruff check app/applications` |
| `ai-judge-p30-registry-route-structure-split-v1` | P0 | 已完成（2026-04-20） | 下沉 registry 路由组装 | 已完成三批下沉：① prompts/tools list/get + policy dependency-health + audits + releases list/get；② publish/activate/rollback 主链；③ governance/overview + prompt-tool/governance + domain-families + gate-simulation，`app_factory` 保留装配与错误映射 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_policy_registry_runtime.py tests/test_registry_runtime.py tests/test_app_factory.py -k "registries or policy"` + `cd ai_judge_service && ../scripts/py -m ruff check app/app_factory.py app/applications` |
| `ai-judge-p30-panel-readiness-route-split-v1` | P1 | 已完成（2026-04-20） | 下沉 panel runtime/readiness 路由组装 | `panels/runtime/profiles` 与 `panels/runtime/readiness` 路由切换到应用层 helper，`panel_runtime_profile_contract` 继续作为硬约束 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_panel_runtime_profile_contract.py tests/test_app_factory.py -k "panels/runtime"` + `cd ai_judge_service && ../scripts/py -m ruff check app/app_factory.py app/applications` |
| `ai-judge-p30-review-alert-route-split-v1` | P1 | 已完成（2026-04-20） | 下沉 review/alert 路由组装 | `review/cases*`、`cases/{id}/alerts*`、`alerts/ops-view`、`alerts/outbox*` 全量下沉到 `app/applications/review_alert_routes.py`，`app_factory` 保留装配与错误映射 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_review_queue_contract.py tests/test_app_factory.py -k "review or alerts"` + `cd ai_judge_service && ../scripts/py -m ruff check app/app_factory.py app/applications` |
| `ai-judge-p30-ops-read-model-pack-v6` | P1 | 已完成（2026-04-20） | 新增 workflow 覆盖度读面聚合 | `ops/read-model/pack` 新增 `judgeWorkflowCoverage` 聚合（如 full/partial/missing 计数、missing role 热点），并更新 contract/test | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_ops_read_model_pack.py tests/test_app_factory.py -k "ops/read-model/pack or workflow coverage"` + `cd ai_judge_service && ../scripts/py -m ruff check app/applications` |
| `ai-judge-p30-local-regression-bundle-v1` | P2 | 已完成（2026-04-20） | 固化 P30 本地回归包 | 已完成 `ruff + pytest -q + runtime_ops_pack(local_reference_ready)`，并产出新工件摘要 | `cd ai_judge_service && ../scripts/py -m ruff check app tests` + `cd ai_judge_service && ../scripts/py -m pytest -q` + `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference` |
| `ai-judge-p30-enterprise-consistency-refresh-v1` | P2 | 已完成（2026-04-20） | 文档一致性刷新 | 当前计划已回写，`harness_docs_lint` 与 `plan_consistency_gate` 均通过 | `bash scripts/quality/harness_docs_lint.sh` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p30-real-env-pass-window-execute-on-env` | P0（环境阻塞） | 阻塞（待真实环境窗口） | 真实环境 pass 冲刺 | `AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=pass` 且 `REAL_PASS_READY=true` | `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p30-stage-closure-execute` | P2 | 待执行 | 阶段收口执行 | 归档活动计划，`completed/todo` 同步，计划重置到下一轮入口 | `bash scripts/harness/ai_judge_stage_closure_execute.sh --root /Users/panyihang/Documents/EchoIsle` |

### 下一开发模块建议

1. `ai-judge-p30-stage-closure-execute`
2. `ai-judge-p30-real-env-pass-window-execute-on-env`（等待真实环境窗口后触发）
3. `ai-judge-next-iteration-planning`（阶段归档后生成新一轮计划）

---

## 5. 延后事项（不阻塞 P30）

1. `real-env pass` 相关能力（严格 `on-env`）。
2. `NPC Coach / Room QA` 正式业务策略与主链接入（等待你冻结 PRD 后再推进）。
3. 协议化扩展（链上锚定 / ZK / ZKML）继续后置，不进入当前官方裁决主链。

---

## 6. 执行顺序与依赖

1. 先做 `judge-workflow-role-node-completeness-v1`，先把 8 Agent 角色完整性合同硬化。
2. 执行 `local-regression-bundle-v1` 与 `enterprise-consistency-refresh-v1`。
3. 当前进入 `stage-closure-execute` 收口；真实环境窗口就绪后再推进 `on-env pass`。

---

## 7. 本阶段明确不做

1. 不推进 `NPC Coach / Room QA` 正式功能开发。
2. 不为未上线能力保留长期兼容层（alias/双写/灰度并行）。
3. 不把 `local_reference_*` 或 `env_blocked` 结论表述为 `pass`。

---

## 8. 测试与验收基线

1. `bash skills/python-venv-guard/scripts/assert_venv.sh --project /Users/panyihang/Documents/EchoIsle/ai_judge_service --venv /Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv`
2. `cd ai_judge_service && ../scripts/py -m ruff check app tests`
3. `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_judge_trace_summary.py tests/test_judge_workflow_roles.py tests/test_app_factory.py`
4. `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_policy_registry_runtime.py tests/test_registry_runtime.py tests/test_panel_runtime_profile_contract.py tests/test_review_queue_contract.py tests/test_ops_read_model_pack.py`
5. `cd ai_judge_service && ../scripts/py -m pytest -q`
6. `bash scripts/harness/tests/test_ai_judge_ops_read_model_export.sh`
7. `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`
8. `bash scripts/quality/harness_docs_lint.sh`
9. `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle`

---

## 9. 风险与对策

1. 风险：路由拆分时引入行为回归。  
   对策：保持外部 DTO/错误码语义不变，先抽 helper 后替换路由调用，并用 `test_app_factory.py` 做对照回归。
2. 风险：8 Agent 角色完整性断言过严导致历史样本失败。  
   对策：仅对新生成/新回放的 phase/final summary 强制完整集合，旧样本通过 replay 重算收敛。
3. 风险：Ops pack 新聚合字段引发跨层漂移。  
   对策：先冻结 v6 合同与测试夹具，再同步文档，不保留长期双轨字段。
4. 风险：无真实环境导致“完成”与“可上线”混淆。  
   对策：继续分层表达 `local_reference_ready` 与 `pass`，`on-env` 单独收口。

---

## 10. 模块完成同步历史

### 模块完成同步历史

1. 2026-04-20：完成 `ai-judge-p29-stage-closure`，归档文件：`/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260420T064142Z-ai-judge-stage-closure-execute.md`。
2. 2026-04-20：完成 `ai-judge-next-iteration-planning`，当前计划切换到 `P30`。
3. 2026-04-20：完成 `ai-judge-p30-judge-workflow-role-node-completeness-v1`，`phase/final` trace summary 对 `roleNodes` 增加完整集合/顺序/section/seq 合同断言，并补齐 `test_judge_trace_summary.py` 与 `test_replay_audit_ops.py` 覆盖。
4. 2026-04-20：完成 `ai-judge-p30-ops-read-model-pack-v6`，`ops/read-model/pack` 新增 `judgeWorkflowCoverage` 聚合，并同步 `ops_read_model_pack`/`app_factory` 回归测试通过。
5. 2026-04-20：完成 `ai-judge-p30-panel-readiness-route-split-v1`，`panels/runtime/profiles` 与 `panels/runtime/readiness` 路由改为调用 `app/applications/panel_runtime_routes.py`，并通过 `panel_runtime` 相关回归。
6. 2026-04-20：推进 `ai-judge-p30-registry-route-structure-split-v1` 第一批，下沉 `prompts/tools list/get`、`policy/dependencies/health`、`registries/{registry_type}/audits`、`releases list/get` 到 `app/applications/registry_routes.py`，并通过 `registries/policy` 回归。
7. 2026-04-20：继续推进 `ai-judge-p30-registry-route-structure-split-v1` 第二批，下沉 `publish/activate/rollback` 主链到 `app/applications/registry_routes.py`（含 gate/依赖告警分支与错误语义保留），并通过 `registries/policy` 回归。
8. 2026-04-20：完成 `ai-judge-p30-registry-route-structure-split-v1` 第三批，下沉 `governance/overview`、`prompt-tool/governance`、`policy/domain-families`、`policy/gate-simulation` 到 `app/applications/registry_routes.py`，并通过 `registries/policy` 回归。
9. 2026-04-20：推进 `ai-judge-p30-review-alert-route-split-v1` 第一批，下沉 `alerts/ops-view` 与 `alerts/outbox*` 到 `app/applications/review_alert_routes.py`，并通过 `review/alerts` 回归。
10. 2026-04-20：完成 `ai-judge-p30-review-alert-route-split-v1` 第二批，下沉 `review/cases*` 与 `cases/{id}/alerts*` 到 `app/applications/review_alert_routes.py`，并通过 `review/alerts` 与 `ops-view/outbox` 回归。
11. 2026-04-20：完成 `ai-judge-p30-local-regression-bundle-v1`，通过 `ruff check app tests`、`pytest -q`，并执行 `ai_judge_runtime_ops_pack --allow-local-reference`，结论为 `local_reference_ready`（非 real-env pass）。
12. 2026-04-20：完成 `ai-judge-p30-enterprise-consistency-refresh-v1`，修复计划文档标题门禁后通过 `harness_docs_lint` 与 `ai_judge_plan_consistency_gate`。

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

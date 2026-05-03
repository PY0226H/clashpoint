# 当前开发计划

关联 slot：`default`  
更新时间：2026-04-19  
当前主线：`AI_judge_service P22（法庭式主链完整化 + 结构降耦 + 契约冻结扩展）`  
当前状态：执行中（本地可执行模块已完成：`ai-judge-next-iteration-planning`、`ai-judge-p22-courtroom-workflow-role-contract-v1`、`ai-judge-p22-app-factory-structure-split-v5`、`ai-judge-p22-read-model-contract-freeze-v4`、`ai-judge-p22-ops-export-and-artifact-hygiene-v2`、`ai-judge-p22-local-regression-bundle-v4`、`ai-judge-p22-enterprise-consistency-refresh-v5`；下一步 `ai-judge-p22-real-env-pass-window-execute-on-env`（环境阻塞））

---

## 1. 计划定位

1. 本计划承接阶段收口归档：`/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260419T225103Z-ai-judge-stage-closure-execute.md`。
2. 当前明确前提：仍处于本地开发阶段，无真实环境窗口；涉及真实流量/真实压测样本的结论继续按 `on-env` 阻塞管理。
3. P22 的目标不是新增“花哨能力”，而是继续补齐企业方案与架构方案之间的落地主链：
   - 法庭式角色边界进一步显式化；
   - `app_factory` 热区继续下沉；
   - 关键 read-model 与导出契约再冻结一轮；
   - 保持本地回归与文档口径稳定。
4. 继续执行预发布硬切原则：不保留长期兼容层、灰度双轨、旧新 alias 或双写路径。

---

## 2. 当前代码状态快照（P22 起点）

截至 2026-04-19，`ai_judge_service` 当前状态：

1. 主链能力已具备：`phase/final dispatch + trace + replay + trust/challenge + fairness gate + failed callback`。
2. 已完成的结构收敛基础：
   - registry ops view 构建逻辑已抽到 `app/applications/registry_ops_views.py`；
   - fairness dashboard 契约校验模块已存在于 `app/applications/fairness_dashboard_contract.py`；
   - `ops_read_model_export` 已补 fairness dashboard 冻结字段检查与指标导出。
3. 当前仍可见的核心缺口：
   - `app_factory.py` 仍是热点文件（已下沉 fairness 分页扫描逻辑，后续继续拆分）；
   - read-model 冻结已扩展到 fairness dashboard / ops pack / drilldown / evidence-claim，导出脚本口径已同步；
   - real-env pass 仍为唯一环境阻塞项。

---

## 3. P22 总目标

1. 对齐企业方案第 6/7/8/9/10/11/12/13 章与架构方案第 5/6/10/13 章的落地主线。
2. 继续把“业务逻辑集中在 `app_factory`”的问题拆解为可维护应用层模块。
3. 提升 read-model 与导出链路的“字段稳定性 + 失败语义可追踪性”。
4. 在无真实环境条件下完成可复现本地收口，不误报 `pass`。

---

## 4. P22 模块执行矩阵

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 本轮目标 | DoD（完成定义） | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| `ai-judge-next-iteration-planning` | P0 | 已完成（2026-04-19） | 阶段收口后生成 P22 完整计划 | 当前计划切换为 P22，明确本地边界、执行矩阵与阻塞项 | `bash scripts/quality/harness_docs_lint.sh` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p22-courtroom-workflow-role-contract-v1` | P0 | 已完成（2026-04-19） | 法庭式角色运行契约显式化 | 对 Clerk/Recorder/ClaimGraph/Evidence/Panel/Fairness/Arbiter/Opinion 的关键输入输出与 stage 标记补齐显式契约（主链可观测，不改业务语义） | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_agent_runtime.py tests/test_app_factory.py -k "phase_dispatch_should_callback_and_support_idempotent_replay or final_dispatch_should_use_phase_receipts_and_callback"` + `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_judge_mainline.py tests/test_app_factory.py -k "judge_core or courtroom_read_model"` |
| `ai-judge-p22-app-factory-structure-split-v5` | P1 | 已完成（2026-04-19） | 继续拆分 `app_factory` 热点 | 再下沉一批高复杂聚合逻辑（优先 fairness dashboard / calibration / ops-pack 组装段），路由层保留编排职责 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_fairness_case_scan.py tests/test_app_factory.py -k "fairness_dashboard_route_should_return_overview_trends_and_top_risk or fairness_calibration_pack_route_should_return_thresholds_drift_and_risks or policy_calibration_advisor_route_should_return_gate_and_advisory_actions"` |
| `ai-judge-p22-read-model-contract-freeze-v4` | P1 | 已完成（2026-04-19） | 扩展冻结口径 | 对 fairness dashboard、ops pack、courtroom drilldown/evidence-claim 等关键聚合段补契约断言与失败分支回归 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py tests/test_agent_runtime.py tests/test_fairness_case_scan.py tests/test_review_queue_contract.py tests/test_fairness_dashboard_contract.py tests/test_ops_read_model_pack.py` |
| `ai-judge-p22-ops-export-and-artifact-hygiene-v2` | P1 | 已完成（2026-04-19） | 导出链路与工件治理收敛 | `ops_read_model_export` 与 read-model 冻结口径保持同步，artifact prune 脚本可稳定回归 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py tests/test_review_queue_contract.py -k "ops_read_model_pack_route_should_join_fairness_registry_and_trust_v5 or courtroom_drilldown_bundle_route_should_return_500_when_contract_validation_fails or evidence_claim_ops_queue_route_should_return_500_when_contract_validation_fails or review_queue_contract"` + `bash scripts/harness/tests/test_ai_judge_ops_read_model_export.sh` + `bash scripts/harness/tests/test_ai_judge_artifact_prune.sh` |
| `ai-judge-p22-local-regression-bundle-v4` | P2 | 已完成（2026-04-19） | 固化 P22 本地回归包 | 完成 `ruff + pytest + runtime_ops_pack(local_reference)` 并产出最新证据工件 | `cd ai_judge_service && ../scripts/py -m ruff check app tests` + `cd ai_judge_service && ../scripts/py -m pytest -q` + `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference` |
| `ai-judge-p22-enterprise-consistency-refresh-v5` | P2 | 已完成（2026-04-19） | 方案一致性刷新 | 更新章节完成度映射与当前计划状态，确保“企业方案/架构方案/代码口径”一致 | `bash scripts/quality/harness_docs_lint.sh` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p22-real-env-pass-window-execute-on-env` | P0（环境阻塞） | 阻塞（待真实环境窗口） | 真实环境 pass 冲刺 | `AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=pass` 且 `REAL_PASS_READY=true`，形成 on-env 证据归档 | `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p22-stage-closure-execute` | P2 | 待执行 | 执行阶段收口 | 归档当前活动计划，`completed/todo` 同步，计划文档重置到下一轮入口 | `bash scripts/harness/ai_judge_stage_closure_execute.sh --root /Users/panyihang/Documents/EchoIsle` |

### 下一开发模块建议

1. `ai-judge-p22-real-env-pass-window-execute-on-env`（环境阻塞）
2. `ai-judge-p22-stage-closure-execute`

---

## 5. 延后事项（不阻塞 P22）

1. `real-env pass` 相关能力（严格 `on-env`）。
2. `NPC Coach / Room QA` 正式业务策略与主链接入（等待你冻结 PRD 后再推进）。
3. 协议化扩展（链上锚定 / ZK / ZKML）继续保持后置，不进入当前主链。

---

## 6. 执行顺序与依赖

1. 先做 `courtroom-workflow-role-contract-v1`，稳住法庭式角色边界。
2. 再做 `app-factory-structure-split-v5`，持续降低维护热区。
3. 完成 `read-model-contract-freeze-v4` 与 `ops-export-and-artifact-hygiene-v2`，收敛读面与导出口径。
4. 跑 `local-regression-bundle-v4`，固化本地证据。
5. 做 `enterprise-consistency-refresh-v5`，保持文档与代码一致。
6. 执行阶段收口；real-env 窗口就绪后再单独推进 `on-env pass`。

---

## 7. 本阶段明确不做

1. 不推进 `NPC Coach / Room QA` 正式功能开发。
2. 不为未上线能力保留长期兼容层（alias/双写/灰度并行）。
3. 不将 `local_reference_ready` 或 `local_reference_frozen` 表述为 `pass`。

---

## 8. 测试与验收基线

1. `bash skills/python-venv-guard/scripts/assert_venv.sh --project /Users/panyihang/Documents/EchoIsle/ai_judge_service --venv /Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv`
2. `cd ai_judge_service && ../scripts/py -m ruff check app tests`
3. `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py tests/test_ops_read_model_pack.py tests/test_fairness_dashboard_contract.py`
4. `cd ai_judge_service && ../scripts/py -m pytest -q`
5. `bash scripts/harness/tests/test_ai_judge_ops_read_model_export.sh`
6. `bash scripts/harness/tests/test_ai_judge_artifact_prune.sh`
7. `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`
8. `bash scripts/quality/harness_docs_lint.sh`
9. `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle`

---

## 9. 风险与对策

1. 风险：法庭式角色边界继续隐式化，后续迭代容易回退为“大 pipeline”。
   对策：P22-M1 先补角色运行契约与 stage 可观测边界，再做功能扩展。
2. 风险：`app_factory` 继续膨胀导致维护与回归成本上升。
   对策：P22-M2 持续拆分热点聚合逻辑，路由仅保留编排职责。
3. 风险：read-model 输出字段隐式漂移，导出/看板口径失配。
   对策：P22-M3/M4 扩展契约冻结并把导出脚本纳入回归门禁。
4. 风险：无真实环境导致状态被误读。
   对策：严格区分 `local_reference_*` 与 `pass`，保持 on-env 独立收口。

---

## 10. 模块完成同步历史

### 模块完成同步历史

1. 2026-04-19：完成 `ai-judge-stage-closure-execute`，当前开发计划已归档到 `20260419T225103Z-ai-judge-stage-closure-execute.md` 并重置。
2. 2026-04-19：完成 `ai-judge-next-iteration-planning`，当前计划切换到 P22 并锁定“无真实环境”执行边界。
3. 2026-04-19：完成 `ai-judge-p22-courtroom-workflow-role-contract-v1`，补齐 8 角色 stage/input/output 运行契约显式字段，并同步 `judgeTrace.agentRuntime` 契约版本透出与回归测试。
4. 2026-04-19：完成 `ai-judge-p22-app-factory-structure-split-v5`，新增 `fairness_case_scan` 应用层模块并在 dashboard/calibration/advisor 路由下沉公平性分页扫描逻辑。
5. 2026-04-19：完成 `ai-judge-p22-read-model-contract-freeze-v4`，新增 `review_queue_contract` 并将 courtroom drilldown/evidence-claim 队列纳入契约冻结与 500 失败分支校验。
6. 2026-04-19：完成 `ai-judge-p22-ops-export-and-artifact-hygiene-v2`，同步导出脚本冻结键检查并修正 evidence-claim unanswered 统计映射，导出/工件脚本回归通过。
7. 2026-04-19：完成 `ai-judge-p22-local-regression-bundle-v4`，全量 `ruff + pytest` 与 `runtime_ops_pack(local_reference)` 回归通过。
8. 2026-04-19：完成 `ai-judge-p22-enterprise-consistency-refresh-v5`，章节完成度映射刷新并通过 docs lint + plan consistency gate。

---

## 11. 本轮启动检查清单

1. 开发前运行 `pre-module-prd-goal-guard`（按模块执行）。
2. 涉及 API/DTO/错误码变更时，同轮同步调用方、测试与文档。
3. 与真实环境有关结论必须标注 `on-env`，本地阶段不得宣称 `pass`。
4. 每完成一个模块都回写当前计划矩阵与同步历史。

---

## 12. 架构方案第13章一致性校验（计划生成前置）

1. **角色一致性**：继续沿用法庭式 8 Agent 边界，不新增绕过 Sentinel/Arbiter 的捷径路径。
2. **数据一致性**：六对象主链仍是唯一裁决事实源，不引入平行 winner 写链。
3. **门禁一致性**：fairness/review/registry/trust gate 不弱化；新增能力需显式标注主链或 advisory-only。
4. **边界一致性**：`NPC/Room QA` 保持 `advisory_only`，不写官方裁决链。
5. **跨层一致性**：契约变更同轮同步调用方、测试与文档，不保留长期双轨 alias。
6. **收口一致性**：真实环境结论与本地参考结论分层表达，未获窗口前不宣称 `pass`。

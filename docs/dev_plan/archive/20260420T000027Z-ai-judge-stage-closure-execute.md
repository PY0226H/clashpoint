# 当前开发计划

关联 slot：`default`  
更新时间：2026-04-19  
当前主线：`AI_judge_service P23（公平读面契约冻结 + 结构拆分延续 + on-env 收口准备）`  
当前状态：执行中（已完成 `ai-judge-next-iteration-planning`、`ai-judge-p23-case-fairness-contract-freeze-v1`、`ai-judge-p23-panel-runtime-profile-contract-freeze-v1`、`ai-judge-p23-app-factory-structure-split-v6`、`ai-judge-p23-ops-export-contract-alignment-v2`、`ai-judge-p23-local-regression-bundle-v5`、`ai-judge-p23-enterprise-consistency-refresh-v6`，下一步 `ai-judge-p23-real-env-pass-window-execute-on-env`）

---

## 1. 计划定位

1. 本计划承接阶段收口归档：`/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260419T231801Z-ai-judge-stage-closure-execute.md`。
2. 当前前提不变：仅本地开发环境可用，真实环境窗口仍不可用；所有 `pass` 级环境结论继续标记为 `on-env`。
3. P23 的目标是承接 P22 已完成成果，继续做“可维护+可验证”主链深化：
   - 扩展关键读面契约冻结（case fairness / panel runtime profile）。
   - 继续下沉 `app_factory` 高复杂公平分析逻辑。
   - 保持导出链路与 read-model 冻结口径一致。
   - 在不依赖真实环境的前提下完成本地闭环证据。
4. 继续执行预发布硬切原则：不保留长期兼容层、灰度双轨、旧字段 alias 或双写路径。

---

## 2. 当前代码状态快照（P23 起点）

截至 2026-04-19，`ai_judge_service` 当前状态：

1. 主链能力已具备：`phase/final dispatch + trace + replay + trust/challenge + fairness gate + failed callback`。
2. P22 已完成并稳定：
   - 法庭式 8 角色运行契约显式化（含 stage/input/output/activation）。
   - `fairness_case_scan` 下沉，dashboard/calibration/advisor 扫描逻辑复用。
   - `review_queue_contract` 上线，`courtroom drilldown` 与 `evidence-claim queue` 接口具备契约冻结与 500 失败语义。
   - `ops_read_model_export` 已与 drilldown/evidence-claim/case fairness/panel runtime profile 关键冻结字段对齐。
3. 当前仍可见的核心缺口：
   - `app_factory.py` 仍为热点文件，但 fairness dashboard/calibration 核心聚合已下沉到 `app/applications/fairness_analysis.py`。
   - real-env pass 仍是唯一环境阻塞项。

---

## 3. P23 总目标

1. 对齐企业方案第 6/7/8/9/10/11/12/13 章与架构方案第 5/6/10/13 章。
2. 把“读面稳定性”从点状冻结推进到队列与看板核心入口。
3. 继续降低 `app_factory` 聚合复杂度，提升后续迭代可维护性。
4. 在无真实环境条件下完成可复现本地收口，不误报 `pass`。

---

## 4. P23 模块执行矩阵

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 本轮目标 | DoD（完成定义） | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| `ai-judge-next-iteration-planning` | P0 | 已完成（2026-04-19） | 阶段收口后生成 P23 完整计划 | 当前计划切换到 P23，明确模块边界、阻塞项与执行顺序 | `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p23-case-fairness-contract-freeze-v1` | P0 | 已完成（2026-04-19） | 冻结 `fairness/cases` 读面契约 | 新增 contract 校验模块并接入 `/internal/judge/fairness/cases`（detail/list）返回链路；补 500 契约失败分支与独立 contract 单测 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "cases_route_should_support_filters_sorting_and_pagination or fairness"` + `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_fairness_case_contract.py` |
| `ai-judge-p23-panel-runtime-profile-contract-freeze-v1` | P1 | 已完成（2026-04-19） | 冻结 `panels/runtime/profiles` 读面契约 | 新增 panel runtime profile 聚合契约校验并接入 `/internal/judge/panels/runtime/profiles` 返回链路；补 500 契约失败分支与独立 contract 单测 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "panel_runtime_profiles"` + `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_panel_runtime_profile_contract.py` |
| `ai-judge-p23-app-factory-structure-split-v6` | P1 | 已完成（2026-04-19） | 继续拆分公平分析热点 | fairness dashboard/calibration 核心聚合函数下沉到 `app/applications/fairness_analysis.py`，`app_factory` 保留编排与调用 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "fairness_dashboard_route or fairness_calibration_pack_route or policy_calibration_advisor_route"` |
| `ai-judge-p23-ops-export-contract-alignment-v2` | P1 | 已完成（2026-04-19） | 导出脚本与新增冻结口径同步 | `ops_read_model_export` 增补 case fairness / panel runtime profile 关键字段检测与指标导出；脚本测试覆盖通过 | `bash scripts/harness/tests/test_ai_judge_ops_read_model_export.sh` |
| `ai-judge-p23-local-regression-bundle-v5` | P2 | 已完成（2026-04-19） | 固化 P23 本地回归包 | 完成 `ruff + pytest + runtime_ops_pack(local_reference)` 并产出最新工件 | `cd ai_judge_service && ../scripts/py -m ruff check app tests` + `cd ai_judge_service && ../scripts/py -m pytest -q` + `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference` |
| `ai-judge-p23-enterprise-consistency-refresh-v6` | P2 | 已完成（2026-04-19） | 文档一致性刷新 | 更新章节完成度映射与当前计划，确保“企业方案/架构方案/代码口径”一致 | `bash scripts/quality/harness_docs_lint.sh` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p23-real-env-pass-window-execute-on-env` | P0（环境阻塞） | 阻塞（待真实环境窗口） | 真实环境 pass 冲刺 | `AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=pass` 且 `REAL_PASS_READY=true` | `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p23-stage-closure-execute` | P2 | 待执行 | 阶段收口执行 | 归档活动计划，`completed/todo` 同步，计划重置到下一轮入口 | `bash scripts/harness/ai_judge_stage_closure_execute.sh --root /Users/panyihang/Documents/EchoIsle` |

### 下一开发模块建议

1. `ai-judge-p23-real-env-pass-window-execute-on-env`（真实环境窗口可用时执行）
2. 若真实环境仍不可用，则先执行 `ai-judge-p23-stage-closure-execute`

---

## 5. 延后事项（不阻塞 P23）

1. `real-env pass` 相关能力（严格 `on-env`）。
2. `NPC Coach / Room QA` 正式业务策略与主链接入（等待你冻结 PRD 后再推进）。
3. 协议化扩展（链上锚定 / ZK / ZKML）继续保持后置，不进入当前主链。

---

## 6. 执行顺序与依赖

1. 先做 `case-fairness-contract-freeze-v1`，稳住 fairness 读面主入口。
2. 再做 `panel-runtime-profile-contract-freeze-v1`，补齐 panel 运维视图契约层。
3. 推进 `app-factory-structure-split-v6`，下沉公平分析热点函数。
4. 同步 `ops-export-contract-alignment-v2`，避免导出链路字段漂移。
5. 执行 `local-regression-bundle-v5` 与 `enterprise-consistency-refresh-v6`。
6. 最后执行阶段收口；真实环境窗口就绪后单独推进 `on-env pass`。

---

## 7. 本阶段明确不做

1. 不推进 `NPC Coach / Room QA` 正式功能开发。
2. 不为未上线能力保留长期兼容层（alias/双写/灰度并行）。
3. 不将 `local_reference_ready` 或 `local_reference_frozen` 表述为 `pass`。

---

## 8. 测试与验收基线

1. `bash skills/python-venv-guard/scripts/assert_venv.sh --project /Users/panyihang/Documents/EchoIsle/ai_judge_service --venv /Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv`
2. `cd ai_judge_service && ../scripts/py -m ruff check app tests`
3. `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py tests/test_review_queue_contract.py tests/test_fairness_dashboard_contract.py tests/test_ops_read_model_pack.py`
4. `cd ai_judge_service && ../scripts/py -m pytest -q`
5. `bash scripts/harness/tests/test_ai_judge_ops_read_model_export.sh`
6. `bash scripts/harness/tests/test_ai_judge_artifact_prune.sh`
7. `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`
8. `bash scripts/quality/harness_docs_lint.sh`
9. `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle`

---

## 9. 风险与对策

1. 风险：核心读面契约继续隐式漂移，导致 Ops/导出口径不稳定。  
   对策：P23-M1/M2 已完成，后续在 M4 导出链路继续保持冻结键与服务契约一致。
2. 风险：`app_factory` 热点持续膨胀，后续改动回归成本上升。  
   对策：P23-M3 继续下沉 fairness 聚合函数到应用层模块。
3. 风险：导出脚本与服务返回字段失配。  
   对策：P23-M4 同步冻结键检查并纳入脚本测试门禁。
4. 风险：无真实环境导致状态被误读。  
   对策：严格区分 `local_reference_*` 与 `pass`，保留 `on-env` 单独收口。

---

## 10. 模块完成同步历史

### 模块完成同步历史

1. 2026-04-19：完成 `ai-judge-stage-closure-execute`，归档 `P22` 到 `20260419T231801Z-ai-judge-stage-closure-execute.md`。
2. 2026-04-19：完成 `ai-judge-next-iteration-planning`，当前计划切换到 `P23`。
3. 2026-04-19：完成 `ai-judge-p23-case-fairness-contract-freeze-v1`，新增 `fairness_case_contract` 模块并接入 `fairness/cases` detail/list 500 契约失败语义与测试。
4. 2026-04-19：完成 `ai-judge-p23-panel-runtime-profile-contract-freeze-v1`，新增 `panel_runtime_profile_contract` 模块并接入 `panels/runtime/profiles` 500 契约失败语义与测试。
5. 2026-04-19：完成 `ai-judge-p23-app-factory-structure-split-v6`，新增 `fairness_analysis` 模块并下沉 dashboard/calibration 核心聚合函数。
6. 2026-04-19：完成 `ai-judge-p23-ops-export-contract-alignment-v2`，`ops_read_model_export` 新增 `fairness/cases` 与 `panels/runtime/profiles` 请求校验链路，并补齐导出指标字段与脚本测试。
7. 2026-04-19：完成 `ai-judge-p23-local-regression-bundle-v5`，`ruff check app tests`、`pytest -q` 与 `runtime_ops_pack(--allow-local-reference)` 全部通过。
8. 2026-04-19：完成 `ai-judge-p23-enterprise-consistency-refresh-v6`，刷新企业方案章节完成度映射，并通过 `harness_docs_lint + plan_consistency_gate` 收口一致性。

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

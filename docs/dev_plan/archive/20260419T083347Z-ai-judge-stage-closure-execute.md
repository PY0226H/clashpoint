# 当前开发计划

关联 slot：`default`  
更新时间：2026-04-18  
当前主线：`AI_judge_service P18（Registry 产品化 + Evidence/Claim 深化 + Ops Pack v5 + 架构拆分收敛）`  
当前状态：执行中（已完成 `ai-judge-next-iteration-planning`、`ai-judge-p18-registry-prompt-tool-governance-v1`、`ai-judge-p18-evidence-claim-ops-queue-v1`、`ai-judge-p18-courtroom-drilldown-bundle-v1`、`ai-judge-p18-ops-pack-and-export-v5`、`ai-judge-p18-app-factory-structure-split-v1`、`ai-judge-p18-enterprise-architecture-consistency-refresh`、`ai-judge-p18-local-pass-rehearsal`，下一步 `P18-M9（阶段收口）`）

---

## 1. 计划定位

1. 本计划承接 `P17` 阶段收口（归档：`docs/dev_plan/archive/20260418T101828Z-ai-judge-stage-closure-execute.md`），进入下一轮可开发主线。
2. 本轮目标不是再横向堆接口，而是按企业方案与架构方案把“法庭式裁判平台”继续做深：补齐 `Prompt/Tool Registry` 产品化治理、强化 `Evidence/Claim` 运维读面，并把 `ops/read-model/pack` 升级到 v5。
3. 本轮继续执行预发布硬切原则：不保留长期兼容层、双轨链路、灰度旧路径。
4. 本轮严格保持边界：
   - `NPC Coach / Room QA` 继续 `advisory_only`（保留 runtime shell，不进入官方裁决写链）。
   - `real-env pass` 继续单列为环境窗口阻塞项，不把本地演练结论写成 `pass`。

---

## 2. 当前代码状态快照（P18 起点）

截至 2026-04-18，`ai_judge_service` 当前状态：

1. P17 已完成：`courtroom/cases`、`trust/challenges/ops-queue`、`review unified priority`、`ops pack v4`、本地收口演练均已落地并归档。
2. 官方裁决主链闭环已具备：`phase/final dispatch + trace + replay + review + failed callback + trust challenge`。
3. Registry 主链可用：`policy/prompt/tool` 的 `publish/activate/rollback/audit/release` 与 policy gate simulation 已有实现。
4. Ops 聚合读面可用：`/internal/judge/ops/read-model/pack` 已升级到 v5，含 fairness/registry/review/courtroom/trust + registry prompt/tool governance + evidence claim queue + courtroom drilldown 综合视图。
5. 结构层风险仍明显：
   - [app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/app/app_factory.py) 约 `13,819` 行；
   - [test_app_factory.py](/Users/panyihang/Documents/EchoIsle/ai_judge_service/tests/test_app_factory.py) 约 `6,401` 行；
   - judge 内部路由规模已达 `64` 个（维护与回归成本高）。
6. 与企业方案/架构方案仍存在的核心缺口：
   - `real-env pass` 仍未执行（环境窗口阻塞）；
   - `NPC Coach / Room QA` 仍保持 `advisory_only` 壳层，等待产品 PRD 冻结后再入主链；
   - `app_factory` 虽完成首轮拆分，但仍是集中式路由+编排热点，需继续分层收敛。

---

## 3. P18 总目标

1. 对齐企业方案第 5/6/8/11/13/17 章与架构方案第 5.1/5.3/5.4：把 Judge 主链从“功能完整”推进到“治理可运维 + 结构可持续”。
2. 完成 `Prompt/Tool Registry` 的产品化运维读面，补齐发布前可观察治理链路（不改变 policy 主语义）。
3. 完成 `Evidence/Claim` 的批量化运维读面，支撑复核与争议定位的 Case 队列化处理。
4. 升级 `ops/read-model/pack` 到 v5，把 registry/evidence/claim 新读面统一打包到第三方看板可消费口径。
5. 进行一次 `app_factory` 的首轮结构收敛：抽离核心读面构建逻辑，降低后续迭代复杂度。

---

## 4. P18 模块执行矩阵

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 本轮目标 | DoD（完成定义） | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| `ai-judge-next-iteration-planning` | P0 | 已完成（2026-04-18） | 基于企业方案+架构方案+当前代码状态生成 P18 计划 | 当前计划已切换为 P18，并给出模块矩阵/门禁口径/阻塞边界 | `bash scripts/quality/harness_docs_lint.sh` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p18-registry-prompt-tool-governance-v1` | P1 | 已完成（2026-04-18） | 补齐 Prompt/Tool Registry 产品化治理视图 | 在现有 registry 主链上新增 `/internal/judge/registries/prompt-tool/governance`，提供 risk summary/risk items/action hints 的产品化治理读面；补齐路由暴露测试与治理用例，不改变 policy gate 主语义 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "registry and prompt and tool and governance"` |
| `ai-judge-p18-evidence-claim-ops-queue-v1` | P1 | 已完成（2026-04-18） | 建立 Evidence/Claim 批量运维队列 | 新增 `/internal/judge/evidence-claim/ops-queue`，支持 conflict/reliability/unanswered/risk/sla 过滤与排序，返回 action hints 与 detail path，并补齐路由暴露+筛选排序校验测试 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "evidence and claim and ops"` |
| `ai-judge-p18-courtroom-drilldown-bundle-v1` | P1 | 已完成（2026-04-18） | 增强 courtroom 高级展开层 | 新增 `/internal/judge/courtroom/drilldown-bundle`，提供 claim/evidence/panel/fairness/opinion/governance 的批量 drilldown 展开、action hints 与聚合计数，保持只读无副作用 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "courtroom and drilldown"` |
| `ai-judge-p18-ops-pack-and-export-v5` | P1 | 已完成（2026-04-18） | 升级 ops 聚合包与导出口径到 v5 | `ops/read-model/pack` 新增 `registryPromptToolGovernance`、`evidenceClaimQueue`、`courtroomDrilldown` 聚合段；`scripts/harness/ai_judge_ops_read_model_export.sh` 与脚本测试同步升级 | `bash scripts/harness/tests/test_ai_judge_ops_read_model_export.sh` + `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "ops and pack and v5"` |
| `ai-judge-p18-app-factory-structure-split-v1` | P2 | 已完成（2026-04-18） | 首轮结构拆分收敛 | 抽离 `app_factory` 中 registry/ops/courtroom 读面构建函数到独立 application/domain 模块并保持契约不变；新增针对新模块的最小单测 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py tests/test_ops_read_model_pack.py` |
| `ai-judge-p18-enterprise-architecture-consistency-refresh` | P2 | 已完成（2026-04-18） | 同步更新章节完成度映射 | `AI_Judge_Service-企业级Agent方案-章节完成度映射-2026-04-13.md` 更新到 P18 口径，补齐 registry/evidence/ops v5 映射 | `bash scripts/quality/harness_docs_lint.sh` |
| `ai-judge-p18-local-pass-rehearsal` | P2 | 已完成（2026-04-18） | 在无真实环境条件下完成本地参考收口演练 | 输出 runtime/ops/fairness/real-pass rehearsal 本地证据并明确 `local_reference_ready`，不宣称 real-env pass | `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference` + `bash scripts/harness/ai_judge_real_pass_rehearsal.sh --root /Users/panyihang/Documents/EchoIsle` + `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference` |
| `ai-judge-p18-real-env-pass-window-execute-on-env` | P0（环境阻塞） | 阻塞（待真实环境窗口） | 真实环境窗口 pass 冲刺 | `AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=pass` 且 `REAL_PASS_READY=true`，形成 on-env 证据归档 | `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p18-stage-closure-execute` | P2 | 待执行 | 执行阶段收口 | 活动计划归档、`completed/todo` 同步、当前计划重置到下一轮模板 | `bash scripts/harness/ai_judge_stage_closure_execute.sh --root /Users/panyihang/Documents/EchoIsle` |

### 下一开发模块建议

1. `ai-judge-p18-stage-closure-execute`

---

## 5. 延后事项（不阻塞 P18）

1. 真实环境样本驱动的阈值冻结、容量规划、成本路由优化（`on-env`）。
2. `NPC Coach / Room QA` 正式业务策略与产品逻辑（等待你冻结这两个模块 PRD）。
3. 链上协议化扩展（ZK/ZKML/链上锚定）继续保持接口预留，主链实现后置。
4. 是否引入 `Temporal/Kafka adapter` 的基础设施升级决策，继续以后续真实运维样本为依据。

---

## 6. 执行顺序与依赖

1. 先做 `registry-prompt-tool-governance-v1`，补齐 Prompt/Tool 产品化治理入口。
2. 再做 `evidence-claim-ops-queue-v1`，把 Evidence/Claim 从单案可查升级为批量可运营。
3. 然后做 `courtroom-drilldown-bundle-v1`，补齐高级展开层读面。
4. 基于前三项升级 `ops-pack-and-export-v5`，统一看板导出口径。
5. 完成首轮 `app-factory-structure-split-v1`，降低后续功能堆叠成本。
6. 更新章节映射与本地收口演练，再执行阶段收口。
7. 真实环境窗口就绪后，单独推进 `real-env-pass-window-execute-on-env`。

---

## 7. 本阶段明确不做

1. 不推进 `NPC Coach / Room QA` 正式业务实现。
2. 不为未上线能力保留长期兼容双轨（alias/双写/灰度并行）。
3. 不新增绕过 Sentinel/Arbiter 的捷径判决路径。
4. 不将本地演练结论标记为 `real-env pass`。

---

## 8. 测试与验收基线

1. 全量回归：`cd ai_judge_service && ../scripts/py -m pytest -q`
2. 主链回归：`cd ai_judge_service && ../scripts/py -m pytest -q tests/test_judge_mainline.py tests/test_phase_final_contract_models.py tests/test_app_factory.py tests/test_evidence_ledger.py`
3. P18 重点回归：`cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "registry or evidence or claim or courtroom or ops"`
4. 质量门禁：
   - `cd ai_judge_service && ../scripts/py -m ruff check app tests`
   - `bash scripts/quality/harness_docs_lint.sh`
   - `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle`
5. 本地收口基线（非 real-env pass）：
   - `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`
   - `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`

---

## 9. 风险与对策

1. 风险：P18 功能继续集中在 `app_factory`，导致复杂度继续上升。  
   对策：本轮强制落地 `app-factory-structure-split-v1`，把核心读面构建逻辑抽离为独立模块。
2. 风险：Registry/Evidence 新增读面与现有 ops pack 口径冲突。  
   对策：先冻结字段契约，再同轮更新导出脚本和脚本测试。
3. 风险：P18 新读面查询压力上升，影响本地回归稳定性。  
   对策：优先轻摘要 + scan limit + 分页；必要时再补索引/缓存。
4. 风险：本地演练结论被误解为真实环境结论。  
   对策：所有收口文案强制区分 `local_reference_ready` 与 `pass`。

---

## 10. 模块完成同步历史

### 模块完成同步历史

1. 2026-04-18：完成 `ai-judge-next-iteration-planning`，基于企业方案+架构方案+当前代码状态生成 P18 完整开发计划，并切换本计划主线至 P18。
2. 2026-04-18：完成 `ai-judge-p18-registry-prompt-tool-governance-v1`，新增 `/internal/judge/registries/prompt-tool/governance` 读面（risk summary/risk items/action hints），并补齐路由暴露测试与治理风险截断测试。
3. 2026-04-18：完成 `ai-judge-p18-evidence-claim-ops-queue-v1`，新增 `/internal/judge/evidence-claim/ops-queue`，打通 conflict/reliability/unanswered/risk/sla 批量筛选排序与 action hints/detail path。
4. 2026-04-18：完成 `ai-judge-p18-courtroom-drilldown-bundle-v1`，新增 `/internal/judge/courtroom/drilldown-bundle`，支持批量 drilldown 展开、聚合统计与 action hints。
5. 2026-04-18：完成 `ai-judge-p18-ops-pack-and-export-v5`，将 `/internal/judge/ops/read-model/pack` 升级到 v5（新增 `registryPromptToolGovernance`、`evidenceClaimQueue`、`courtroomDrilldown`）并同步导出脚本与脚本测试口径。
6. 2026-04-18：完成 `ai-judge-p18-app-factory-structure-split-v1`，新增 `app/applications/ops_read_model_pack.py` 并将 `ops/read-model/pack` 的 `adaptiveSummary/trustOverview/filters` 构建逻辑从 `app_factory` 抽离，补齐独立单测 `tests/test_ops_read_model_pack.py`。
7. 2026-04-18：完成 `ai-judge-p18-enterprise-architecture-consistency-refresh`，更新 [AI_Judge_Service-企业级Agent方案-章节完成度映射-2026-04-13.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/AI_Judge_Service-企业级Agent方案-章节完成度映射-2026-04-13.md) 到 P18-M1~M5 口径，并通过 docs lint 与 plan consistency gate。
8. 2026-04-18：完成 `ai-judge-p18-local-pass-rehearsal`，执行 `runtime_ops_pack + real_pass_rehearsal + real_env_window_closure(--allow-local-reference)`，得到 `local_reference_ready` 口径证据，继续保持 `real-env pass` 阻塞状态。

---

## 11. 本轮启动检查清单

1. 开发前先跑 `pre-module-prd-goal-guard`（本轮已执行，模式为 `full`）。
2. 任何 API/DTO/错误码变更，同轮检查调用方、路由测试与文档，不保留长期 alias。
3. 与 `real-env` 相关结论必须标记 `on-env`，禁止把本地结论写成 pass。
4. 每完成一个模块就回写本计划矩阵与同步历史。

---

## 12. 架构方案第13章一致性校验（计划生成前置）

1. **角色一致性**：继续沿用法庭式 8 Agent 职责，不新增绕过 Sentinel/Arbiter 的捷径路径。
2. **数据一致性**：六对象主链仍是唯一裁决事实源，不引入平行 verdict 写链。
3. **门禁一致性**：fairness/review/registry/trust gate 不弱化；新增能力需显式标注是否 advisory-only。
4. **边界一致性**：`NPC/Room QA` 继续 `advisory_only`，不写官方裁决链。
5. **跨层一致性**：契约变更同轮同步调用方和测试，不保留长期双轨 alias。
6. **收口一致性**：真实环境结论与本地参考结论继续分层表达，未获窗口前不宣称 `pass`。

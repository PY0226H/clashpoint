# 当前开发计划

关联 slot：`default`  
更新时间：2026-04-17  
当前主线：`AI_judge_service P13（Fairness Hardened 工程化收口 + Shadow Evaluation 启动 + real-env 窗口待执行）`  
当前状态：执行中（P13-M1/M2/M3/M4 已完成；real-env 仍为窗口阻塞）

---

## 1. 计划定位

1. 本计划承接 `P12`，目标是把企业方案的 `Phase 2（Fairness Hardened）` 从“已实现门禁”推进到“可运营、可核验、可发布门禁”。
2. 本轮继续执行硬切原则：不保留兼容层、灰度双轨、旧新并行主链。
3. 当前产品仍在本地开发，凡依赖真实环境数据的结论统一标记为 `on-env`，不与本机参考结论混写。
4. 本计划要求后续每次“下一阶段开发计划”先通过架构方案第13章一致性检查（角色/数据/门禁/边界/跨层/收口）。

---

## 2. 当前代码状态快照（P13 起点）

以下能力作为 P13 基线保留，不回退：

1. `trace/replay/review/failed callback` 主链已可用，且具备可追踪落库。
2. 法庭式 8 Agent 主链已显式建模，`Fairness Sentinel -> Chief Arbiter` 门禁关系已在主链生效。
3. 六对象主链已形成稳定路径：`case_dossier / claim_graph / evidence_bundle / verdict_ledger / fairness_report / opinion_pack`。
4. 公平门禁三件套已入主链：`label_swap_instability / style_shift_instability / panel_disagreement`，并接入 `draw/review_required`。
5. `registry` 三元（policy/prompt/tool）与 fairness benchmark 路由已具备，发布治理主链已可用。
6. 可验证信任层 `phaseA/phaseB` 已有主链接口；`public-verify` 聚合读接口已进入回归可用状态。
7. `opinionPack.userReport` 的 `phaseDebateTimeline/evidenceInsightCards` 与 `evidence reliability guard` 已完成基线冻结并通过回归。
8. `fairness_shadow_runs` 事实源与 `/internal/judge/fairness/shadow-runs` 写读接口已落地，`fairness/cases` 已可读取 `shadowSummary`。
9. `/internal/judge/fairness/dashboard` 聚合读接口与 `ai_judge_fairness_dashboard_export.sh` 导出脚本已落地，支持 `overview/trends/topRiskCases/gateDistribution` 稳定导出。
10. policy release gate 已接入 shadow 评测结果：`publish/activate` 在 benchmark 通过后会继续校验 latest shadow run，shadow 超阈值默认阻断，仅允许带理由 override，审计链与告警链可追踪。
11. `NPC Coach / Room QA` 仅保留 `advisory_only` 内部入口壳，未侵入官方裁决链。
12. real-env 收口当前仍是 `local_reference_ready`，未达到 `pass`。

---

## 3. P13 总目标（下一阶段）

1. 先冻结当前在途改动，确保 `public-verify + opinion timeline + evidence reliability guard` 完成测试闭环与文档对齐。
2. 新增 `shadow evaluation` 数据主链，让公平性从“单案门禁”升级为“样本集对比与漂移追踪”。
3. 形成可运营公平读模型与导出能力，支持后续接第三方运维看板，而不是在服务里重造完整看板前端。
4. 将 `shadow drift` 纳入 policy release gate，避免“benchmark 通过但影子评测明显漂移”的错误发布。
5. 保持 real-env 口径严格分层：窗口前只认 `local_reference_ready`，窗口到位后再冲刺 `pass`。

---

## 4. P13 模块执行矩阵

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 本轮目标 | DoD（完成定义） | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| `ai-judge-p13-baseline-delta-freeze` | P0 | 已完成（2026-04-17） | 冻结当前在途改动（`public-verify`、`opinion timeline/cards`、`evidence reliability guard`） | 相关代码和测试闭环通过，映射文档与计划状态同步，形成可复跑证据 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py tests/test_judge_mainline.py tests/test_evidence_ledger.py tests/test_phase_final_contract_models.py` |
| `ai-judge-p13-fairness-shadow-eval-ledger-v1` | P1 | 已完成（2026-04-17） | 新增 `shadow evaluation` 落库与查询能力（不参与官方 winner 写链） | `shadow run` 数据模型、写读接口、fairness case `shadowSummary` 与 `has_shadow_breach` 过滤已可用 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_fact_repository.py tests/test_app_factory.py -k "shadow"` |
| `ai-judge-p13-fairness-dashboard-export-v1` | P1 | 已完成（2026-04-17） | 提供公平运营聚合读接口 + 导出脚本（JSON/MD） | `/internal/judge/fairness/dashboard` 与 `ai_judge_fairness_dashboard_export.sh` 已可输出 `overview/trends/topRiskCases/gateDistribution`，并具备脚本回归测试 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "fairness_dashboard_route_should_return_overview_trends_and_top_risk"` + `bash scripts/harness/tests/test_ai_judge_fairness_dashboard_export.sh` |
| `ai-judge-p13-policy-release-gate-shadow-link` | P1 | 已完成（2026-04-17） | 把 shadow 漂移结论接入 registry release gate | 发布/激活时若 shadow 漂移超阈值则阻断或转人工 override，且审计链可追踪 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "policy_registry_activate_should_block_when_shadow_gate_not_ready or policy_registry_publish_activate_should_allow_shadow_gate_override_and_audit"` |
| `ai-judge-p13-stage-closure-execute` | P2 | 待执行 | 在本阶段尾部执行标准收口（主体完成/环境阻塞/下轮入口） | 产出 stage closure summary，`completed/todo` 分离清晰，且与计划矩阵一致 | `bash scripts/harness/ai_judge_stage_closure_execute.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p13-real-env-pass-window-execute-on-env` | P0（环境阻塞） | 阻塞（待真实环境窗口） | 真实环境窗口到来时执行一键收口冲刺 | `AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=pass` 且 `REAL_PASS_READY=true`，并具备 real-env 证据键 | `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle` |

---

## 5. 延后事项（不阻塞当前阶段）

1. 真实环境样本驱动的阈值最终冻结（runtime SLA / fairness benchmark）继续保留 `on-env`。
2. 真实部署环境压测、成本账单和长期漂移观测仍待后续环境窗口。
3. `NPC Coach / Room QA` 正式产品化需求未冻结，当前不推进功能实装，仅保留平台边界。
4. `multi-model panel / policy auto-calibration / domain judge families` 属于企业方案 Phase 3，不在本阶段进入主链。

### 下一开发模块建议

1. `ai-judge-p13-stage-closure-execute`
2. `ai-judge-p13-real-env-pass-window-execute-on-env`

---

## 6. 执行顺序与依赖

1. 先完成 `baseline-delta-freeze`，把工作区在途改动转为可验证基线，避免后续模块叠加在不稳定状态上。
2. 再做 `shadow-eval-ledger-v1`，先落事实源与读写模型。
3. 基于 shadow 数据推进 `fairness-dashboard-export-v1`，形成运营可消费结构（已完成）。
4. 在读模型稳定后接入 `policy-release-gate-shadow-link`，把发布门禁闭环打通（已完成）。
5. 模块完成后执行 `stage-closure-execute`，固化阶段结论与下轮入口。
6. 环境窗口到位后单独推进 `real-env-pass-window-execute-on-env`，不与本地模块口径混写。

---

## 7. 本阶段明确不做

1. 不开放 `NPC Coach / Room QA` 到用户正式流程（继续 `advisory_only`）。
2. 不引入长期兼容层、旧字段 alias 并存、双写路径。
3. 不启动服务拆分（Judge/NPC/QA 微服务化继续延后）。
4. 不在当前阶段引入区块链/ZK/ZKML 的上链执行依赖（仅保持可扩展接口边界）。

---

## 8. 测试与验收基线

1. AI Judge 服务回归：`cd ai_judge_service && ../scripts/py -m pytest -q`
2. 关键主链回归：`cd ai_judge_service && ../scripts/py -m pytest -q tests/test_judge_mainline.py tests/test_phase_final_contract_models.py tests/test_app_factory.py tests/test_evidence_ledger.py`
3. 事实源回归：`cd ai_judge_service && ../scripts/py -m pytest -q tests/test_fact_repository.py tests/test_workflow_orchestrator.py`
4. 文档与计划门禁：
   - `bash scripts/quality/harness_docs_lint.sh`
   - `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle`
5. 本地收口基线（非 real-env pass）：
   - `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`
   - `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`

---

## 9. 风险与对策

1. 风险：工作区在途改动未冻结就叠加新模块，导致回归噪音扩散。  
   对策：P13 第一模块先做 `baseline-delta-freeze`，再进入新增功能。
2. 风险：shadow 结果误入官方裁决链，引入用户可见语义污染。  
   对策：强制 `shadow advisory-only`，仅写公平治理与发布门禁，不写 winner 主链。
3. 风险：公平运营读模型字段频繁变化，调用方难以稳定接入。  
   对策：先冻结 `overview/trends/top_risk_cases/gate_distribution` 契约，并补 route 测试。
4. 风险：real-env 长期不可用导致计划尾部停滞。  
   对策：维持 `local_reference_ready` 收口，并持续输出 blocker 字段，窗口到来后一次性冲刺。

---

## 10. 模块完成同步历史

### 模块完成同步历史

1. 2026-04-17：归档上一轮计划到 `docs/dev_plan/archive/20260417T043207Z-ai-judge-current-plan-archive.md`，并清空活动计划文档。
2. 2026-04-17：生成 `P13` 计划，主线切换为“Fairness Hardened 工程化收口 + Shadow Evaluation 启动 + real-env 窗口待执行”。
3. 2026-04-17：完成 `ai-judge-p13-baseline-delta-freeze`，`public-verify + opinion timeline/cards + evidence reliability guard` 相关改动通过目标回归与综合回归。
4. 2026-04-17：完成 `ai-judge-p13-fairness-shadow-eval-ledger-v1`，新增 `fairness_shadow_runs` 表、事实仓储、`/internal/judge/fairness/shadow-runs` 写读路由，并把 `shadowSummary`/`has_shadow_breach` 接入 `fairness/cases` 读模型。
5. 2026-04-17：修复 `m7_acceptance_gate` 负载门禁的 SQLite 脏库干扰（改为每次运行独立临时 DB 路径），全量 `pytest -q` 回归恢复通过。
6. 2026-04-17：完成 `ai-judge-p13-fairness-dashboard-export-v1`，新增 `/internal/judge/fairness/dashboard` 聚合接口（overview/trends/topRiskCases/gateDistribution），并新增 `scripts/harness/ai_judge_fairness_dashboard_export.sh` 与回归测试 `scripts/harness/tests/test_ai_judge_fairness_dashboard_export.sh`。
7. 2026-04-17：完成 `ai-judge-p13-policy-release-gate-shadow-link`，`publish/activate` 公平门禁升级为 benchmark + shadow 双判定；新增 shadow breach 阻断与 override 审计测试，回归 `pytest -q` 全量通过。

---

## 11. 本轮启动检查清单

1. 先按 `ai-judge-p13-baseline-delta-freeze` 冻结在途改动，不在脏基线上继续叠功能。
2. 涉及 API/DTO/错误码/状态字段变更时，同轮检查跨层调用方（至少 `chat_server` + 相关契约测试）。
3. `shadow` 相关改动必须显式标注“非官方裁决链”。
4. 涉及 real-env 结论时，严格区分 `local_reference_ready` 与 `pass`。
5. 每次模块结束后，更新本计划矩阵状态与同步历史。

---

## 12. 架构方案第13章一致性校验（计划生成前置）

1. **角色一致性**：P13 不新增绕过角色，继续沿用 8 Agent 主链；新增 shadow 仅作为公平治理侧链，不替代 Judge Panel / Arbiter。
2. **数据一致性**：本阶段新增能力仍围绕六对象扩展；shadow 结果进入 fairness/read-model 与发布门禁，不引入平行 winner 事实源。
3. **门禁一致性**：`Fairness Sentinel` 仍在终判前；新增 shadow 漂移只会强化发布门禁，不允许绕过审计。
4. **边界一致性**：`NPC/Room QA` 继续 `advisory_only`，本阶段不写官方裁决链。
5. **跨层一致性**：若本阶段新增 fairness/dashboard 或 release gate 契约字段，将同轮同步调用方与测试，不保留长期 alias 双轨。
6. **收口一致性**：real-env 继续区分 `local_reference_ready` 与 `pass`；本计划只把 `pass` 定义为窗口执行后的结果，不提前宣称通过。

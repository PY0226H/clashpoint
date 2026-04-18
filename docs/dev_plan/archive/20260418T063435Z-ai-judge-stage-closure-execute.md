# 当前开发计划

关联 slot：`default`  
更新时间：2026-04-17  
当前主线：`AI_judge_service P14（Phase2 最终就绪 + Adaptive Judge Platform 启动）`  
当前状态：执行中（P14-M1/M2/M3/M4/M5 已完成；本地环境继续推进，real-env 仍为窗口阻塞）

---

## 1. 计划定位

1. 本计划承接 `P13` 收口结果，目标是在不引入兼容层的前提下完成 `Phase2 -> Phase3` 过渡。
2. 先完成本地可执行的“工程化与治理闭环”，再把真实环境相关事项保持 `on-env` 单独冲刺。
3. 本轮继续执行硬切原则：不保留旧链路 alias、双写路径、灰度分流。
4. 本计划生成必须满足架构方案第13章一致性清单（角色/数据/门禁/边界/跨层/收口）。

---

## 2. 当前代码状态快照（P14 起点）

以下能力已在 `P13` 收口完成后作为基线保留：

1. `trace / replay / review / failed callback` 主链稳定可用，且可追踪落库。
2. 六对象主链已形成：`case_dossier / claim_graph / evidence_bundle / verdict_ledger / fairness_report / opinion_pack`。
3. 公平治理主链已具备：`benchmark-runs + shadow-runs + fairness/cases + fairness/dashboard`。
4. policy release gate 已接入 shadow 判定，支持阻断与 override 审计追踪。
5. 可验证信任层 `phaseA/phaseB` 主链接口已可用，`public-verify` 聚合读接口已在回归主线。
6. `NPC Coach / Room QA` 保持 `advisory_only` 壳层，不写官方裁决链。
7. `P13` 阶段收口已执行：活动计划已归档，`completed/todo` 已同步。
8. registry 三元治理已新增统一治理视图：`/internal/judge/registries/governance/overview`，可聚合 dependency health、reverse usage、release state 与 audit/rollback 摘要。
9. panel runtime profile 已完成 Adaptive bootstrap 骨架：支持 `strategySlot/domainSlot/runtimeStage/adaptiveEnabled/candidateModels/strategyMetadata`，并在 `/internal/judge/panels/runtime/profiles` 提供对应筛选与聚合。
10. Ops 统一读模型聚合已落地：`/internal/judge/ops/read-model/pack` 联合输出 fairness dashboard + registry governance + trust overview，并提供 `scripts/harness/ai_judge_ops_read_model_export.sh` 导出脚本与测试。

当前主要缺口（进入 P14）：

1. 真实环境 `pass` 仍未完成，仅到 `local_reference_ready`。
2. `Prompt/Tool/Policy` 三元治理已具备统一运营视图，但联动阻断策略仍可继续细化。
3. Adaptive 平台能力已进入首版可执行骨架，但自动校准与多模型联动策略仍待后续模块完善。
4. Ops 统一读模型已完成首版聚合导出，但真实环境看板接入与阈值封板仍待 `on-env` 校准。

---

## 3. P14 总目标（下一阶段）

1. 完成 `Phase2` 的“发布治理 + 运营读模型 + 本地校准”最终就绪。
2. 启动 `Phase3` 的最小可执行骨架：不改变官方裁决语义，先搭建 Adaptive 能力入口。
3. 强化 registry 三元治理，确保策略变更具备可审计、可回滚、可复盘的闭环。
4. 持续保持 `NPC/Room QA advisory-only` 边界，不让互动型 Agent 污染官方裁决链。
5. 对真实环境事项严格保留 `on-env` 口径，不提前宣称 `pass`。

---

## 4. P14 模块执行矩阵

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 本轮目标 | DoD（完成定义） | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| `ai-judge-next-iteration-planning` | P0 | 已完成（2026-04-17） | 基于 P13 收口状态重建下一阶段计划入口 | 当前计划归档、重置与一致性校验通过，P14 活动计划就位 | `bash scripts/harness/ai_judge_stage_closure_execute.sh --root /Users/panyihang/Documents/EchoIsle` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p14-baseline-freeze` | P0 | 已完成（2026-04-17） | 冻结 P13 收口后代码基线，确保下一阶段在干净回归面上推进 | `pytest/ruff/doc gates` 全绿，形成 P14 起点证据 | `cd ai_judge_service && ../scripts/py -m pytest -q` + `cd ai_judge_service && ../scripts/py -m ruff check app tests` + `bash scripts/quality/harness_docs_lint.sh` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p14-registry-triple-governance-v2` | P1 | 已完成（2026-04-17） | 强化 policy/prompt/tool 三元发布治理（联动检查、审计视图、回滚可追踪） | 新增 `governance/overview` 聚合视图；registry 发布/激活/回滚链可在统一视图中追踪 dependency/usage/release/audit 摘要 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "registry"` + `cd ai_judge_service && ../scripts/py -m pytest -q` |
| `ai-judge-p14-adaptive-panel-runtime-bootstrap` | P1 | 已完成（2026-04-17） | 在不改变主裁决合同前提下，落地 panel runtime 可扩展骨架（策略槽位/领域槽位） | panel runtime profile 已支持策略槽位/领域槽位/运行阶段/候选模型/扩展元数据，并在 ops 读模型可筛选聚合；winner 主语义不变 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_judge_mainline.py tests/test_app_factory.py -k "panel_runtime or fairness"` + `cd ai_judge_service && ../scripts/py -m pytest -q` |
| `ai-judge-p14-ops-read-model-pack-v1` | P1 | 已完成（2026-04-17） | 打通 fairness/registry/trust 的统一导出视图，面向第三方看板接入 | 新增 `/internal/judge/ops/read-model/pack`；新增 `ai_judge_ops_read_model_export.sh` 与脚本回归，输出稳定 JSON/MD/ENV 证据 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "ops or fairness_dashboard or registries"` + `bash scripts/harness/tests/test_ai_judge_fairness_dashboard_export.sh` + `bash scripts/harness/tests/test_ai_judge_ops_read_model_export.sh` + `cd ai_judge_service && ../scripts/py -m pytest -q` |
| `ai-judge-p14-fairness-calibration-pack-local` | P1 | 已完成（2026-04-17） | 基于本地样本形成 calibration pack（不宣称 real-env 结论） | 新增 `/internal/judge/fairness/calibration-pack` 输出阈值建议、漂移摘要、风险项和 on-env 输入模板；新增本地导出脚本 `ai_judge_fairness_calibration_pack_local.sh` 与脚本测试 | `cd ai_judge_service && ../scripts/py -m ruff check app tests` + `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_m7_acceptance_gate.py tests/test_app_factory.py -k "fairness or benchmark or shadow or calibration"` + `bash scripts/harness/tests/test_ai_judge_fairness_calibration_pack_local.sh` + `cd ai_judge_service && ../scripts/py -m pytest -q` |
| `ai-judge-p14-stage-closure-execute` | P2 | 待执行 | 本阶段完成后执行标准收口（主体完成/环境阻塞/下轮入口） | 计划归档、`completed/todo` 分离、下一轮入口清晰 | `bash scripts/harness/ai_judge_stage_closure_execute.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p14-real-env-pass-window-execute-on-env` | P0（环境阻塞） | 阻塞（待真实环境窗口） | 真实环境窗口到来后完成 `pass` 冲刺 | `AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=pass` 且 `REAL_PASS_READY=true`，形成真实环境证据闭环 | `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle` |

---

## 5. 延后事项（不阻塞当前阶段）

1. 真实环境样本驱动的 fairness/runtime 阈值最终冻结（`on-env`）。
2. 真实压测数据驱动的成本/容量治理与长期漂移观测（`on-env`）。
3. `NPC Coach / Room QA` 产品需求未冻结前，不推进正式功能实装。
4. `multi-model panel / policy auto-calibration / domain judge families` 仅先做骨架，不在本阶段直接切主裁决语义。

### 下一开发模块建议

1. `ai-judge-p14-stage-closure-execute`
2. `ai-judge-p14-real-env-pass-window-execute-on-env`

---

## 6. 执行顺序与依赖

1. 先执行 `baseline-freeze`，避免在漂移基线上叠加新模块（已完成）。
2. 再推进 `registry-triple-governance-v2`，先把发布治理主链做稳（已完成）。
3. 然后进入 `adaptive-panel-runtime-bootstrap`，确保扩展能力不破坏官方裁决语义（已完成）。
4. 基于稳定治理与 runtime 能力，推进 `ops-read-model-pack-v1`（已完成）。
5. 再做 `fairness-calibration-pack-local`，输出本地校准证据与 on-env 输入模板（已完成）。
6. 模块完成后执行 `stage-closure-execute`，固化阶段结论。
7. 环境窗口就绪时单独执行 `real-env-pass-window-execute-on-env`。

---

## 7. 本阶段明确不做

1. 不把 `NPC/Room QA` 接入官方裁决写链。
2. 不保留长期兼容层、双写链路、旧新字段并存。
3. 不提前拆 Judge/NPC/QA 为独立微服务。
4. 不在当前阶段引入链上执行依赖（仅保留协议化扩展边界）。

---

## 8. 测试与验收基线

1. 全量回归：`cd ai_judge_service && ../scripts/py -m pytest -q`
2. 主链回归：`cd ai_judge_service && ../scripts/py -m pytest -q tests/test_judge_mainline.py tests/test_phase_final_contract_models.py tests/test_app_factory.py tests/test_evidence_ledger.py`
3. 事实源回归：`cd ai_judge_service && ../scripts/py -m pytest -q tests/test_fact_repository.py tests/test_workflow_orchestrator.py`
4. 质量门禁：
   - `cd ai_judge_service && ../scripts/py -m ruff check app tests`
   - `bash scripts/quality/harness_docs_lint.sh`
   - `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle`
5. 本地收口基线（非 real-env pass）：
   - `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`
   - `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`

---

## 9. 风险与对策

1. 风险：Adaptive 能力开发反向污染官方裁决链。  
   对策：保持 `advisory-only` 边界，所有新策略先走 runtime profile，不直接改 winner 主语义。
2. 风险：registry 三元治理改动引发跨层契约漂移。  
   对策：API/DTO 变更同轮同步 `chat_server` 调用方与测试，不保留长期 alias。
3. 风险：过度依赖本地样本导致阈值结论失真。  
   对策：本地只产出建议与风险，不声明 `pass`，真实结论统一留在 on-env 窗口。
4. 风险：阶段尾部文档收口遗漏导致后续计划偏航。  
   对策：阶段末固定执行 `stage-closure + consistency gate + docs lint` 三件套。

---

## 10. 模块完成同步历史

### 模块完成同步历史

1. 2026-04-17：执行 `ai-judge-p13-stage-closure-execute`，归档活动计划并同步 `completed/todo`。
2. 2026-04-17：修复阶段收口模板缺少“架构一致性校验段”的问题，恢复 `plan_consistency_gate` 可通过状态。
3. 2026-04-17：归档重置后的活动计划到 `docs/dev_plan/archive/20260418T053103Z-ai-judge-current-plan-archive.md`。
4. 2026-04-17：生成本计划（P14），主线切换为“Phase2 最终就绪 + Adaptive Judge Platform 启动”。
5. 2026-04-17：完成 `ai-judge-p14-baseline-freeze`，本地全量 `pytest -q` 与 `ruff check`、`harness_docs_lint`、`plan_consistency_gate` 全部通过，P14 基线冻结完成。
6. 2026-04-17：完成 `ai-judge-p14-registry-triple-governance-v2`，新增 `/internal/judge/registries/governance/overview` 聚合治理视图，并补齐路由与治理回归测试，`pytest -q` 全量通过。
7. 2026-04-17：完成 `ai-judge-p14-adaptive-panel-runtime-bootstrap`，panel runtime profile 增加 `strategySlot/domainSlot/runtimeStage/adaptiveEnabled/candidateModels/strategyMetadata` 并接入 ops 聚合筛选；`pytest -q` 与 `ruff check` 全量通过。
8. 2026-04-17：完成 `ai-judge-p14-ops-read-model-pack-v1`，新增 `/internal/judge/ops/read-model/pack` 聚合 fairness/registry/trust 读模型，并新增 `ai_judge_ops_read_model_export.sh` 导出脚本与脚本测试；`pytest -q`、`ruff check`、导出脚本测试全绿。
9. 2026-04-17：完成 `ai-judge-p14-fairness-calibration-pack-local`，新增 `/internal/judge/fairness/calibration-pack` 本地校准读接口（`overview/thresholdSuggestions/driftSummary/riskItems/onEnvInputTemplate`），并新增 `ai_judge_fairness_calibration_pack_local.sh` 及脚本测试；`ruff + targeted pytest + full pytest` 全绿。

---

## 11. 本轮启动检查清单

1. 开发前先跑 `pre-module-prd-goal-guard` 与 `python-venv-guard`。
2. 涉及 API/错误码/状态字段变更时，同轮检查跨层调用方与契约测试。
3. 与 `real-env` 相关结论必须显式标记 `on-env`，禁止混写本地结论。
4. 新增策略必须证明“不改变官方 winner 主语义”或给出审计化 override 方案。
5. 每个模块完成后更新本计划矩阵与同步历史。

---

## 12. 架构方案第13章一致性校验（计划生成前置）

1. **角色一致性**：8 Agent 职责保持完整，不新增绕过 Sentinel/Arbiter 的捷径链路。
2. **数据一致性**：六对象主链仍是唯一裁决事实源，不引入平行 winner 写链。
3. **门禁一致性**：Fairness gate 保持终判前置，override 必须可审计可追溯。
4. **边界一致性**：`NPC/Room QA` 继续 `advisory_only`，不写官方裁决链。
5. **跨层一致性**：契约变更同轮同步调用方与测试，不保留长期双轨 alias。
6. **收口一致性**：real-env 继续区分 `local_reference_ready` 与 `pass`，不混淆口径。

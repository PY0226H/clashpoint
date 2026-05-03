# 当前开发计划

关联 slot：`default`  
更新时间：2026-04-18  
当前主线：`AI_judge_service P15（Phase3 Adaptive Judge Platform 深化 + 企业级运营化闭环）`  
当前状态：执行中（`ai-judge-next-iteration-planning`、`P15-M1`~`P15-M4` 已完成；P15-M5~M6 待执行；real-env 仍为窗口阻塞）

---

## 1. 计划定位

1. 本计划承接 `P14` 阶段收口结果，进入企业方案 `Phase3: Adaptive Judge Platform` 的主线执行。
2. 本轮继续坚持“未上线产品硬切原则”：不保留长期兼容层、双写链路、灰度旧路径。
3. 先完成本地可执行的 adaptive 与运营闭环增强，再将真实环境结论严格保留为 `on-env` 专项冲刺。
4. 计划生成必须同时满足：
   - 企业方案（`AI_Judge_Service-企业级Agent服务设计方案-2026-04-13.md`）
   - 架构方案（`AI_Judge_Service-架构与技术栈决策方案-2026-04-13.md`）
   - 当前收口状态（`completed/todo` + 最新 stage closure 归档）

---

## 2. 当前代码状态快照（P15 起点）

截至 `2026-04-18`，以下主链能力已确认可用：

1. 裁判主链稳定：`phase/final dispatch + trace + replay + review + failed callback` 全链可追踪。
2. 六对象主链已成型：`case_dossier / claim_graph / evidence_bundle / verdict_ledger / fairness_report / opinion_pack`。
3. 公平治理主链可用：`benchmark-runs + shadow-runs + fairness/cases + fairness/dashboard + fairness/calibration-pack`。
4. registry 三元治理主链可用：`policy/prompt/tool` 发布、激活、回滚、审计、依赖健康与治理总览。
5. adaptive runtime 骨架可用：panel runtime profile 已支持 `strategySlot/domainSlot/runtimeStage/adaptiveEnabled/candidateModels/strategyMetadata`。
6. ops 聚合读模型 v1 可用：`/internal/judge/ops/read-model/pack` + 导出脚本与脚本回归已落地。
7. `P14` 已执行阶段收口：
   - 归档：`docs/dev_plan/archive/20260418T063435Z-ai-judge-stage-closure-execute.md`
   - 当前计划模板已重置
   - `completed.md / todo.md` 已同步

当前主要缺口（进入 P15）：

1. `policy auto-calibration` 仍停留在“校准证据导出”，尚未形成“策略建议 -> 发布治理联动”的闭环。
2. `multi-model panel` 仍是 runtime metadata 骨架，缺少可运营的 readiness/simulation 视图。
3. `domain-specific judge families` 尚未完成治理级路由与策略封板。
4. `ops read model` 仍需从 v1 聚合升级到可直接驱动第三方看板接入的 v2 结构。
5. `real-env pass` 仍未完成，属于环境窗口阻塞项。

---

## 3. P15 总目标（下一阶段）

1. 对齐企业方案 `Phase3`：把 adaptive 能力从“骨架”推进到“可治理、可验证、可运营”。
2. 在不改变官方 winner 主语义的前提下，补齐：
   - policy auto-calibration advisory
   - multi-model panel readiness
   - domain judge family 治理入口
3. 将 `fairness + registry + trust + adaptive` 聚合成更稳定的 ops/read-model v2 输出，支撑后续第三方看板接入。
4. 继续保持边界：`NPC Coach / Room QA` 仅 advisory-only，不进入官方裁决写链。
5. 对 `real-env` 结论保持严格口径，不把本地结果写成 pass。

---

## 4. P15 模块执行矩阵

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 本轮目标 | DoD（完成定义） | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| `ai-judge-next-iteration-planning` | P0 | 已完成（2026-04-18） | 基于收口状态 + 企业方案 + 架构方案生成下一阶段计划 | 当前计划已归档并重写为 P15，矩阵/顺序/门禁口径完整 | `bash scripts/quality/harness_docs_lint.sh` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p15-adaptive-policy-calibration-advisor-v1` | P1 | 已完成（2026-04-17） | 把 calibration 证据升级为 policy 校准建议能力（advisory） | 新增 policy calibration advisor 读接口（建议阈值 + 风险解释 + 建议动作），并与 registry release gate 形成“建议可见、执行受控”闭环，不自动改写 active policy | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "calibration or registry or fairness"` + `cd ai_judge_service && ../scripts/py -m pytest -q` |
| `ai-judge-p15-panel-multi-model-readiness-v1` | P1 | 已完成（2026-04-17） | 提供 multi-model panel readiness/simulation 运营视图 | 新增或增强 panel runtime read model（候选模型、策略槽、分歧度、建议切换条件），保持 winner 主语义不变 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_judge_mainline.py tests/test_app_factory.py -k "panel_runtime or fairness"` |
| `ai-judge-p15-domain-judge-family-bootstrap-v1` | P1 | 已完成（2026-04-17） | 建立 domain judge family 的治理入口 | 在 policy/profile 层补齐 domain family 路由与合法性校验（例如 `general/tft/...`），并纳入 registry governance 可观测面 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "registry or policy or panel"` |
| `ai-judge-p15-ops-read-model-pack-v2` | P1 | 已完成（2026-04-17） | 将 ops 聚合从 v1 升级为 v2（更适配看板接入） | `/internal/judge/ops/read-model/pack` 增强输出 adaptive + calibration 摘要；新增/升级导出脚本与脚本测试，保证 JSON/MD/ENV 证据稳定 | `bash scripts/harness/tests/test_ai_judge_ops_read_model_export.sh` + `bash scripts/harness/tests/test_ai_judge_fairness_calibration_pack_local.sh` + `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "ops or fairness or calibration"` |
| `ai-judge-p15-enterprise-alignment-mapping-refresh` | P1 | 待执行 | 更新企业方案章节完成度映射，避免方案与实现断层 | 更新 `AI_Judge_Service-企业级Agent方案-章节完成度映射-2026-04-13.md`，明确 P15 新进展与剩余缺口 | `bash scripts/quality/harness_docs_lint.sh` |
| `ai-judge-p15-stage-closure-execute` | P2 | 待执行 | 本阶段完成后执行标准收口 | 计划归档、`completed/todo` 分离、下一轮入口清晰 | `bash scripts/harness/ai_judge_stage_closure_execute.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p15-real-env-pass-window-execute-on-env` | P0（环境阻塞） | 阻塞（待真实环境窗口） | 真实环境窗口到来后完成 pass 冲刺 | `AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=pass` 且 `REAL_PASS_READY=true`，形成真实环境证据闭环 | `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle` |

---

## 5. 延后事项（不阻塞当前阶段）

1. 真实环境样本驱动的阈值冻结、容量规划、成本路由优化（`on-env`）。
2. `Temporal` / 向量后端替换等基础设施对比评估（需要真实运维样本）。
3. `NPC Coach / Room QA` 的正式产品实现（等待你冻结模块 PRD）。
4. 链上协议化扩展（ZK/ZKML/链上锚定）保持“接口预留、实现后置”。

### 下一开发模块建议

1. `ai-judge-p15-adaptive-policy-calibration-advisor-v1`
2. `ai-judge-p15-panel-multi-model-readiness-v1`
3. `ai-judge-p15-domain-judge-family-bootstrap-v1`
4. `ai-judge-p15-ops-read-model-pack-v2`

---

## 6. 执行顺序与依赖

1. 先做 `adaptive-policy-calibration-advisor-v1`，把 calibration 从“报表”推进到“治理建议”。
2. 再做 `panel-multi-model-readiness-v1`，形成 multi-model 的可观测 readiness 面。
3. 然后做 `domain-judge-family-bootstrap-v1`，把 domain 策略路由纳入治理主链。
4. 基于前 3 项成果，升级 `ops-read-model-pack-v2`，统一导出运营证据。
5. 完成后更新 `企业级Agent方案-章节完成度映射`，确保方案-架构-代码三者一致。
6. 执行 `p15-stage-closure-execute` 收口。
7. 环境窗口就绪时单独执行 `p15-real-env-pass-window-execute-on-env`。

---

## 7. 本阶段明确不做

1. 不把 `NPC Coach / Room QA` 接入官方裁决写链。
2. 不做兼容双轨（alias 字段、旧新双写、灰度并行路径）。
3. 不提前拆分 Judge/NPC/QA 为独立微服务。
4. 不把本地校准结论写成 real-env pass。
5. 不在未冻结产品需求前推进 NPC/Room QA 业务细节实现。

---

## 8. 测试与验收基线

1. 全量回归：`cd ai_judge_service && ../scripts/py -m pytest -q`
2. 主链回归：`cd ai_judge_service && ../scripts/py -m pytest -q tests/test_judge_mainline.py tests/test_phase_final_contract_models.py tests/test_app_factory.py tests/test_evidence_ledger.py`
3. fairness + adaptive 回归：`cd ai_judge_service && ../scripts/py -m pytest -q tests/test_m7_acceptance_gate.py tests/test_app_factory.py -k "fairness or benchmark or shadow or calibration or panel"`
4. 质量门禁：
   - `cd ai_judge_service && ../scripts/py -m ruff check app tests`
   - `bash scripts/quality/harness_docs_lint.sh`
   - `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle`
5. 本地收口基线（非 real-env pass）：
   - `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`
   - `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`

---

## 9. 风险与对策

1. 风险：Adaptive 逻辑侵入官方裁决语义。  
   对策：所有 adaptive 输出先走 advisory/read-model，不直接改 winner 主语义。
2. 风险：policy calibration 建议被误当“自动生效”。  
   对策：显式区分 `advisory` 与 `active policy`，发布动作必须走 registry 审计链。
3. 风险：domain family 引入跨层契约漂移。  
   对策：API/DTO 变更同轮同步调用方与测试，不保留长期 alias。
4. 风险：本地样本过拟合导致错误阈值方向。  
   对策：本地只产建议与风险提示，最终结论仅在 real-env 窗口冻结。
5. 风险：计划文档与实现节奏再次断层。  
   对策：每个模块结束后同步更新当前计划与章节完成度映射。

---

## 10. 模块完成同步历史

### 模块完成同步历史

1. 2026-04-18：完成 `ai-judge-p14-stage-closure-execute`，归档 `P14` 活动计划并重置当前计划模板。
2. 2026-04-18：归档当前计划模板到 `docs/dev_plan/archive/20260418T064409Z-ai-judge-current-plan-pre-p15.md`。
3. 2026-04-18：完成 `ai-judge-next-iteration-planning`，生成并写入本 `P15` 完整开发计划。
4. 2026-04-17：完成 `ai-judge-p15-adaptive-policy-calibration-advisor-v1`，新增 `/internal/judge/fairness/policy-calibration-advisor`（advisory-only），并补齐对应测试与全量回归。
5. 2026-04-17：完成 `ai-judge-p15-panel-multi-model-readiness-v1`，新增 `/internal/judge/panels/runtime/readiness`，落地 readiness/simulation 读模型（advisory-only）并补齐测试与全量回归。
6. 2026-04-17：完成 `ai-judge-p15-domain-judge-family-bootstrap-v1`，新增 `domain-families` 治理读接口，补齐 policy domain family 合法性校验并并入 governance overview。
7. 2026-04-17：完成 `ai-judge-p15-ops-read-model-pack-v2`，升级 ops pack 聚合（fairness calibration advisor + panel readiness + adaptive summary）并同步导出脚本与脚本回归。

---

## 11. 本轮启动检查清单

1. 开发前先跑 `pre-module-prd-goal-guard` 与 `python-venv-guard`。
2. 涉及 API/错误码/状态字段变更时，同轮检查跨层调用方与契约测试。
3. 与 `real-env` 相关结论必须显式标记 `on-env`，禁止混写本地结论。
4. 新增 adaptive 策略必须证明“不改变官方 winner 主语义”或给出审计化 override 方案。
5. 每个模块完成后更新本计划矩阵与同步历史。

---

## 12. 架构方案第13章一致性校验（计划生成前置）

1. **角色一致性**：8 Agent 职责保持完整，不新增绕过 Sentinel/Arbiter 的捷径链路。
2. **数据一致性**：六对象主链仍是唯一裁决事实源，不引入平行 winner 写链。
3. **门禁一致性**：Fairness gate 保持终判前置，override 必须可审计可追溯。
4. **边界一致性**：`NPC/Room QA` 继续 `advisory_only`，不写官方裁决链。
5. **跨层一致性**：契约变更同轮同步调用方与测试，不保留长期双轨 alias。
6. **收口一致性**：real-env 继续区分 `local_reference_ready` 与 `pass`，不混淆口径。

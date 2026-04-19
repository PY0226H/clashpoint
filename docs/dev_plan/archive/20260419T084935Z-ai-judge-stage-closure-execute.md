# 当前开发计划

关联 slot：`default`  
更新时间：2026-04-19  
当前主线：`AI_judge_service P19（结构收敛 + 契约冻结 + 本地证据稳态化）`  
当前状态：执行中（已完成 `ai-judge-p19-enterprise-consistency-refresh-v2`，下一步 `ai-judge-p19-stage-closure-execute`）

---

## 1. 计划定位

1. 本计划承接 `P18` 阶段收口归档：`/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260419T083347Z-ai-judge-stage-closure-execute.md`。
2. 当前明确前提：你没有真实开发环境，本轮仍按 `local_reference` 路径推进，不宣称 `real-env pass`。
3. 本轮核心目标不是扩新功能，而是把已完成主链进一步“可维护、可验证、可收口”：
   - 收敛阶段工件噪音；
   - 冻结 `ops/read-model/pack v5` 契约；
   - 继续拆分 `app_factory` 热点；
   - 固化本地回归证据闭环。
4. 继续执行预发布硬切原则：不保留长期兼容层、灰度双轨、旧新并行语义。

---

## 2. 当前代码状态快照（P19 起点）

截至 2026-04-19，`ai_judge_service` 当前状态：

1. P18 主体已完成并收口：
   - `prompt/tool governance`；
   - `evidence claim ops queue`；
   - `courtroom drilldown bundle`；
   - `ops/read-model/pack v5`；
   - `app_factory` 首轮结构拆分；
   - 章节完成度映射刷新；
   - 本地收口演练（`local_reference_ready`）。
2. 裁决主链保持稳定：`phase/final dispatch + trace + replay + review + failed callback + trust challenge`。
3. 已新增结构模块：`app/applications/ops_read_model_pack.py`，但 `app_factory` 仍是高热点文件。
4. 本轮可见风险：
   - harness 运行会产生较多时间戳工件，影响工作区可读性与回合噪音；
   - `ops/read-model/pack v5` 目前主要靠集成断言，缺少更显式的契约冻结层；
   - `real-env pass` 仍是环境阻塞项，短期不能闭合。

---

## 3. P19 总目标

1. 对齐企业方案与架构方案中的“可运维 + 可持续演进”目标，优先做工程收敛与治理固化。
2. 把 P18 的新增能力从“已实现”推进到“回归稳定 + 契约稳定 + 工件稳定”。
3. 在不依赖真实环境的条件下，尽可能提高下一轮迭代效率，降低上下文与噪音成本。

---

## 4. P19 模块执行矩阵

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 本轮目标 | DoD（完成定义） | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| `ai-judge-next-iteration-planning` | P0 | 已完成（2026-04-19） | 阶段收口后生成新一轮完整计划 | 当前计划切换为 P19，明确无真实环境前提、模块矩阵与阻塞边界 | `bash scripts/quality/harness_docs_lint.sh` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p19-stage-artifact-governance-v1` | P1 | 已完成（2026-04-19） | 收敛阶段工件噪音 | 新增 `ai_judge_artifact_prune.sh`（按模块保留 N 份、默认 dry-run）与回归测试，兼容本机 Bash 3.2，能稳定清理时间戳工件噪音 | `bash scripts/harness/tests/test_ai_judge_artifact_prune.sh` |
| `ai-judge-p19-ops-pack-contract-freeze-v1` | P1 | 已完成（2026-04-19） | 冻结 `ops/read-model/pack v5` 契约 | 新增 `validate_ops_read_model_pack_v5_contract`，覆盖主字段/聚合段/关键计数校验，并在 `/internal/judge/ops/read-model/pack` 出口强制校验；补充 route + unit 冻结测试 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py -k "ops and pack and v5"` |
| `ai-judge-p19-app-factory-structure-split-v2` | P1 | 已完成（2026-04-19） | 继续拆分 `app_factory` 热点 | 将 `ops/read-model/pack` 最终 payload 组装与契约校验下沉到 `applications/ops_read_model_pack.py`，路由层保留编排职责；补齐单测并保持行为不变 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py tests/test_ops_read_model_pack.py` |
| `ai-judge-p19-local-regression-bundle-v1` | P2 | 已完成（2026-04-19） | 固化本地回归包 | 完成 `ruff + pytest + runtime_ops_pack(local_reference)` 三段回归并产出最新证据工件，口径保持 `local_reference_ready` | `cd ai_judge_service && ../scripts/py -m ruff check app tests` + `cd ai_judge_service && ../scripts/py -m pytest -q` + `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference` |
| `ai-judge-p19-enterprise-consistency-refresh-v2` | P2 | 已完成（2026-04-19） | 同步文档一致性 | 已更新章节完成度映射到 P19 当前状态（M1~M4 完成、real-env 阻塞不变），并同步当前计划状态 | `bash scripts/quality/harness_docs_lint.sh` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p19-real-env-pass-window-execute-on-env` | P0（环境阻塞） | 阻塞（待真实环境窗口） | 真实环境窗口 pass 冲刺 | `AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=pass` 且 `REAL_PASS_READY=true`，形成 on-env 证据归档 | `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p19-stage-closure-execute` | P2 | 待执行 | 执行阶段收口 | 归档当前活动计划，`completed/todo` 同步，计划文档重置到下一轮入口 | `bash scripts/harness/ai_judge_stage_closure_execute.sh --root /Users/panyihang/Documents/EchoIsle` |

### 下一开发模块建议

1. `ai-judge-p19-stage-closure-execute`

---

## 5. 延后事项（不阻塞 P19）

1. `real-env pass` 相关能力（严格 on-env）。
2. `NPC Coach / Room QA` 正式业务策略与主链接入（等待你冻结 PRD）。
3. 协议化扩展（链上锚定 / ZK / ZKML）继续保持后置。

---

## 6. 执行顺序与依赖

1. 先做 `stage-artifact-governance-v1`，降低每轮噪音与证据维护成本。
2. 再做 `ops-pack-contract-freeze-v1`，把 v5 字段契约固定。
3. 然后做 `app-factory-structure-split-v2`，继续降低结构复杂度。
4. 完成本地回归包与企业一致性刷新。
5. 执行阶段收口；真实环境窗口就绪后单独推进 on-env pass。

---

## 7. 本阶段明确不做

1. 不推进 `NPC Coach / Room QA` 正式功能。
2. 不为未上线能力保留长期兼容层（alias/双写/灰度并行）。
3. 不把 `local_reference_ready` 描述成 `pass`。

---

## 8. 测试与验收基线

1. `bash skills/python-venv-guard/scripts/assert_venv.sh --project /Users/panyihang/Documents/EchoIsle/ai_judge_service --venv /Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv`
2. `cd ai_judge_service && ../scripts/py -m ruff check app tests`
3. `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_app_factory.py tests/test_ops_read_model_pack.py`
4. `bash scripts/harness/tests/test_ai_judge_ops_read_model_export.sh`
5. `bash scripts/harness/tests/test_ai_judge_artifact_prune.sh`
6. `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`
7. `bash scripts/quality/harness_docs_lint.sh`
8. `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle`

---

## 9. 风险与对策

1. 风险：工件持续膨胀导致开发噪音与审阅成本上升。  
   对策：P19-M1 优先治理工件口径与归档策略。
2. 风险：`ops pack v5` 后续迭代出现字段漂移。  
   对策：P19-M2 增加契约冻结断言，避免隐式破坏。
3. 风险：`app_factory` 再次堆叠导致维护成本反弹。  
   对策：P19-M3 持续拆分，优先抽离纯组装逻辑与可测函数。
4. 风险：无真实环境导致结论被误读。  
   对策：保持 `local_reference_ready` 与 `pass` 双层口径，文档显式标注。

---

## 10. 模块完成同步历史

### 模块完成同步历史

1. 2026-04-19：完成 `ai-judge-next-iteration-planning`，阶段收口后生成 P19 完整开发计划，并锁定“无真实环境”执行前提。
2. 2026-04-19：完成 `ai-judge-p19-stage-artifact-governance-v1`，新增 `scripts/harness/ai_judge_artifact_prune.sh` 与 `scripts/harness/tests/test_ai_judge_artifact_prune.sh`，并完成 Bash 3.2 兼容修复与回归通过。
3. 2026-04-19：完成 `ai-judge-p19-ops-pack-contract-freeze-v1`，新增 `ops/read-model/pack v5` 契约校验器并接入路由返回主链，补齐 `tests/test_ops_read_model_pack.py` 与 `tests/test_app_factory.py` 的冻结断言回归。
4. 2026-04-19：完成 `ai-judge-p19-app-factory-structure-split-v2`，将 pack v5 payload 组装下沉至 `app/applications/ops_read_model_pack.py` 的独立 builder，`app_factory` 路由仅做数据编排与错误语义转换。
5. 2026-04-19：完成 `ai-judge-p19-local-regression-bundle-v1`，本地回归命令全绿：`ruff check app tests`、`pytest -q`、`ai_judge_runtime_ops_pack --allow-local-reference`，并生成最新 summary/evidence 工件。
6. 2026-04-19：完成 `ai-judge-p19-enterprise-consistency-refresh-v2`，章节完成度映射文档已切换到 P19 口径并同步最新模块完成状态与阻塞边界。

---

## 11. 本轮启动检查清单

1. 开发前运行 `pre-module-prd-goal-guard`（本轮已执行，`full`）。
2. 涉及 API/DTO/错误码变更时，同轮同步调用方、测试与文档。
3. 与真实环境有关结论必须标注 on-env，不在本地阶段宣称 `pass`。
4. 每完成一个模块都回写当前计划矩阵与同步历史。

---

## 12. 架构方案第13章一致性校验（计划生成前置）

1. **角色一致性**：继续沿用法庭式 8 Agent 边界，不新增绕过 Sentinel/Arbiter 的捷径路径。
2. **数据一致性**：六对象主链仍是唯一裁决事实源，不引入平行 winner 写链。
3. **门禁一致性**：fairness/review/registry/trust gate 不弱化；新增能力显式标注主链或 advisory-only。
4. **边界一致性**：`NPC/Room QA` 继续 `advisory_only`，不写官方裁决链。
5. **跨层一致性**：契约变更同轮同步调用方、测试与文档，不保留长期双轨 alias。
6. **收口一致性**：真实环境结论与本地参考结论分层表达，未获窗口前不宣称 `pass`。

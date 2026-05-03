# 当前开发计划

关联 slot：`default`  
更新时间：2026-04-19  
当前主线：`AI_judge_service P20（结构继续拆分 + 运行证据稳态 + real-env 窗口待命）`  
当前状态：执行中（已完成 `ai-judge-p20-enterprise-consistency-refresh-v3`，下一步 `ai-judge-p20-stage-closure-execute`）

---

## 1. 计划定位

1. 本计划承接 P19 阶段收口归档：`/Users/panyihang/Documents/EchoIsle/docs/dev_plan/archive/20260419T084935Z-ai-judge-stage-closure-execute.md`。
2. 当前明确前提：你仍没有真实开发环境，本轮继续按 `local_reference` 路径推进，不宣称 `real-env pass`。
3. P20 核心目标：
   - 继续降低 `app_factory` 热点复杂度；
   - 扩展 ops/read-model 关键契约冻结；
   - 固化本地回归证据与收口节奏；
   - 维持 real-env 窗口阻塞项可执行待命。
4. 继续执行预发布硬切原则：不保留长期兼容层、灰度双轨或旧新并行字段。

---

## 2. 当前代码状态快照（P20 起点）

截至 2026-04-19，`ai_judge_service` 当前状态：

1. P19 本地可执行模块已完成并收口：
   - `stage artifact governance`；
   - `ops pack v5 contract freeze`；
   - `app_factory structure split v2`；
   - `local regression bundle`；
   - `enterprise consistency refresh`。
2. 裁决主链保持稳定：`phase/final dispatch + trace + replay + review + failed callback + trust challenge`。
3. 当前可见缺口：
   - `app_factory.py` 仍是高热点文件；
   - 除 pack v5 外，部分 read-model 路由仍缺显式冻结契约层；
   - real-env pass 仍为环境阻塞项。

---

## 3. P20 总目标

1. 在不依赖真实环境的情况下继续提升可维护性与可验证性。
2. 把“局部拆分 + 局部冻结”推进到“可复用拆分模式 + 关键路由契约收敛”。
3. 保持文档、测试、脚本三层口径一致，为 real-env 窗口保留一次性收口通道。

---

## 4. P20 模块执行矩阵

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 本轮目标 | DoD（完成定义） | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| `ai-judge-next-iteration-planning` | P0 | 已完成（2026-04-19） | 阶段收口后生成 P20 计划 | 当前计划切换到 P20，明确“无真实环境”边界与模块矩阵 | `bash scripts/quality/harness_docs_lint.sh` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p20-app-factory-structure-split-v3` | P1 | 已完成（2026-04-19） | 继续拆分 `app_factory` 热点 | 将 pack 路由中的 trust/review 统计循环下沉到 `applications/ops_read_model_pack.py`，路由层进一步收敛为编排职责并补充单测 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_ops_read_model_pack.py tests/test_app_factory.py -k "ops_read_model_pack"` |
| `ai-judge-p20-ops-read-model-contract-freeze-v2` | P1 | 已完成（2026-04-19） | 扩展 read-model 契约冻结 | 在 pack v5 契约校验中新增 `courtroomReadModel` 行级字段与 count/errorCount 一致性断言，补充失败分支回归 | `cd ai_judge_service && ../scripts/py -m pytest -q tests/test_ops_read_model_pack.py tests/test_app_factory.py -k "ops_read_model_pack"` |
| `ai-judge-p20-local-regression-bundle-v2` | P2 | 已完成（2026-04-19） | 固化 P20 本地回归包 | 完成 `ruff + pytest + runtime_ops_pack(local_reference)` 三段回归并产出最新证据工件，口径保持 `local_reference_ready` | `cd ai_judge_service && ../scripts/py -m ruff check app tests` + `cd ai_judge_service && ../scripts/py -m pytest -q` + `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference` |
| `ai-judge-p20-enterprise-consistency-refresh-v3` | P2 | 已完成（2026-04-19） | 同步企业方案一致性 | 已同步章节完成度映射到 P20 当前状态（M1~M3 完成、real-env 阻塞不变），并回写当前计划状态 | `bash scripts/quality/harness_docs_lint.sh` + `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p20-real-env-pass-window-execute-on-env` | P0（环境阻塞） | 阻塞（待真实环境窗口） | 真实环境窗口 pass 冲刺 | `AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=pass` 且 `REAL_PASS_READY=true`，形成 on-env 证据归档 | `bash scripts/harness/ai_judge_real_env_window_closure.sh --root /Users/panyihang/Documents/EchoIsle` |
| `ai-judge-p20-stage-closure-execute` | P2 | 待执行 | 执行阶段收口 | 归档当前活动计划，`completed/todo` 同步，计划文档重置到下一轮入口 | `bash scripts/harness/ai_judge_stage_closure_execute.sh --root /Users/panyihang/Documents/EchoIsle` |

### 下一开发模块建议

1. `ai-judge-p20-stage-closure-execute`

---

## 5. 延后事项（不阻塞 P20）

1. `real-env pass` 相关能力（严格 on-env）。
2. `NPC Coach / Room QA` 正式业务策略与主链接入（等待你冻结 PRD）。
3. 协议化扩展（链上锚定 / ZK / ZKML）保持后置。

---

## 6. 执行顺序与依赖

1. 先做 `app-factory-structure-split-v3`，持续降低维护热区。
2. 再做 `ops-read-model-contract-freeze-v2`，扩大关键读面契约保护。
3. 完成本地回归包与企业一致性刷新。
4. 执行阶段收口；real-env 窗口就绪后单独推进 on-env pass。

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
4. `cd ai_judge_service && ../scripts/py -m pytest -q`
5. `bash scripts/harness/tests/test_ai_judge_artifact_prune.sh`
6. `bash scripts/harness/ai_judge_runtime_ops_pack.sh --root /Users/panyihang/Documents/EchoIsle --allow-local-reference`
7. `bash scripts/quality/harness_docs_lint.sh`
8. `bash scripts/harness/ai_judge_plan_consistency_gate.sh --root /Users/panyihang/Documents/EchoIsle`

---

## 9. 风险与对策

1. 风险：`app_factory` 再次集中膨胀。  
   对策：P20-M1 继续按热点分层抽离并保持行为回归。
2. 风险：read-model 输出随迭代发生字段漂移。  
   对策：P20-M2 扩展契约冻结断言，阻断隐式破坏。
3. 风险：本地证据与真实环境结论被混淆。  
   对策：继续保持 `local_reference_*` 与 `pass` 分层表达。

---

## 10. 模块完成同步历史

### 模块完成同步历史

1. 2026-04-19：完成 `ai-judge-stage-closure-execute`，P19 阶段活动计划已归档并重置。
2. 2026-04-19：完成 `ai-judge-next-iteration-planning`，当前计划切换为 P20 并锁定“无真实环境”执行边界。
3. 2026-04-19：完成 `ai-judge-p20-app-factory-structure-split-v3`，将 pack 路由统计逻辑进一步下沉到 applications，并完成对应单测回归。
4. 2026-04-19：完成 `ai-judge-p20-ops-read-model-contract-freeze-v2`，补齐 courtroom read model 行级契约冻结与 count 一致性校验，新增对应失败用例回归。
5. 2026-04-19：完成 `ai-judge-p20-local-regression-bundle-v2`，完成本地全量 `ruff + pytest + runtime_ops_pack` 回归并刷新最新 evidence/summary 工件。
6. 2026-04-19：完成 `ai-judge-p20-enterprise-consistency-refresh-v3`，章节完成度映射与当前计划口径已同步到 P20 最新完成度。

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

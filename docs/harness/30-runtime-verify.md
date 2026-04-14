# EchoIsle Runtime Verify

更新时间：2026-04-14
状态：P3-1 已完成，judge-ops 证据扫描已接入，其他 profile 细化待继续推进

---

## 1. 当前事实

EchoIsle 当前已经有统一的 `runtime verify` 入口：

- `scripts/harness/journey_verify.sh`

也就是说：

1. 已有 `journey_verify.sh`，可分发 `auth/lobby/room/judge-ops/release`
2. 但具体业务旅程验证仍在按 Phase 3 分阶段细化
3. 当前运行态证据仍主要来自既有测试、smoke、release、联调脚本
4. `judge-ops` profile 已支持扫描 `artifacts/harness/*ai-judge-*.summary.{json,md}` 作为模块运行态证据

---

## 2. 当前可用验证来源

### 2.1 模块开发默认验证

当前最主要的验证入口仍然是：

1. `post-module-test-guard`
2. 其内部的 test change guard
3. 其内部的 test gate

这意味着当前默认收口偏向：

1. 编译/测试/门禁通过
2. 必要时补测
3. 环境受限时明确说明阻塞

### 2.2 专项验证来源

当前专项运行态验证主要来自：

1. 前端 Playwright / smoke 脚本
2. release/preflight/supply-chain 脚本
3. 模块专属验证脚本
4. 手工联调与环境证据
5. `scripts/harness/ai_judge_evidence_gap_remediation.sh`（补齐历史模块缺失 summary）
6. `scripts/harness/ai_judge_evidence_closure.sh`（ai_judge P2/P3/P4 证据聚合）
7. `scripts/harness/ai_judge_calibration_prep.sh`（ai_judge P5 校准模板与待验证清单）
8. `scripts/harness/ai_judge_p5_real_calibration_on_env.sh`（ai_judge P5 真实环境校准门禁）
9. `scripts/harness/ai_judge_fairness_benchmark_freeze.sh`（ai_judge fairness benchmark 阈值冻结）
10. `scripts/harness/ai_judge_real_env_evidence_closure.sh`（ai_judge real-env 证据收口清单）
11. `scripts/harness/ai_judge_runtime_sla_freeze.sh`（ai_judge runtime SLA 阈值冻结）

### 2.3 当前统一入口能力

`journey_verify.sh` 当前已经负责：

1. 统一 profile 分发
2. 统一 JSON/Markdown 摘要
3. 统一记录 `evidence_missing`
4. 统一暴露候选脚本与证据来源
5. `judge-ops` profile 自动归集 ai_judge 模块门禁摘要证据

另外，`ai_judge` 主线新增证据收口脚本：

1. `scripts/harness/ai_judge_evidence_closure.sh`
2. 统一校验 P2/P3/P4 关键模块证据是否齐全
3. 输出 `pass/evidence_missing` 与统一 JSON/Markdown 摘要

同时，新增历史证据缺口补齐脚本：

1. `scripts/harness/ai_judge_evidence_gap_remediation.sh`
2. 从当前开发计划历史中提取模块摘要，为缺失模块生成标准化 `summary.json/.md`
3. 回填产物显式携带 `backfilled: true` 与来源 `plan_history`，用于和原始模块门禁结果区分

同时，P5 校准准备脚本用于本地阶段“先有模板与清单，再等真实数据”：

1. `scripts/harness/ai_judge_calibration_prep.sh`
2. 自动生成/检查延迟、成本、公平、故障演练、可信证明五类校准证据模板
3. 在缺少真实环境样本时输出 `pending_real_data`，不做假通过

真实环境执行阶段使用专门门禁脚本：

1. `scripts/harness/ai_judge_p5_real_calibration_on_env.sh`
2. 读取 `ai_judge_p5_real_env.env` 的 `REAL_CALIBRATION_ENV_READY` 判定环境是否就绪
3. 环境未就绪时输出 `env_blocked`；环境就绪且五类轨道满足 real 证据键时才输出 `pass`
4. 若明确允许本机参考（`--allow-local-reference`）且 marker 标记 `LOCAL_REFERENCE_ENV_READY=true`，会输出 `local_reference_pass/local_reference_pending`，用于本地设备参考，不替代真实环境 `pass`

fairness benchmark 冻结阶段使用专门脚本：

1. `scripts/harness/ai_judge_fairness_benchmark_freeze.sh`
2. 读取 `ai_judge_p5_fairness_benchmark.env` 与 `ai_judge_p5_real_env.env` 生成阈值冻结工件
3. 输出 `pass/local_reference_frozen/pending_data/threshold_violation/env_blocked`
4. 产出冻结阈值文件 `docs/loadtest/evidence/ai_judge_fairness_benchmark_thresholds.env`

real-env 证据收口阶段使用专门脚本：

1. `scripts/harness/ai_judge_real_env_evidence_closure.sh`
2. 统一检查六轨道 real 必填键与 marker 就绪状态（含 `runtime_sla_freeze`）
3. 默认输出 `pass/env_blocked/pending_real_evidence/evidence_missing`
4. 开启 `--allow-local-reference` 时可输出 `local_reference_ready/local_reference_pending`（仅本机预检，不替代 real pass）
5. 产出收口清单 `docs/loadtest/evidence/ai_judge_p5_real_env_closure_checklist.md`

runtime SLA 冻结阶段使用专门脚本：

1. `scripts/harness/ai_judge_runtime_sla_freeze.sh`
2. 读取 latency/fault/trust 三轨道证据与 `ai_judge_p5_real_env.env` 环境 marker
3. 输出 `pass/local_reference_frozen/pending_data/threshold_violation/env_blocked/evidence_missing`
4. 产出阈值工件 `docs/loadtest/evidence/ai_judge_runtime_sla_thresholds.env`

但当前还没有负责：

1. 真正执行业务旅程
2. 自动收集 logs / metrics / trace
3. 自动接入普通开发主链

---

## 3. 当前使用规则

当前使用时：

1. 模块级开发仍以 `post-module-test-guard` 为主验证入口
2. `journey_verify.sh` 适合单独生成运行态验证摘要，或为后续普通开发主链做证据准备
3. 如果仓库中已经存在更贴近该模块的专项脚本，应优先复用，并通过 `journey_verify.sh` 暴露统一结论
4. 若验证受环境限制阻塞，必须明确区分：
   - 代码逻辑失败
   - 环境阻塞
5. 不能把“缺环境证据”说成“已验证通过”
6. `journey_verify.sh` 当前若缺少具体运行态证据，会显式输出 `evidence_missing`

### 3.1 当前命令

```bash
bash scripts/harness/journey_verify.sh \
  --profile "<auth|lobby|room|judge-ops|release>" \
  --emit-json "artifacts/harness/manual-runtime.summary.json" \
  --emit-md "artifacts/harness/manual-runtime.summary.md" \
  [--collect-logs] \
  [--collect-metrics] \
  [--collect-trace]

bash scripts/harness/ai_judge_evidence_closure.sh \
  --emit-json "artifacts/harness/manual-ai-judge-evidence.summary.json" \
  --emit-md "artifacts/harness/manual-ai-judge-evidence.summary.md"

bash scripts/harness/ai_judge_evidence_gap_remediation.sh \
  --emit-json "artifacts/harness/manual-ai-judge-evidence-remediation.summary.json" \
  --emit-md "artifacts/harness/manual-ai-judge-evidence-remediation.summary.md"

bash scripts/harness/ai_judge_evidence_gap_remediation.sh \
  && bash scripts/harness/ai_judge_evidence_closure.sh

bash scripts/harness/ai_judge_calibration_prep.sh \
  --emit-json "artifacts/harness/manual-ai-judge-calibration.summary.json" \
  --emit-md "artifacts/harness/manual-ai-judge-calibration.summary.md"

bash scripts/harness/ai_judge_p5_real_calibration_on_env.sh \
  --emit-json "artifacts/harness/manual-ai-judge-p5-on-env.summary.json" \
  --emit-md "artifacts/harness/manual-ai-judge-p5-on-env.summary.md"

bash scripts/harness/ai_judge_p5_real_calibration_on_env.sh \
  --allow-local-reference \
  --emit-json "artifacts/harness/manual-ai-judge-p5-local-reference.summary.json" \
  --emit-md "artifacts/harness/manual-ai-judge-p5-local-reference.summary.md"

bash scripts/harness/ai_judge_fairness_benchmark_freeze.sh \
  --allow-local-reference \
  --emit-json "artifacts/harness/manual-ai-judge-fairness-benchmark-freeze.summary.json" \
  --emit-md "artifacts/harness/manual-ai-judge-fairness-benchmark-freeze.summary.md"

bash scripts/harness/ai_judge_real_env_evidence_closure.sh \
  --emit-json "artifacts/harness/manual-ai-judge-real-env-closure.summary.json" \
  --emit-md "artifacts/harness/manual-ai-judge-real-env-closure.summary.md"

bash scripts/harness/ai_judge_real_env_evidence_closure.sh \
  --allow-local-reference \
  --emit-json "artifacts/harness/manual-ai-judge-real-env-closure-local.summary.json" \
  --emit-md "artifacts/harness/manual-ai-judge-real-env-closure-local.summary.md"

bash scripts/harness/ai_judge_runtime_sla_freeze.sh \
  --allow-local-reference \
  --emit-json "artifacts/harness/manual-ai-judge-runtime-sla-freeze.summary.json" \
  --emit-md "artifacts/harness/manual-ai-judge-runtime-sla-freeze.summary.md"
```

---

## 4. 当前缺口

当前缺少的不是“测试命令”，而是“完整主链化的运行态验证能力”：

1. `auth/lobby/room/release` 的具体 profile 还未全部落地
2. 统一的日志/指标/trace 采集出口尚未真正实现
3. `journey_verify.sh` 还未接入 orchestrator 主链
4. `judge-ops` 之外的 profile 仍以提示与缺口暴露为主

---

## 5. 后续目标形态（未全部生效）

后续 Phase 3 仍要继续完成：

1. `auth` profile 细化
2. `lobby` / `room` profile 细化
3. `release` profile 细化
4. runtime verify 主链化

在那之前，当前仓库处于“已有统一入口，但验证证据仍分散”的状态。

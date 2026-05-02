# AI Judge Real-Env Readiness 输入冻结清单

更新时间：2026-05-01
状态：本地准备完成；真实环境未提供；不得宣称 real-env pass

## 1. 当前口径

1. 当前没有真实环境窗口，`REAL_CALIBRATION_ENV_READY` 必须保持 `false`。
2. 当前对象存储证据为 `local_reference` / `productionReady=false`，只能证明门禁会阻断 fake ready；即使出现污染 JSON 写成 `productionReady=true`，只要 `provider=local` 或 `status=local_reference`，preflight 也必须阻断。
3. `NPC Coach` / `Room QA` 仍保持暂停，本清单只服务官方 AI Judge / Official Verdict Plane。
4. 所有 `*_READY=true` 都必须有对应证据链接，不能只靠手工布尔值。

## 2. 输入模板

模板文件：[ai_judge_real_env_readiness_inputs.env.example](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_real_env_readiness_inputs.env.example)

真实环境开放后，把模板中的值同步到 [ai_judge_p5_real_env.env](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_p5_real_env.env) 或同名环境变量中，再运行 preflight。

## 3. 必填输入与证据

| 输入 | 当前默认 | ready 条件 | 证据要求 |
| --- | --- | --- | --- |
| `REAL_CALIBRATION_ENV_READY` | `false` | 真实服务窗口、真实样本、真实 provider/callback 与目标阈值均具备 | real-env window 负责人确认 |
| `CALIBRATION_ENV_MODE` | `real` | 只在真实窗口使用 `real` | 不接受 `local_reference` 作为 real pass |
| `REAL_SAMPLE_MANIFEST` | 空 | 指向真实样本 manifest | 样本字段、脱敏状态、数据集版本已审核 |
| `REAL_SAMPLE_MANIFEST_READY` | `false` | manifest 通过校验 | fairness benchmark manifest evidence |
| `REAL_PROVIDER_READY` | `false` | 真实模型/provider 可用 | provider 健康检查或运行窗口记录 |
| `REAL_CALLBACK_READY` | `false` | 回写 callback 可用 | callback 健康检查或端到端回写记录 |
| `PRODUCTION_ARTIFACT_STORE_READY` | `false` | 对象存储 roundtrip 通过 | `artifact_store_healthcheck.py` 输出 `productionReady=true`、`provider!=local` 且 roundtrip 为 `pass` |
| `PRODUCTION_ARTIFACT_STORE_EVIDENCE_JSON` | `docs/loadtest/evidence/ai_judge_artifact_store_healthcheck.json` | 指向生产对象存储 healthcheck evidence | evidence 必须脱敏，且不是 `local_reference`；不得只手工设置 `PRODUCTION_ARTIFACT_STORE_READY=true` |
| `BENCHMARK_TARGETS_READY` | `false` | benchmark 样本口径与阈值冻结 | benchmark target freeze evidence |
| `FAIRNESS_TARGETS_READY` | `false` | fairness 阈值冻结 | fairness benchmark threshold evidence |
| `RUNTIME_OPS_TARGETS_READY` | `false` | runtime ops / SLA 目标冻结 | runtime ops / SLA freeze evidence |
| `REAL_EVIDENCE_LINK` | 空 | 指向真实窗口证据汇总 | closure 输出、运行日志或证据索引 |

## 4. 真实环境开放后的执行顺序

1. 配置生产对象存储，运行：
   ```bash
   /Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/python ai_judge_service/scripts/artifact_store_healthcheck.py --enable-roundtrip --fail-on-not-ready --output docs/loadtest/evidence/ai_judge_artifact_store_healthcheck.json
   ```
2. 确认 [ai_judge_artifact_store_healthcheck.json](/Users/panyihang/Documents/EchoIsle/docs/loadtest/evidence/ai_judge_artifact_store_healthcheck.json) 中 `productionReady=true`。
3. 填入真实样本 manifest，并确认 `REAL_SAMPLE_MANIFEST_READY=true`。
4. 填入 provider、callback、benchmark、fairness、runtime ops 证据链接，并逐项把对应 `*_READY` 置为 `true`。
5. 运行：
   ```bash
   bash scripts/harness/ai_judge_real_env_window_closure.sh --preflight-only
   ```
6. 只有 preflight 输出 `preflight_ready` 后，才进入 `ai-judge-real-env-pass-window-execute-on-env`。

## 5. 禁止事项

1. 不把 `local_reference`、mock provider、mock callback 或本机对象存储写成真实通过。
2. 不只设置 `PRODUCTION_ARTIFACT_STORE_READY=true` 而缺少 healthcheck evidence；不使用 `provider=local`、`status=local_reference` 或 roundtrip 非 `pass` 的 evidence。
3. 不在 `NPC Coach` / `Room QA` 暂停期间推进 assistant executor、prompt/output、chat/frontend ready-state 或 Ops evidence。
4. 不把 preflight 的 `env_blocked` 解释成失败；在无真实环境时，它是正确阻断。

# consistency_reports

本目录用于保存“数据库/缓存一致性专项验证”产生的执行报告。

## 目录职责

- 仅存放执行产物（gate 报告、基线结果、故障注入结果）。
- 不存放开发计划、TODO、阶段进度说明。
- 开发计划仍统一写入 `docs/dev_plan/`。

## B3 报告命名规范

默认命名格式：

`AI裁判B3一致性验收报告-<mode>-<UTC时间>.md`

示例：

- `AI裁判B3一致性验收报告-memory-20260331-120000Z.md`
- `AI裁判B3一致性验收报告-redis-20260331-120030Z.md`

并发冲突兜底：

- 若同秒并发写入导致文件名冲突，脚本会自动重试并追加随机后缀：
  - `AI裁判B3一致性验收报告-redis-20260331-120030Z-a1b2c3.md`
- 重试次数可通过 `--report-collision-retries <N>` 调整（默认 `8`）。

## B3 报告保留策略

脚本：`ai_judge_service/scripts/b3_consistency_gate.py`

默认策略：

- 最多保留 `60` 份同前缀报告（按修改时间倒序保留最新）。
- 最大保留 `30` 天（超过天数自动清理）。
- 本次刚生成的报告不会被清理。

可调参数：

- `--report-retention-max-files <N>`
- `--report-retention-max-days <N>`
- `--skip-report-prune`（禁用清理）

## 周期归档脚本（建议每周执行）

脚本：`ai_judge_service/scripts/archive_consistency_reports.py`

职责：

- 将根目录中“超过保留天数”的报告迁移到 `archive/YYYY-MM/`。
- 保持根目录只保留近期报告，便于快速查看。
- 遇到目标文件名冲突时自动追加 `-dup-<random>` 后缀。

默认参数：

- `--keep-days-in-root 14`
- `--report-dir` 默认 `docs/consistency_reports`
- `--archive-dir` 默认 `docs/consistency_reports/archive`

常用参数：

- `--dry-run`：只打印迁移计划，不真正移动文件。
- `--max-collision-retries <N>`：目标名冲突重试次数（默认 `8`）。

## 并发冲突压测脚本（建议改造后执行）

脚本：`ai_judge_service/scripts/b3_report_collision_stress.py`

用途：

- 并发触发多个 `b3_consistency_gate` 进程，共用同一 `--report-out` 目标。
- 验证冲突重试机制是否保证“每个 worker 产出唯一报告路径”。
- 生成压测报告到 `docs/consistency_reports`。

默认行为：

- worker 数：`16`
- 默认模式：`memory`
- 固定并发目标文件：`b3-collision-stress-target.md`
- 报告前缀：`AI裁判B3报告冲突压测报告-<mode>-<UTC时间>.md`

常用参数：

- `--workers <N>`
- `--mode memory|auto|redis`
- `--collision-retries <N>`
- `--stress-report-out <path>`

## 本地维护脚本（定时执行入口）

脚本：`ai_judge_service/scripts/run_consistency_maintenance_local.sh`

职责：

- 先执行 memory 冲突压测；
- 可选执行 redis 冲突压测；
- 最后执行归档（dry-run 或 apply）。

常用参数：

- `--mode dry-run|apply`（默认 `dry-run`）
- `--keep-days <N>`（默认 `14`）
- `--memory-workers <N>`（默认 `16`）
- `--redis-workers <N>`（默认 `16`）
- `--skip-redis`

本地 cron 示例（每周一 09:00）：

```bash
0 9 * * 1 cd /Users/panyihang/Documents/EchoIsle/ai_judge_service && bash scripts/run_consistency_maintenance_local.sh --mode dry-run >> /Users/panyihang/Documents/EchoIsle/docs/consistency_reports/maintenance-cron.log 2>&1
```

## 推荐执行

```bash
cd /Users/panyihang/Documents/EchoIsle/ai_judge_service
../scripts/py scripts/b3_consistency_gate.py --mode auto
../scripts/py scripts/b3_consistency_gate.py --mode redis
../scripts/py scripts/archive_consistency_reports.py --dry-run
../scripts/py scripts/archive_consistency_reports.py --keep-days-in-root 14
../scripts/py scripts/b3_report_collision_stress.py --workers 16 --mode memory
bash scripts/run_consistency_maintenance_local.sh --mode dry-run
```

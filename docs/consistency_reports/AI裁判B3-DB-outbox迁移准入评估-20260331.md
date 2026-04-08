# AI裁判 B3 DB Outbox 迁移准入评估（本地）

- 评估时间: 2026-03-31
- 评估范围: B3 幂等竞争、outbox 并发回写、报告冲突恢复、维护链路可执行性
- 结论: **Go（准入通过）**

## 1. 准入阈值

1. `pending` 幂等竞争：`acquired=1`、`errors=0`、`p95 < 50ms`
2. `replay` 幂等重放：`replay=total`、`errors=0`、`p95 < 20ms`
3. outbox 回写竞争：`errors=0`、`pending_rows=0`、`p95 < 20ms`
4. 报告冲突恢复：并发写同目标文件时 `unique_report_paths == workers`
5. 维护可执行性：本地 dry-run 一键维护脚本可完成“压测 + 归档预演”

## 2. 样本证据

### 2.1 Redis 高并发一致性样本（已通过）

报告: `docs/consistency_reports/AI裁判B3一致性验收报告-redis-2026-03-31-36e8d0.md`

- pending: `120/20`, `acquired=1`, `errors=0`, `p95=15.93ms`
- replay: `120/20`, `replay=120`, `errors=0`, `p95=1.83ms`
- outbox: `160/20`, `errors=0`, `pending=0`, `p95=6.77ms`

结论: 全量满足阈值。

### 2.2 报告冲突压测样本（memory，已通过）

报告: `docs/consistency_reports/AI裁判B3报告冲突压测报告-memory-20260331-220618Z.md`

- workers: `16`
- succeeded: `16`
- unique_report_paths: `16`
- duplicates: `0`

结论: 冲突恢复机制满足唯一性要求。

### 2.3 本地维护脚本 dry-run（已通过）

命令:

```bash
cd /Users/panyihang/Documents/EchoIsle/ai_judge_service
bash scripts/run_consistency_maintenance_local.sh --mode dry-run --skip-redis --memory-workers 16 --keep-days 14
```

结果:

- memory 压测 PASS
- archive dry-run PASS
- maintenance 流程闭环可执行

## 3. 受限项与补充计划

1. 在当前会话沙箱下，`redis` 冲突压测（多 worker）受本地网络权限限制，未形成同轮放大量样本。
2. 已有 Redis 高并发一致性样本可支撑本轮“准入通过”判断。
3. 后续在无沙箱限制环境补齐 `redis` 冲突压测放大量样本，作为切换前补证动作。

## 4. Go / No-Go

- 判定: **Go**
- 原因: 关键一致性阈值全部达标，且维护链路可重复执行。
- 下阶段建议: 进入 DB outbox 切换实施计划（字段映射、写入路径替换、回放校验脚本）。

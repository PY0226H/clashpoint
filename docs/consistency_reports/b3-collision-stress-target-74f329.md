# AI 裁判 B3 一致性专项验收报告

- 生成时间: 2026-03-31T22:00:03.828529+00:00
- 运行模式: `redis`
- 结论: PASS

## 幂等并发竞争（pending）
- 请求数/并发: 10/2
- 状态计数: acquired=1, conflict=9, replay=0, errors=0
- 时延: p50=0.55ms, p95=2.54ms, max=2.54ms

## 幂等重放竞争（success）
- 请求数/并发: 10/2
- 状态计数: acquired=0, conflict=0, replay=10, errors=0
- 时延: p50=0.47ms, p95=9.82ms, max=9.82ms

## Outbox 并发回写
- 更新数/并发: 12/2
- 更新统计: sent=6, failed=6, errors=0
- 最终状态: failed
- 可见性快照: pending=0, sent=0, failed=1
- 时延: p50=0.43ms, p95=1.86ms, max=1.86ms

## 失败原因
- 无

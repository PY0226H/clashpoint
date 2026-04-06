# Test Gate Matrix

本仓库现有质量门禁主要来自：
- `.pre-commit-config.yaml`
- `.github/workflows/build.yml`

## Rust 门禁（本 Skill 默认执行）
适用目录：`chat`, `swiftide-pgvector`, `frontend/apps/desktop/src-tauri`

1. 格式检查
- `cargo fmt --all -- --check`

2. 编译检查
- `cargo check --all`

3. 静态检查
- `cargo clippy --all-targets --all-features --tests --benches -- -D warnings`

4. 测试执行
- `cargo nextest run --all-features`

## 何时使用 quick / full
- `quick`: 本地快速迭代，减少等待时间。
- `full`: 模块完成前必须执行，与 CI 预期一致。

## 当前已知差异
- 仓库存在 `e2e/` Playwright 测试，但 `e2e/package.json` 未定义统一 `test` 脚本。
- 本 Skill 默认不自动跑 Playwright，除非后续补齐统一命令并扩展脚本。

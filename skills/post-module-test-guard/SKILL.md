---
name: post-module-test-guard
description: "在模块代码实现或重构完成后，自动执行测试补齐与测试门禁。用于识别改动是否缺少测试、生成测试目标建议、补充或更新测试代码，并运行与 pre-commit/CI 对齐的测试流程，直到通过为止。"
---

# Post Module Test Guard

## 概述
把“模块开发完成”收口为可验证状态：
1. 先判断是否需要补测。
2. 再补充/更新测试代码。
3. 最后执行测试门禁并要求通过。

## 输出语言
- 默认使用中文描述执行结果。
- 命令、路径、技术关键字保持原样。

## 工作流
1. 收集本次改动文件。
2. 运行 `scripts/test_change_guard.sh` 检查是否存在“改代码未改测试”。
3. 如果缺测试：
   - 运行 `scripts/suggest_test_targets.sh` 生成候选测试位置。
   - 按 `references/test-generation-playbook.md` 补充测试代码。
4. 运行 `scripts/run_test_gate.sh` 执行测试门禁。
5. 失败则修复并重试，直到通过。

## Step 1: 检查是否缺少测试
运行：

```bash
bash skills/post-module-test-guard/scripts/test_change_guard.sh
```

- 返回 0: 测试改动充分，可进入测试门禁。
- 返回 2: 检测到业务/模块代码改动，但没有对应测试改动，必须先补测。

## Step 2: 生成测试目标并补测
当 Step 1 返回 2 时：

```bash
bash skills/post-module-test-guard/scripts/suggest_test_targets.sh
```

然后按以下优先级补测：
1. 直接覆盖本次改动的行为分支（成功路径 + 失败路径）。
2. 覆盖边界条件（空值、越界、权限、异常输入、并发/重复提交）。
3. 覆盖回归风险点（这次修复过的问题必须有测试）。

补测规则见 `references/test-generation-playbook.md`。

## Step 3: 跑测试门禁
运行：

```bash
bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode full
```

该脚本会执行与仓库 pre-commit / CI 一致的 Rust 门禁：
- `cargo fmt --all -- --check`
- `cargo check --all`
- `cargo clippy --all-targets --all-features --tests --benches -- -D warnings`
- `cargo nextest run --all-features`

## Step 4: 沙箱/环境受限失败处理（强制）
如果门禁失败且日志出现以下任一特征，必须视为“环境阻塞”，不能直接跳过：
1. 数据库不可达：`no reachable postgres maintenance url`、`Connection refused`、`could not connect to server`
2. 网络受限：`Could not resolve host`、依赖下载失败
3. 权限受限：`permission denied`、沙箱写入/访问限制

处理规则：
1. 先明确失败原因属于环境受限，而不是代码逻辑错误。
2. 立即申请提升权限（escalation）并重跑同一门禁命令，不得直接结束本轮。
3. 仅当“提升权限后仍失败”时，才进入问题修复或向用户同步阻塞细节。
4. 若用户拒绝权限申请，需明确说明“当前测试结论待定，受环境限制”，不能给出“已通过”结论。

## 完成标准
只有同时满足以下条件才算模块完成：
1. 业务改动对应测试已补齐。
2. 测试门禁全通过。
3. 最终回复中列出关键测试与命令结果。

## 资源

### scripts/
- `scripts/test_change_guard.sh`: 识别“改代码未改测试”的情况。
- `scripts/suggest_test_targets.sh`: 根据改动文件给出测试落点建议。
- `scripts/run_test_gate.sh`: 运行测试门禁（对齐 pre-commit/CI）。

### references/
- `references/test-gate-matrix.md`: 当前仓库测试门禁矩阵。
- `references/test-generation-playbook.md`: 如何针对改动补测。

### assets/
- `assets/module-test-checklist.md`: 模块测试收口清单模板。

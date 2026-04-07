# 计划文档识别说明

脚本 `post_module_plan_sync.sh` 的目标是回写“当前正在使用”的开发计划文档，而不是写死某一个固定路径。
在 P1-3 之后，“当前正在使用”优先通过活动计划入口与命名 slot 定义，而不是继续依赖最近修改时间猜测。

## 检测优先级
1. `--plan` 显式指定。
2. `--slot` 显式指定。
3. 环境变量：`POST_MODULE_ACTIVE_PLAN` / `ACTIVE_PLAN_DOC` / `PLAN_DOC`。
4. 环境变量：`POST_MODULE_PLAN_SLOT` / `ACTIVE_PLAN_SLOT` / `PLAN_SLOT`。
5. `.codex/plan-slots/*.txt`。
6. legacy fallback：`git status` 已改动且文件名包含 `开发计划` 的 Markdown 文档。
7. legacy fallback：`docs/dev_plan/*开发计划*.md` 中最近修改文件。
8. legacy fallback：`docs/**/*开发计划*.md` 中最近修改文件。

## 冲突处理
- 若显式传入 `--plan`，直接使用指定文档。
- 若显式传入 `--slot`，只解析对应 slot 指针。
- 若未显式指定且检测到多个活动 slot，脚本会拒绝猜测并直接报错。
- 只有在 slot 机制不可用时，legacy fallback 才会退回到“最近修改时间”策略。
- 若无法识别到候选文件，脚本会报错并退出。

## 建议
- 单计划时期：保持 `default` slot 指向 `docs/dev_plan/当前开发计划.md`。
- 并行计划时期：每个线程使用独立 slot，例如 `backend-signin`、`frontend-ui`。
- 目标文档完全明确时，优先传 `--plan`。

# 计划文档识别说明

脚本 `post_module_plan_sync.sh` 的目标是回写“当前正在使用”的开发计划文档，而不是写死某一个固定路径。

## 检测优先级
1. `--plan` 显式指定。
2. 环境变量：`POST_MODULE_ACTIVE_PLAN` / `ACTIVE_PLAN_DOC` / `PLAN_DOC`。
3. `git status` 已改动且文件名包含 `开发计划` 的 Markdown 文档。
4. `docs/dev_plan/*开发计划*.md` 中最近修改文件。
5. `docs/**/*开发计划*.md` 中最近修改文件。

## 冲突处理
- 若同优先级存在多个候选，按“最近修改时间”选择。
- 若无法识别到候选文件，脚本会报错并退出。

## 建议
- 为避免误判，模块回写时优先传 `--plan`。
- 在自动化任务中可设置 `POST_MODULE_ACTIVE_PLAN` 固定当前阶段文档。

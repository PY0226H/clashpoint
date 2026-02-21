# 问题与修复记录

## post-module-interview-journal-skill | 2026-02-21 03:27:05 -0800
- 改动概述: 创建了一个自动文档化 Skill：每次模块实现后自动沉淀开发细节、问题修复细节和面试问答内容，并在 AGENTS.md 中加入自动执行触发规则。
- 问题 -> 修复:
- 现象/根因: 沙箱拒绝写入 `.codex` 目录。
  修复: 将 Skill 实现迁移到可写的 `skills/` 目录，并同步更新 AGENTS 路径。
- 验证结果:
- python3 /Users/panyihang/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/post-module-interview-journal -> pass

## post-module-interview-journal-script-fix | 2026-02-21 03:27:36 -0800
- 改动概述: 强化文档脚本中的 git 元数据提取逻辑，兼容仓库无提交记录或 HEAD 处于 detached/unborn 状态的场景。
- 问题 -> 修复:
- 现象/根因: 在 unborn 仓库中，`git rev-parse --abbrev-ref HEAD` 会输出 `HEAD` 且返回非零，导致分支信息异常。
  修复: 改为 `symbolic-ref` 获取分支并为无提交场景增加 `uncommitted` 回退值。
- 验证结果:
- bash skills/post-module-interview-journal/scripts/update_module_docs.sh --help -> pass
## post-module-interview-journal-zh | 2026-02-21 03:36:06 -0800
- 改动概述: 将 post-module-interview-journal 的自动文档输出全面中文化：脚本提示、字段名、STAR 结构、问题修复描述和模板内容均改为中文。
- 问题 -> 修复:
- 现象/根因: 文档脚本默认英文输出不符合项目要求
  修复: 统一替换为中文文案并补充中文 STAR 与高频问题模板
- 验证结果:
- python3 /Users/panyihang/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/post-module-interview-journal -> pass;bash skills/post-module-interview-journal/scripts/update_module_docs.sh --help -> pass

## post-module-test-guard-skill | 2026-02-21 03:46:01 -0800
- 改动概述: 新增 post-module-test-guard Skill：在模块实现后自动做缺测检查、测试目标建议与测试门禁执行，确保改动有测试并可通过质量门禁；同时将该 Skill 接入 AGENTS 的强制后置流程。
- 问题 -> 修复:
- 现象/根因: init_skill.py 初始化时 short_description 超长导致中断
  修复: 改为手动补齐 Skill 目录结构与元数据文件
- 现象/根因: test_change_guard.sh 变量插值出现异常字符导致 unbound variable
  修复: 重写输出行并使用显式变量包裹
- 验证结果:
- python3 /Users/panyihang/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/post-module-test-guard -> pass;bash skills/post-module-test-guard/scripts/test_change_guard.sh --changes <skill-files> -> pass;bash skills/post-module-test-guard/scripts/test_change_guard.sh --changes chat/chat_server/src/lib.rs -> expected exit 2

## post-module-test-guard-network-hint | 2026-02-21 03:47:52 -0800
- 改动概述: 优化 run_test_gate.sh 的失败提示：当环境因无法访问 github 导致 utoipa-swagger-ui 下载失败时，明确提示这是外网依赖问题，并给出重试/预置资源建议。
- 问题 -> 修复:
- 现象/根因: run_test_gate 实跑时在无外网环境因 swagger-ui 资源下载失败，容易被误判为代码回归
  修复: 增加可读的故障归因提示与处理建议
- 验证结果:
- bash skills/post-module-test-guard/scripts/run_test_gate.sh --help -> pass;python3 /Users/panyihang/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/post-module-test-guard -> pass

## security-auth-header-only-v1 | 2026-02-21 03:52:20 -0800
- 改动概述: 第一模块完成：新增 Header-only 鉴权中间件，并将 chat_server 的主业务 API 切换为仅 Header 鉴权；文件下载链路保留兼容 token query。同步新增中间件测试，验证 Header-only 会拒绝 query token。
- 问题 -> 修复:
- 现象/根因: 测试守门脚本仅按测试文件路径判断，无法识别 Rust 内联测试导致误报缺测
  修复: 增强脚本：若 src/*.rs 含 #[cfg(test)] 视为测试证据
- 现象/根因: 完整门禁在无外网环境下构建 utoipa-swagger-ui 失败
  修复: 保留失败归因提示并标记为环境阻塞
- 验证结果:
- cd chat && cargo test -p chat-core verify_token_middleware_should_work -- --nocapture -> pass;cd chat && cargo test -p chat-core verify_token_header_only_middleware_should_reject_query_token -- --nocapture -> pass;bash skills/post-module-test-guard/scripts/test_change_guard.sh --changes 'chat/chat_core/src/middlewares/auth.rs;chat/chat_core/src/middlewares/mod.rs;chat/chat_server/src/lib.rs' -> pass;bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode quick -> blocked by swagger-ui download (no network)

## analytics-header-auth-no-query-token-v1 | 2026-02-21 04:11:13 -0800
- 改动概述: 第二模块完成：analytics 链路去除 URL token。后端 analytics 改为 extract_user_header_only（仅从 Authorization 头提取可选用户）；前端埋点上报改为 fetch + Authorization 头，不再在 URL 上拼接 token。
- 问题 -> 修复:
- 现象/根因: analytics 上报原先通过 URL query 传 token，存在日志/代理泄露风险
  修复: 改为 Authorization 头并统一 keepalive fetch
- 现象/根因: 测试守门脚本原先只看测试文件路径，Rust 内联测试会被误判
  修复: 增强为识别 src/*.rs 内 #[cfg(test)]
- 验证结果:
- cd chat && cargo test -p chat-core extract_user_header_only_should_ignore_query_token -- --nocapture -> pass;cd chat && cargo test -p chat-core verify_token_header_only_middleware_should_reject_query_token -- --nocapture -> pass;bash skills/post-module-test-guard/scripts/test_change_guard.sh --changes 'chat/analytics_server/src/lib.rs;chatapp/src/analytics/event.js;chat/chat_core/src/middlewares/auth.rs' -> pass;bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode quick -> blocked by swagger-ui download (no network in this runtime)


---
name: python-venv-guard
description: "在执行任何 Python 相关命令前，强制检查并使用项目虚拟环境（.venv），禁止使用全局 python/pip。适用于安装依赖、运行测试、启动服务、执行脚本等所有 Python 工作流。"
---

# Python Venv Guard

## 目标
确保所有 Python 命令都在项目虚拟环境中执行，避免全局环境污染和依赖漂移。

## 强制规则
1. 任何 Python 命令前，先执行 `scripts/assert_venv.sh` 做环境检查。
2. 仓库内默认入口统一使用 `scripts/py` 与 `scripts/pip`。
3. 只允许使用 `<venv>/bin/python` 运行 Python（由 `scripts/py` 代理）。
4. `pip` 必须通过 `<venv>/bin/python -m pip` 调用（由 `scripts/pip` 代理）。
5. 禁止直接使用全局 `python`、`python3`、`pip`、`pip3`。

## 默认路径
- 项目目录：`ai_judge_service`
- 虚拟环境目录：`ai_judge_service/.venv`
- 解释器：`ai_judge_service/.venv/bin/python`

## 执行流程
1. 运行检查脚本：
```bash
bash skills/python-venv-guard/scripts/assert_venv.sh \
  --project /Users/panyihang/Documents/EchoIsle/ai_judge_service \
  --venv /Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv
```

2. 安装依赖（推荐入口）：
```bash
/Users/panyihang/Documents/EchoIsle/scripts/pip install -r /Users/panyihang/Documents/EchoIsle/ai_judge_service/requirements.txt
```

3. 运行测试（推荐入口）：
```bash
cd /Users/panyihang/Documents/EchoIsle/ai_judge_service
../scripts/py -m unittest discover -s tests -p "test_*.py" -v
```

4. 启动服务（推荐入口）：
```bash
cd /Users/panyihang/Documents/EchoIsle/ai_judge_service
../scripts/py -m uvicorn app.main:app --host 0.0.0.0 --port 8787
```

## 失败处理
- 若 `.venv` 不存在：先创建虚拟环境，再安装依赖。
- 若检查脚本判定为全局环境：停止执行，改用 `<venv>/bin/python` 重跑。

## 资源
- `scripts/assert_venv.sh`：验证虚拟环境存在且解释器正确。
- `/Users/panyihang/Documents/EchoIsle/scripts/py`：仓库 Python 统一执行入口（自动 venv 校验）。
- `/Users/panyihang/Documents/EchoIsle/scripts/pip`：仓库 Pip 统一执行入口（自动 venv 校验）。
- `references/python-command-policy.md`：命令规范与反例清单。

# Python 命令策略

## 允许
1. `/Users/panyihang/Documents/EchoIsle/scripts/pip ...`
2. `cd /Users/panyihang/Documents/EchoIsle/ai_judge_service && ../scripts/py -m unittest ...`
3. `cd /Users/panyihang/Documents/EchoIsle/ai_judge_service && ../scripts/py -m uvicorn ...`
4. （兼容）`/Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/python -m <module> ...`

## 禁止
1. `python ...`
2. `python3 ...`
3. `pip ...`
4. `pip3 ...`
5. `python -m pip ...`（未明确指定 venv 绝对路径）

## 说明
- 如果需要执行任意 Python 模块，统一使用 `<venv>/bin/python -m <module>`。
- 仓库日常开发优先使用 `scripts/py` 与 `scripts/pip`，它们会先做 venv 校验再执行。
- 不要依赖 shell 激活状态；直接使用 venv 绝对路径最稳定。

# AI Judge Service (Mock)

用于接收 `chat_server` 的评审派发请求，执行本地可重复的双次评估逻辑，并回调内部接口写入评审结果。

## 目录结构

- `app/main.py`: FastAPI 入口与回调编排
- `app/models.py`: 派发请求与回调模型
- `app/scoring_core.py`: 不依赖三方框架的评分核心
- `app/scoring.py`: `pydantic` 适配层
- `tests/test_scoring_core.py`: 评分核心单测（`unittest`）

## 快速启动

```bash
cd ai_judge_service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8787
```

## 环境变量

- `AI_JUDGE_INTERNAL_KEY`: 与 `chat_server.ai_judge.internal_key` 保持一致
- `CHAT_SERVER_BASE_URL`: 例如 `http://127.0.0.1:6688`
- `CHAT_SERVER_REPORT_PATH_TEMPLATE`: 默认 `/api/internal/ai/judge/jobs/{job_id}/report`
- `CHAT_SERVER_FAILED_PATH_TEMPLATE`: 默认 `/api/internal/ai/judge/jobs/{job_id}/failed`
- `CALLBACK_TIMEOUT_SECONDS`: 回调超时，默认 `8`
- `JUDGE_PROCESS_DELAY_MS`: 模拟处理耗时，默认 `0`

## 运行测试

依赖安装完成后执行：

```bash
cd ai_judge_service
python3 -m unittest discover -s tests -p "test_*.py" -v
```

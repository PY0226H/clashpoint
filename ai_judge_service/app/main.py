from __future__ import annotations

from .app_factory import create_default_app
from .openai_judge import build_report_with_openai as _build_report_with_openai


app = create_default_app()

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from . import models as _models  # noqa: F401
from .base import Base


@dataclass(frozen=True)
class DatabaseRuntime:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]

    async def create_schema(self) -> None:
        # 使用统一 metadata 建表，保证本地开发环境可直接验证工作流主链。
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self.engine.dispose()


def build_database_runtime(*, settings: object) -> DatabaseRuntime:
    db_url = str(getattr(settings, "db_url", "")).strip()
    if not db_url:
        raise ValueError("AI_JUDGE_DB_URL cannot be empty")

    is_sqlite = db_url.startswith("sqlite+")
    engine_kwargs = {
        "echo": bool(getattr(settings, "db_echo", False)),
        "future": True,
    }
    if not is_sqlite:
        engine_kwargs["pool_size"] = max(1, int(getattr(settings, "db_pool_size", 10)))
        engine_kwargs["max_overflow"] = max(0, int(getattr(settings, "db_max_overflow", 20)))

    engine = create_async_engine(db_url, **engine_kwargs)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return DatabaseRuntime(engine=engine, session_factory=session_factory)

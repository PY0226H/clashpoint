from __future__ import annotations

from typing import Protocol

from .ledger_objects import JudgeLedgerSnapshot


class JudgeLedgerPort(Protocol):
    async def upsert_judge_ledger_snapshot(
        self,
        *,
        snapshot: JudgeLedgerSnapshot,
    ) -> JudgeLedgerSnapshot: ...

    async def get_judge_ledger_snapshot(
        self,
        *,
        case_id: int,
        dispatch_type: str | None = None,
        judge_policy_version: str | None = None,
        rubric_version: str | None = None,
    ) -> JudgeLedgerSnapshot | None: ...

    async def list_judge_ledger_snapshots(
        self,
        *,
        case_id: int,
        dispatch_type: str | None = None,
        limit: int = 20,
    ) -> list[JudgeLedgerSnapshot]: ...

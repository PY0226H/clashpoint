from __future__ import annotations

from typing import Protocol

from .models import TrustChallengeEvent, TrustRegistrySnapshot


class TrustRegistryPort(Protocol):
    async def upsert_trust_registry_snapshot(
        self,
        *,
        snapshot: TrustRegistrySnapshot,
    ) -> TrustRegistrySnapshot: ...

    async def get_trust_registry_snapshot(
        self,
        *,
        case_id: int,
        dispatch_type: str | None = None,
        trace_id: str | None = None,
        registry_version: str | None = None,
    ) -> TrustRegistrySnapshot | None: ...

    async def list_trust_registry_snapshots(
        self,
        *,
        case_id: int,
        dispatch_type: str | None = None,
        limit: int = 20,
    ) -> list[TrustRegistrySnapshot]: ...

    async def append_challenge_event(
        self,
        *,
        case_id: int,
        dispatch_type: str,
        trace_id: str,
        registry_version: str | None,
        event: TrustChallengeEvent,
    ) -> TrustRegistrySnapshot | None: ...

from __future__ import annotations

from typing import Any, Protocol

from .models import ArtifactManifest, ArtifactRef


class ArtifactStorePort(Protocol):
    async def put_json(
        self,
        *,
        case_id: int,
        kind: str,
        payload: dict[str, Any],
        redaction_level: str = "redacted",
        dispatch_type: str | None = None,
        trace_id: str | None = None,
        artifact_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactRef: ...

    async def get_json(self, *, ref: ArtifactRef) -> dict[str, Any]: ...

    async def exists(self, *, ref: ArtifactRef) -> bool: ...

    def build_manifest(
        self,
        *,
        case_id: int,
        dispatch_type: str,
        trace_id: str,
        refs: list[ArtifactRef] | tuple[ArtifactRef, ...],
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactManifest: ...

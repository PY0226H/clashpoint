from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.domain.artifacts import (
    ARTIFACT_CONTENT_TYPE_JSON,
    ArtifactManifest,
    ArtifactRef,
    normalize_artifact_kind,
    normalize_redaction_level,
    sha256_hex,
    stable_json_bytes,
    validate_artifact_payload,
)

_SAFE_ARTIFACT_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _safe_token(value: Any, *, fallback: str = "unknown") -> str:
    token = str(value or "").strip().lower().replace("-", "_")
    cleaned = re.sub(r"[^a-z0-9_.]+", "_", token).strip("._")
    return cleaned or fallback


@dataclass(frozen=True)
class _ArtifactPath:
    case_id: int
    kind: str
    artifact_id: str
    path: Path


class LocalArtifactStore:
    def __init__(self, *, root_dir: str | Path, namespace: str = "ai_judge_service") -> None:
        self._root_dir = Path(root_dir).expanduser()
        self._namespace = _safe_token(namespace, fallback="ai_judge_service")

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
    ) -> ArtifactRef:
        normalized_kind = normalize_artifact_kind(kind)
        normalized_redaction = normalize_redaction_level(redaction_level)
        validate_artifact_payload(payload)
        body = stable_json_bytes(payload)
        digest = sha256_hex(payload)
        resolved_artifact_id = self._build_artifact_id(
            case_id=case_id,
            kind=normalized_kind,
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            digest=digest,
            explicit_artifact_id=artifact_id,
        )
        artifact_path = self._artifact_path(
            case_id=case_id,
            kind=normalized_kind,
            artifact_id=resolved_artifact_id,
        )
        artifact_path.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = artifact_path.path.with_name(f".{artifact_path.path.name}.tmp")
        temp_path.write_bytes(body)
        temp_path.replace(artifact_path.path)
        return ArtifactRef(
            artifact_id=resolved_artifact_id,
            kind=normalized_kind,
            uri=self._uri_for(artifact_path),
            sha256=digest,
            content_type=ARTIFACT_CONTENT_TYPE_JSON,
            created_at=_utcnow(),
            redaction_level=normalized_redaction,
            size_bytes=len(body),
            metadata=dict(metadata or {}),
        ).normalized()

    async def get_json(self, *, ref: ArtifactRef) -> dict[str, Any]:
        normalized_ref = ref.normalized()
        artifact_path = self._artifact_path_from_ref(normalized_ref)
        body = artifact_path.path.read_bytes()
        digest = sha256_hex(json.loads(body.decode("utf-8")))
        if digest != normalized_ref.sha256:
            raise ValueError("artifact_sha256_mismatch")
        payload = json.loads(body.decode("utf-8"))
        validate_artifact_payload(payload)
        return payload

    async def exists(self, *, ref: ArtifactRef) -> bool:
        try:
            await self.get_json(ref=ref)
        except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
            return False
        return True

    def build_manifest(
        self,
        *,
        case_id: int,
        dispatch_type: str,
        trace_id: str,
        refs: list[ArtifactRef] | tuple[ArtifactRef, ...],
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactManifest:
        return ArtifactManifest(
            case_id=case_id,
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            refs=tuple(ref.normalized() for ref in refs),
            created_at=_utcnow(),
            metadata=dict(metadata or {}),
        ).normalized()

    def _build_artifact_id(
        self,
        *,
        case_id: int,
        kind: str,
        dispatch_type: str | None,
        trace_id: str | None,
        digest: str,
        explicit_artifact_id: str | None,
    ) -> str:
        if explicit_artifact_id:
            artifact_id = str(explicit_artifact_id).strip()
        else:
            dispatch_token = _safe_token(dispatch_type, fallback="unknown")
            trace_token = _safe_token(trace_id, fallback="trace")[:32]
            artifact_id = f"{kind}-{int(case_id)}-{dispatch_token}-{trace_token}-{digest[:16]}"
        if not _SAFE_ARTIFACT_ID_RE.match(artifact_id) or "/" in artifact_id:
            raise ValueError("artifact_id_invalid")
        return artifact_id

    def _artifact_path(self, *, case_id: int, kind: str, artifact_id: str) -> _ArtifactPath:
        parsed_case_id = int(case_id)
        if parsed_case_id <= 0:
            raise ValueError("artifact_case_id_invalid")
        normalized_kind = normalize_artifact_kind(kind)
        if not _SAFE_ARTIFACT_ID_RE.match(artifact_id):
            raise ValueError("artifact_id_invalid")
        candidate = (
            self._root_dir
            / str(parsed_case_id)
            / normalized_kind
            / f"{artifact_id}.json"
        )
        resolved = candidate.resolve()
        root = self._root_dir.resolve()
        # 本地适配器必须把写入钉在配置根目录内，避免 URI 或 artifactId 逃逸路径。
        if not resolved.is_relative_to(root):
            raise ValueError("artifact_path_outside_root")
        return _ArtifactPath(
            case_id=parsed_case_id,
            kind=normalized_kind,
            artifact_id=artifact_id,
            path=resolved,
        )

    def _artifact_path_from_ref(self, ref: ArtifactRef) -> _ArtifactPath:
        parsed = urlparse(ref.uri)
        if parsed.scheme != "local-artifact":
            raise ValueError("artifact_uri_scheme_invalid")
        if parsed.netloc != self._namespace:
            raise ValueError("artifact_uri_namespace_invalid")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 3:
            raise ValueError("artifact_uri_path_invalid")
        case_id_raw, kind, filename = parts
        if not filename.endswith(".json"):
            raise ValueError("artifact_uri_filename_invalid")
        artifact_id = filename.removesuffix(".json")
        if artifact_id != ref.artifact_id:
            raise ValueError("artifact_uri_id_mismatch")
        return self._artifact_path(
            case_id=int(case_id_raw),
            kind=kind,
            artifact_id=artifact_id,
        )

    def _uri_for(self, artifact_path: _ArtifactPath) -> str:
        return (
            f"local-artifact://{self._namespace}/"
            f"{artifact_path.case_id}/{artifact_path.kind}/{artifact_path.artifact_id}.json"
        )

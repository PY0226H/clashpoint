from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
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


def _normalize_prefix(value: str | None) -> str:
    prefix = str(value or "").strip().strip("/")
    if not prefix:
        return ""
    parts = [part for part in prefix.split("/") if part]
    if any(part in {".", ".."} for part in parts):
        raise ValueError("artifact_s3_prefix_invalid")
    return "/".join(parts)


def _safe_token(value: Any, *, fallback: str = "unknown") -> str:
    token = str(value or "").strip().lower().replace("-", "_")
    cleaned = re.sub(r"[^a-z0-9_.]+", "_", token).strip("._")
    return cleaned or fallback


def _body_bytes(value: Any) -> bytes:
    if hasattr(value, "read"):
        value = value.read()
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    raise ValueError("artifact_s3_body_invalid")


@dataclass(frozen=True)
class _ArtifactKey:
    case_id: int
    kind: str
    artifact_id: str
    key: str


class S3CompatibleArtifactStore:
    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "ai_judge_service",
        client: Any,
        force_path_style: bool = False,
        endpoint_configured: bool = False,
    ) -> None:
        bucket_token = str(bucket or "").strip()
        if not bucket_token:
            raise ValueError("artifact_s3_bucket_required")
        if "/" in bucket_token:
            raise ValueError("artifact_s3_bucket_invalid")
        self._bucket = bucket_token
        self._prefix = _normalize_prefix(prefix)
        self._client = client
        self._force_path_style = bool(force_path_style)
        self._endpoint_configured = bool(endpoint_configured)

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
        artifact_key = self._artifact_key(
            case_id=case_id,
            kind=normalized_kind,
            artifact_id=resolved_artifact_id,
        )
        self._client.put_object(
            Bucket=self._bucket,
            Key=artifact_key.key,
            Body=body,
            ContentType=ARTIFACT_CONTENT_TYPE_JSON,
            Metadata={
                "sha256": digest,
                "artifact_id": resolved_artifact_id,
                "artifact_kind": normalized_kind,
                "redaction_level": normalized_redaction,
            },
        )
        return ArtifactRef(
            artifact_id=resolved_artifact_id,
            kind=normalized_kind,
            uri=self._uri_for(artifact_key),
            sha256=digest,
            content_type=ARTIFACT_CONTENT_TYPE_JSON,
            created_at=_utcnow(),
            redaction_level=normalized_redaction,
            size_bytes=len(body),
            metadata=dict(metadata or {}),
        ).normalized()

    async def get_json(self, *, ref: ArtifactRef) -> dict[str, Any]:
        normalized_ref = ref.normalized()
        artifact_key = self._artifact_key_from_ref(normalized_ref)
        response = self._client.get_object(Bucket=self._bucket, Key=artifact_key.key)
        body = _body_bytes(response.get("Body"))
        payload = json.loads(body.decode("utf-8"))
        digest = sha256_hex(payload)
        if digest != normalized_ref.sha256:
            raise ValueError("artifact_sha256_mismatch")
        validate_artifact_payload(payload)
        return payload

    async def exists(self, *, ref: ArtifactRef) -> bool:
        try:
            normalized_ref = ref.normalized()
            artifact_key = self._artifact_key_from_ref(normalized_ref)
            self._client.head_object(Bucket=self._bucket, Key=artifact_key.key)
        except Exception:
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

    def readiness_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "provider": "s3_compatible",
            "status": "production_configured",
            "productionReady": True,
            "uriScheme": "s3",
            "bucketConfigured": bool(self._bucket),
            "prefixConfigured": bool(self._prefix),
            "endpointConfigured": self._endpoint_configured,
        }
        if self._force_path_style:
            payload["forcePathStyle"] = True
        return payload

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

    def _artifact_key(self, *, case_id: int, kind: str, artifact_id: str) -> _ArtifactKey:
        parsed_case_id = int(case_id)
        if parsed_case_id <= 0:
            raise ValueError("artifact_case_id_invalid")
        normalized_kind = normalize_artifact_kind(kind)
        if not _SAFE_ARTIFACT_ID_RE.match(artifact_id):
            raise ValueError("artifact_id_invalid")
        key_parts = [str(parsed_case_id), normalized_kind, f"{artifact_id}.json"]
        key = "/".join([self._prefix, *key_parts]) if self._prefix else "/".join(key_parts)
        return _ArtifactKey(
            case_id=parsed_case_id,
            kind=normalized_kind,
            artifact_id=artifact_id,
            key=key,
        )

    def _artifact_key_from_ref(self, ref: ArtifactRef) -> _ArtifactKey:
        parsed = urlparse(ref.uri)
        if parsed.scheme != "s3":
            raise ValueError("artifact_uri_scheme_invalid")
        if parsed.netloc != self._bucket:
            raise ValueError("artifact_uri_bucket_invalid")
        path = parsed.path.lstrip("/")
        if self._prefix:
            prefix = f"{self._prefix}/"
            if not path.startswith(prefix):
                raise ValueError("artifact_uri_prefix_invalid")
            path = path.removeprefix(prefix)
        parts = [part for part in path.split("/") if part]
        if len(parts) != 3:
            raise ValueError("artifact_uri_path_invalid")
        case_id_raw, kind, filename = parts
        if not filename.endswith(".json"):
            raise ValueError("artifact_uri_filename_invalid")
        artifact_id = filename.removesuffix(".json")
        if artifact_id != ref.artifact_id:
            raise ValueError("artifact_uri_id_mismatch")
        return self._artifact_key(
            case_id=int(case_id_raw),
            kind=kind,
            artifact_id=artifact_id,
        )

    def _uri_for(self, artifact_key: _ArtifactKey) -> str:
        return f"s3://{self._bucket}/{artifact_key.key}"

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

ARTIFACT_MANIFEST_VERSION = "artifact-manifest-v1"
ARTIFACT_CONTENT_TYPE_JSON = "application/json"
ARTIFACT_REDACTION_LEVELS = frozenset({"redacted", "ops", "internal"})
ARTIFACT_KINDS = frozenset(
    {
        "transcript_snapshot",
        "evidence_pack",
        "replay_snapshot",
        "audit_pack",
        "trust_registry_snapshot",
    }
)
ARTIFACT_FORBIDDEN_KEYS = frozenset(
    {
        "accesstoken",
        "apikey",
        "authorization",
        "email",
        "messagecontent",
        "messages",
        "password",
        "phone",
        "prompt",
        "prompttext",
        "rawmessages",
        "rawprompt",
        "rawtrace",
        "rawtranscript",
        "refreshtoken",
        "secret",
        "sourcemessages",
        "token",
        "userid",
        "useridentity",
        "wallet",
    }
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def stable_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(stable_json_bytes(value)).hexdigest()


def normalize_artifact_kind(value: Any) -> str:
    token = str(value or "").strip().lower().replace("-", "_")
    if token not in ARTIFACT_KINDS:
        raise ValueError("artifact_kind_invalid")
    return token


def normalize_redaction_level(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token not in ARTIFACT_REDACTION_LEVELS:
        raise ValueError("artifact_redaction_level_invalid")
    return token


def _normalize_key(value: Any) -> str:
    return str(value or "").strip().replace("_", "").replace("-", "").lower()


def find_artifact_forbidden_keys(payload: Any) -> set[str]:
    violations: set[str] = set()

    def _walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if _normalize_key(key) in ARTIFACT_FORBIDDEN_KEYS:
                    violations.add(str(key))
                _walk(child)
        elif isinstance(value, list):
            for child in value:
                _walk(child)

    _walk(payload)
    return violations


def validate_artifact_payload(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("artifact_payload_not_dict")
    forbidden_keys = sorted(find_artifact_forbidden_keys(payload))
    if forbidden_keys:
        raise ValueError(f"artifact_payload_forbidden_keys:{','.join(forbidden_keys)}")


def normalize_artifact_hash(value: Any) -> str:
    token = str(value or "").strip().lower()
    if not _SHA256_RE.match(token):
        raise ValueError("artifact_sha256_invalid")
    return token


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _iso_datetime(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    kind: str
    uri: str
    sha256: str
    content_type: str = ARTIFACT_CONTENT_TYPE_JSON
    created_at: datetime | None = None
    redaction_level: str = "redacted"
    size_bytes: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> ArtifactRef:
        artifact_id = str(self.artifact_id or "").strip()
        uri = str(self.uri or "").strip()
        content_type = str(self.content_type or "").strip() or ARTIFACT_CONTENT_TYPE_JSON
        if not artifact_id:
            raise ValueError("artifact_id_required")
        if not uri:
            raise ValueError("artifact_uri_required")
        if uri.startswith("file://"):
            raise ValueError("artifact_uri_must_not_expose_file_path")
        return ArtifactRef(
            artifact_id=artifact_id,
            kind=normalize_artifact_kind(self.kind),
            uri=uri,
            sha256=normalize_artifact_hash(self.sha256),
            content_type=content_type,
            created_at=self.created_at,
            redaction_level=normalize_redaction_level(self.redaction_level),
            size_bytes=max(0, _safe_int(self.size_bytes)),
            metadata=dict(self.metadata),
        )

    def to_payload(self) -> dict[str, Any]:
        normalized = self.normalized()
        payload = {
            "artifactId": normalized.artifact_id,
            "kind": normalized.kind,
            "uri": normalized.uri,
            "sha256": normalized.sha256,
            "contentType": normalized.content_type,
            "createdAt": _iso_datetime(normalized.created_at),
            "redactionLevel": normalized.redaction_level,
            "sizeBytes": normalized.size_bytes,
        }
        if normalized.metadata:
            payload["metadata"] = dict(normalized.metadata)
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ArtifactRef:
        return cls(
            artifact_id=str(payload.get("artifactId") or ""),
            kind=str(payload.get("kind") or ""),
            uri=str(payload.get("uri") or ""),
            sha256=str(payload.get("sha256") or ""),
            content_type=str(payload.get("contentType") or ARTIFACT_CONTENT_TYPE_JSON),
            redaction_level=str(payload.get("redactionLevel") or "redacted"),
            size_bytes=_safe_int(payload.get("sizeBytes")),
            metadata=dict(payload.get("metadata")) if isinstance(payload.get("metadata"), dict) else {},
        )


@dataclass(frozen=True)
class ArtifactManifest:
    case_id: int
    dispatch_type: str
    trace_id: str
    refs: tuple[ArtifactRef, ...]
    manifest_version: str = ARTIFACT_MANIFEST_VERSION
    created_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> ArtifactManifest:
        case_id = _safe_int(self.case_id)
        if case_id <= 0:
            raise ValueError("artifact_manifest_case_id_invalid")
        dispatch_type = str(self.dispatch_type or "").strip().lower()
        if dispatch_type not in {"phase", "final"}:
            raise ValueError("artifact_manifest_dispatch_type_invalid")
        trace_id = str(self.trace_id or "").strip()
        if not trace_id:
            raise ValueError("artifact_manifest_trace_id_required")
        refs = tuple(ref.normalized() for ref in self.refs)
        if not refs:
            raise ValueError("artifact_manifest_refs_required")
        return ArtifactManifest(
            case_id=case_id,
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            refs=refs,
            manifest_version=str(self.manifest_version or "").strip() or ARTIFACT_MANIFEST_VERSION,
            created_at=self.created_at,
            metadata=dict(self.metadata),
        )

    def to_payload(self) -> dict[str, Any]:
        normalized = self.normalized()
        ref_payloads = [ref.to_payload() for ref in normalized.refs]
        artifact_hashes = {ref["kind"]: ref["sha256"] for ref in ref_payloads}
        basis = {
            "version": normalized.manifest_version,
            "caseId": normalized.case_id,
            "dispatchType": normalized.dispatch_type,
            "traceId": normalized.trace_id,
            "artifactRefs": ref_payloads,
            "artifactHashes": artifact_hashes,
            "metadata": dict(normalized.metadata),
        }
        return {
            **basis,
            "artifactCount": len(ref_payloads),
            "createdAt": _iso_datetime(normalized.created_at),
            "manifestHash": sha256_hex(basis),
        }

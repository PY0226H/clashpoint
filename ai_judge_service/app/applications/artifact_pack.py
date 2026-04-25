from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.artifacts import ArtifactManifest, ArtifactRef, ArtifactStorePort

CASE_ARTIFACT_KINDS: tuple[str, ...] = (
    "transcript_snapshot",
    "evidence_pack",
    "replay_snapshot",
    "audit_pack",
    "trust_registry_snapshot",
)


@dataclass(frozen=True)
class CaseArtifactPack:
    manifest: ArtifactManifest
    refs: tuple[ArtifactRef, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest.to_payload(),
            "refs": [ref.to_payload() for ref in self.refs],
        }


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


async def write_case_artifact_pack(
    *,
    artifact_store: ArtifactStorePort,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    transcript_snapshot: dict[str, Any] | None = None,
    evidence_pack: dict[str, Any] | None = None,
    replay_snapshot: dict[str, Any] | None = None,
    audit_pack: dict[str, Any] | None = None,
    trust_registry_snapshot: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> CaseArtifactPack:
    sections = {
        "transcript_snapshot": _dict_or_empty(transcript_snapshot),
        "evidence_pack": _dict_or_empty(evidence_pack),
        "replay_snapshot": _dict_or_empty(replay_snapshot),
        "audit_pack": _dict_or_empty(audit_pack),
        "trust_registry_snapshot": _dict_or_empty(trust_registry_snapshot),
    }
    refs: list[ArtifactRef] = []
    for kind in CASE_ARTIFACT_KINDS:
        payload = sections[kind]
        if not payload:
            continue
        ref = await artifact_store.put_json(
            case_id=case_id,
            kind=kind,
            payload=payload,
            redaction_level="ops" if kind == "audit_pack" else "redacted",
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            metadata={
                "caseId": int(case_id),
                "dispatchType": str(dispatch_type or "").strip().lower(),
                "traceId": str(trace_id or "").strip(),
            },
        )
        refs.append(ref)
    manifest = artifact_store.build_manifest(
        case_id=case_id,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        refs=refs,
        metadata=dict(metadata or {}),
    )
    return CaseArtifactPack(manifest=manifest, refs=tuple(refs))

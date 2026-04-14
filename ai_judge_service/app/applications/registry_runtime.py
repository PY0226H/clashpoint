from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

DEFAULT_PROMPT_REGISTRY_VERSION = "promptset-v3-default"
DEFAULT_TOOL_REGISTRY_VERSION = "toolset-v3-default"
DEFAULT_PROMPT_VERSIONS = {
    "summaryPromptVersion": "v3.a2a3.summary.v1",
    "agent2PromptVersion": "v3.a6a7.bidirectional.v2",
    "finalPipelineVersion": "v3-final-a9a10-rollup-v2",
    "claimGraphVersion": "v1-claim-graph-bootstrap",
}
DEFAULT_TOOL_IDS = (
    "transcript_reader",
    "summary_guard",
    "evidence_retriever",
    "agent2_bidirectional_path",
    "fairness_gate_phase2",
    "claim_graph_builder",
)


@dataclass(frozen=True)
class PromptSetProfile:
    version: str
    prompt_versions: dict[str, str]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ToolsetProfile:
    version: str
    tool_ids: tuple[str, ...]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class PromptRegistryRuntime:
    default_version: str
    profiles_by_version: dict[str, PromptSetProfile]

    def list_profiles(self) -> list[PromptSetProfile]:
        return [self.profiles_by_version[key] for key in sorted(self.profiles_by_version.keys())]

    def get_profile(self, version: str) -> PromptSetProfile | None:
        key = str(version or "").strip()
        if not key:
            return None
        return self.profiles_by_version.get(key)

    @staticmethod
    def serialize_profile(profile: PromptSetProfile) -> dict[str, Any]:
        return {
            "version": profile.version,
            "promptVersions": dict(profile.prompt_versions),
            "metadata": dict(profile.metadata),
        }

    @staticmethod
    def build_trace_snapshot(profile: PromptSetProfile) -> dict[str, Any]:
        return {
            "version": profile.version,
            "promptVersions": dict(profile.prompt_versions),
        }


@dataclass(frozen=True)
class ToolRegistryRuntime:
    default_version: str
    profiles_by_version: dict[str, ToolsetProfile]

    def list_profiles(self) -> list[ToolsetProfile]:
        return [self.profiles_by_version[key] for key in sorted(self.profiles_by_version.keys())]

    def get_profile(self, version: str) -> ToolsetProfile | None:
        key = str(version or "").strip()
        if not key:
            return None
        return self.profiles_by_version.get(key)

    @staticmethod
    def serialize_profile(profile: ToolsetProfile) -> dict[str, Any]:
        return {
            "version": profile.version,
            "toolIds": list(profile.tool_ids),
            "metadata": dict(profile.metadata),
        }

    @staticmethod
    def build_trace_snapshot(profile: ToolsetProfile) -> dict[str, Any]:
        return {
            "version": profile.version,
            "toolIds": list(profile.tool_ids),
        }


def _normalize_prompt_versions(raw: Any, defaults: dict[str, str]) -> dict[str, str]:
    source = raw if isinstance(raw, dict) else {}
    normalized = {
        "summaryPromptVersion": str(
            source.get("summaryPromptVersion")
            or source.get("summary_prompt_version")
            or defaults["summaryPromptVersion"]
        ).strip(),
        "agent2PromptVersion": str(
            source.get("agent2PromptVersion")
            or source.get("agent2_prompt_version")
            or defaults["agent2PromptVersion"]
        ).strip(),
        "finalPipelineVersion": str(
            source.get("finalPipelineVersion")
            or source.get("final_pipeline_version")
            or defaults["finalPipelineVersion"]
        ).strip(),
        "claimGraphVersion": str(
            source.get("claimGraphVersion")
            or source.get("claim_graph_version")
            or defaults["claimGraphVersion"]
        ).strip(),
    }
    return {key: (value or defaults[key]) for key, value in normalized.items()}


def _normalize_tool_ids(raw: Any, defaults: tuple[str, ...]) -> tuple[str, ...]:
    values = raw if isinstance(raw, list) else list(defaults)
    out: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return tuple(out or defaults)


def _normalize_prompt_profiles(raw_profiles: Any, *, default_version: str) -> list[PromptSetProfile]:
    fallback = [
        PromptSetProfile(
            version=default_version,
            prompt_versions=dict(DEFAULT_PROMPT_VERSIONS),
            metadata={"status": "active", "source": "builtin"},
        )
    ]
    if not isinstance(raw_profiles, list):
        return fallback

    entries: list[PromptSetProfile] = []
    seen_versions: set[str] = set()
    for row in raw_profiles:
        if not isinstance(row, dict):
            continue
        version = str(row.get("version") or "").strip()
        if not version or version in seen_versions:
            continue
        seen_versions.add(version)
        prompt_versions = _normalize_prompt_versions(
            row.get("promptVersions") or row.get("prompt_versions"),
            defaults=DEFAULT_PROMPT_VERSIONS,
        )
        metadata = dict(row.get("metadata")) if isinstance(row.get("metadata"), dict) else {}
        metadata.setdefault("status", "active")
        metadata.setdefault("source", "env")
        entries.append(
            PromptSetProfile(
                version=version,
                prompt_versions=prompt_versions,
                metadata=metadata,
            )
        )
    return entries or fallback


def _normalize_tool_profiles(raw_profiles: Any, *, default_version: str) -> list[ToolsetProfile]:
    fallback = [
        ToolsetProfile(
            version=default_version,
            tool_ids=DEFAULT_TOOL_IDS,
            metadata={"status": "active", "source": "builtin"},
        )
    ]
    if not isinstance(raw_profiles, list):
        return fallback

    entries: list[ToolsetProfile] = []
    seen_versions: set[str] = set()
    for row in raw_profiles:
        if not isinstance(row, dict):
            continue
        version = str(row.get("version") or "").strip()
        if not version or version in seen_versions:
            continue
        seen_versions.add(version)
        tool_ids = _normalize_tool_ids(
            row.get("toolIds") or row.get("tool_ids"),
            defaults=DEFAULT_TOOL_IDS,
        )
        metadata = dict(row.get("metadata")) if isinstance(row.get("metadata"), dict) else {}
        metadata.setdefault("status", "active")
        metadata.setdefault("source", "env")
        entries.append(
            ToolsetProfile(
                version=version,
                tool_ids=tool_ids,
                metadata=metadata,
            )
        )
    return entries or fallback


def build_prompt_registry_runtime(*, settings: Any) -> PromptRegistryRuntime:
    default_version = (
        str(getattr(settings, "prompt_registry_default_version", DEFAULT_PROMPT_REGISTRY_VERSION)).strip()
        or DEFAULT_PROMPT_REGISTRY_VERSION
    )
    raw_text = str(getattr(settings, "prompt_registry_json", "") or "").strip()
    raw_profiles: Any = None
    if raw_text:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            raw_profiles = parsed.get("profiles")
            maybe_default = str(
                parsed.get("defaultVersion") or parsed.get("default_version") or ""
            ).strip()
            if maybe_default:
                default_version = maybe_default
        elif isinstance(parsed, list):
            raw_profiles = parsed
    profiles = _normalize_prompt_profiles(raw_profiles, default_version=default_version)
    profiles_by_version = {item.version: item for item in profiles}
    if default_version not in profiles_by_version:
        default_version = profiles[0].version
    return PromptRegistryRuntime(
        default_version=default_version,
        profiles_by_version=profiles_by_version,
    )


def build_tool_registry_runtime(*, settings: Any) -> ToolRegistryRuntime:
    default_version = (
        str(getattr(settings, "tool_registry_default_version", DEFAULT_TOOL_REGISTRY_VERSION)).strip()
        or DEFAULT_TOOL_REGISTRY_VERSION
    )
    raw_text = str(getattr(settings, "tool_registry_json", "") or "").strip()
    raw_profiles: Any = None
    if raw_text:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            raw_profiles = parsed.get("profiles")
            maybe_default = str(
                parsed.get("defaultVersion") or parsed.get("default_version") or ""
            ).strip()
            if maybe_default:
                default_version = maybe_default
        elif isinstance(parsed, list):
            raw_profiles = parsed
    profiles = _normalize_tool_profiles(raw_profiles, default_version=default_version)
    profiles_by_version = {item.version: item for item in profiles}
    if default_version not in profiles_by_version:
        default_version = profiles[0].version
    return ToolRegistryRuntime(
        default_version=default_version,
        profiles_by_version=profiles_by_version,
    )

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .registry_runtime import (
    DEFAULT_PROMPT_REGISTRY_VERSION,
    DEFAULT_PROMPT_VERSIONS,
    DEFAULT_TOOL_IDS,
    DEFAULT_TOOL_REGISTRY_VERSION,
)


@dataclass(frozen=True)
class JudgePolicyProfile:
    version: str
    rubric_version: str
    topic_domain: str
    prompt_registry_version: str
    tool_registry_version: str
    prompt_versions: dict[str, str]
    tool_ids: tuple[str, ...]
    fairness_thresholds: dict[str, Any]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class PolicyValidationResult:
    profile: JudgePolicyProfile | None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class PolicyRegistryRuntime:
    default_version: str
    profiles_by_version: dict[str, JudgePolicyProfile]

    def list_profiles(self) -> list[JudgePolicyProfile]:
        return [self.profiles_by_version[key] for key in sorted(self.profiles_by_version.keys())]

    def get_profile(self, version: str) -> JudgePolicyProfile | None:
        key = str(version or "").strip()
        if not key:
            return None
        return self.profiles_by_version.get(key)

    def resolve(self, *, requested_version: str, rubric_version: str, topic_domain: str) -> PolicyValidationResult:
        profile = self.get_profile(requested_version)
        if profile is None:
            return PolicyValidationResult(
                profile=None,
                error_code="unknown_judge_policy_version",
                error_message=f"policy version '{requested_version}' is not registered",
            )
        request_rubric = str(rubric_version or "").strip()
        if request_rubric and request_rubric != profile.rubric_version:
            return PolicyValidationResult(
                profile=None,
                error_code="judge_policy_rubric_mismatch",
                error_message=(
                    f"policy '{profile.version}' requires rubric '{profile.rubric_version}', "
                    f"got '{request_rubric}'"
                ),
            )
        profile_topic = str(profile.topic_domain or "").strip().lower()
        request_topic = str(topic_domain or "").strip().lower()
        if profile_topic and profile_topic not in {"*", request_topic}:
            return PolicyValidationResult(
                profile=None,
                error_code="judge_policy_topic_domain_mismatch",
                error_message=(
                    f"policy '{profile.version}' requires topic_domain '{profile.topic_domain}', "
                    f"got '{topic_domain}'"
                ),
            )
        return PolicyValidationResult(profile=profile)

    @staticmethod
    def serialize_profile(profile: JudgePolicyProfile) -> dict[str, Any]:
        return {
            "version": profile.version,
            "rubricVersion": profile.rubric_version,
            "topicDomain": profile.topic_domain,
            "promptRegistryVersion": profile.prompt_registry_version,
            "toolRegistryVersion": profile.tool_registry_version,
            "promptVersions": dict(profile.prompt_versions),
            "toolIds": list(profile.tool_ids),
            "fairnessThresholds": dict(profile.fairness_thresholds),
            "metadata": dict(profile.metadata),
        }

    @staticmethod
    def build_trace_snapshot(profile: JudgePolicyProfile) -> dict[str, Any]:
        return {
            "version": profile.version,
            "rubricVersion": profile.rubric_version,
            "topicDomain": profile.topic_domain,
            "promptRegistryVersion": profile.prompt_registry_version,
            "toolRegistryVersion": profile.tool_registry_version,
            "promptVersions": dict(profile.prompt_versions),
            "toolIds": list(profile.tool_ids),
            "fairnessThresholds": dict(profile.fairness_thresholds),
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
    return {
        key: (value or defaults[key])
        for key, value in normalized.items()
    }


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


def _normalize_profiles(raw_profiles: Any, *, default_version: str) -> list[JudgePolicyProfile]:
    default_thresholds = {
        "drawRateMax": 0.30,
        "sideBiasDeltaMax": 0.08,
        "appealOverturnRateMax": 0.12,
        "evidenceMinTotalRefs": 4,
        "evidenceMinDecisiveRefs": 2,
        "evidenceMinWinnerSupportRefs": 1,
        "evidenceConflictRatioMax": 0.65,
    }
    fallback = [
        JudgePolicyProfile(
            version=default_version,
            rubric_version="v3",
            topic_domain="*",
            prompt_registry_version=DEFAULT_PROMPT_REGISTRY_VERSION,
            tool_registry_version=DEFAULT_TOOL_REGISTRY_VERSION,
            prompt_versions=dict(DEFAULT_PROMPT_VERSIONS),
            tool_ids=DEFAULT_TOOL_IDS,
            fairness_thresholds=default_thresholds,
            metadata={"status": "active", "source": "builtin"},
        )
    ]
    if not isinstance(raw_profiles, list):
        return fallback

    entries: list[JudgePolicyProfile] = []
    seen_versions: set[str] = set()
    for row in raw_profiles:
        if not isinstance(row, dict):
            continue
        version = str(row.get("version") or "").strip()
        if not version or version in seen_versions:
            continue
        seen_versions.add(version)
        rubric_version = str(
            row.get("rubricVersion") or row.get("rubric_version") or "v3"
        ).strip() or "v3"
        topic_domain = str(
            row.get("topicDomain") or row.get("topic_domain") or "*"
        ).strip() or "*"
        prompt_registry_version = str(
            row.get("promptRegistryVersion")
            or row.get("prompt_registry_version")
            or DEFAULT_PROMPT_REGISTRY_VERSION
        ).strip() or DEFAULT_PROMPT_REGISTRY_VERSION
        tool_registry_version = str(
            row.get("toolRegistryVersion")
            or row.get("tool_registry_version")
            or DEFAULT_TOOL_REGISTRY_VERSION
        ).strip() or DEFAULT_TOOL_REGISTRY_VERSION
        prompt_versions = _normalize_prompt_versions(
            row.get("promptVersions") or row.get("prompt_versions"),
            defaults=DEFAULT_PROMPT_VERSIONS,
        )
        tool_ids = _normalize_tool_ids(
            row.get("toolIds") or row.get("tool_ids"),
            defaults=DEFAULT_TOOL_IDS,
        )
        fairness_thresholds = (
            dict(row.get("fairnessThresholds"))
            if isinstance(row.get("fairnessThresholds"), dict)
            else dict(default_thresholds)
        )
        metadata = dict(row.get("metadata")) if isinstance(row.get("metadata"), dict) else {}
        metadata.setdefault("status", "active")
        metadata.setdefault("source", "env")
        entries.append(
            JudgePolicyProfile(
                version=version,
                rubric_version=rubric_version,
                topic_domain=topic_domain,
                prompt_registry_version=prompt_registry_version,
                tool_registry_version=tool_registry_version,
                prompt_versions=prompt_versions,
                tool_ids=tool_ids,
                fairness_thresholds=fairness_thresholds,
                metadata=metadata,
            )
        )
    return entries or fallback


def build_policy_registry_runtime(*, settings: Any) -> PolicyRegistryRuntime:
    default_version = str(getattr(settings, "policy_registry_default_version", "v3-default")).strip() or "v3-default"
    raw_text = str(getattr(settings, "policy_registry_json", "") or "").strip()
    raw_profiles: Any = None
    if raw_text:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            raw_profiles = parsed.get("profiles")
            maybe_default = str(parsed.get("defaultVersion") or parsed.get("default_version") or "").strip()
            if maybe_default:
                default_version = maybe_default
        elif isinstance(parsed, list):
            raw_profiles = parsed
    profiles = _normalize_profiles(raw_profiles, default_version=default_version)
    profiles_by_version = {item.version: item for item in profiles}
    if default_version not in profiles_by_version:
        default_version = profiles[0].version
    return PolicyRegistryRuntime(
        default_version=default_version,
        profiles_by_version=profiles_by_version,
    )

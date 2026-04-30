from __future__ import annotations

from typing import Any

from ..domain.agents import (
    AGENT_KIND_NPC_COACH,
    AGENT_KIND_ROOM_QA,
    AgentKind,
)
from .assistant_advisory_contract import (
    AssistantAdvisoryContractViolation,
    validate_assistant_advisory_raw_output,
)

ASSISTANT_LLM_OUTPUT_CONTRACT_VERSION = "assistant_llm_output_contract_v1"
ASSISTANT_LLM_OUTPUT_ALLOWED_KEYS = frozenset(
    {
        "safeGuidanceSummary",
        "suggestedNextQuestions",
        "contextCaveats",
        "nextStepChecklist",
        "sourceUsePolicy",
    }
)
ASSISTANT_LLM_PUBLIC_OUTPUT_KEYS = frozenset(
    {
        "kind",
        "accepted",
        "mode",
        "advisoryOnly",
        "traceId",
        "policyIsolation",
        "llmOutputContractVersion",
        *ASSISTANT_LLM_OUTPUT_ALLOWED_KEYS,
    }
)
ASSISTANT_LLM_OUTPUT_FORBIDDEN_FIELD_NAMES = (
    "winner",
    "verdictReason",
    "proScore",
    "conScore",
    "dimensionScores",
    "fairnessGate",
    "trustAttestation",
    "rawPrompt",
    "rawTrace",
    "providerConfig",
    "officialVerdictAuthority",
    "writesVerdictLedger",
)
_VALID_ASSISTANT_LLM_AGENT_KINDS = frozenset(
    {
        AGENT_KIND_NPC_COACH,
        AGENT_KIND_ROOM_QA,
    }
)
_MAX_SUMMARY_CHARS = 1200
_MAX_TEXT_ITEM_CHARS = 320
_MAX_SOURCE_POLICY_CHARS = 600
_MAX_LIST_ITEMS = 5


def _ensure_dict(payload: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise AssistantAdvisoryContractViolation(
            f"assistant_llm_output_contract_{path}_not_object"
        )
    return payload


def _ensure_exact_keys(payload: dict[str, Any], *, expected_keys: frozenset[str]) -> None:
    actual_keys = set(payload.keys())
    if actual_keys != expected_keys:
        extra = sorted(actual_keys - expected_keys)
        missing = sorted(expected_keys - actual_keys)
        raise AssistantAdvisoryContractViolation(
            f"assistant_llm_output_contract_keys:extra={extra}:missing={missing}"
        )


def _normalize_required_text(value: Any, *, path: str, max_chars: int) -> str:
    if not isinstance(value, str):
        raise AssistantAdvisoryContractViolation(
            f"assistant_llm_output_contract_{path}_not_string"
        )
    normalized = value.strip()
    if not normalized:
        raise AssistantAdvisoryContractViolation(
            f"assistant_llm_output_contract_{path}_empty"
        )
    if len(normalized) > max_chars:
        raise AssistantAdvisoryContractViolation(
            f"assistant_llm_output_contract_{path}_too_long"
        )
    return normalized


def _normalize_text_list(value: Any, *, path: str) -> list[str]:
    if not isinstance(value, list):
        raise AssistantAdvisoryContractViolation(
            f"assistant_llm_output_contract_{path}_not_list"
        )
    if len(value) > _MAX_LIST_ITEMS:
        raise AssistantAdvisoryContractViolation(
            f"assistant_llm_output_contract_{path}_too_many_items"
        )
    normalized: list[str] = []
    for index, item in enumerate(value):
        normalized.append(
            _normalize_required_text(
                item,
                path=f"{path}_{index}",
                max_chars=_MAX_TEXT_ITEM_CHARS,
            )
        )
    return normalized


def normalize_assistant_llm_output(payload: Any) -> dict[str, Any]:
    validate_assistant_advisory_raw_output(payload)
    output = _ensure_dict(payload, path="payload")
    _ensure_exact_keys(output, expected_keys=ASSISTANT_LLM_OUTPUT_ALLOWED_KEYS)
    return {
        "safeGuidanceSummary": _normalize_required_text(
            output.get("safeGuidanceSummary"),
            path="safe_guidance_summary",
            max_chars=_MAX_SUMMARY_CHARS,
        ),
        "suggestedNextQuestions": _normalize_text_list(
            output.get("suggestedNextQuestions"),
            path="suggested_next_questions",
        ),
        "contextCaveats": _normalize_text_list(
            output.get("contextCaveats"),
            path="context_caveats",
        ),
        "nextStepChecklist": _normalize_text_list(
            output.get("nextStepChecklist"),
            path="next_step_checklist",
        ),
        "sourceUsePolicy": _normalize_required_text(
            output.get("sourceUsePolicy"),
            path="source_use_policy",
            max_chars=_MAX_SOURCE_POLICY_CHARS,
        ),
    }


def build_assistant_llm_public_output(
    *,
    agent_kind: AgentKind,
    trace_id: str | None,
    raw_output: Any,
) -> dict[str, Any]:
    if agent_kind not in _VALID_ASSISTANT_LLM_AGENT_KINDS:
        raise AssistantAdvisoryContractViolation(
            "assistant_llm_output_contract_agent_kind_invalid"
        )
    normalized = normalize_assistant_llm_output(raw_output)
    return {
        "kind": agent_kind,
        "accepted": True,
        "mode": "advisory_only",
        "advisoryOnly": True,
        "traceId": trace_id,
        "policyIsolation": "assistant_advisory_policy",
        "llmOutputContractVersion": ASSISTANT_LLM_OUTPUT_CONTRACT_VERSION,
        **normalized,
    }


def validate_assistant_llm_public_output(payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    if "llmOutputContractVersion" not in payload:
        return
    validate_assistant_advisory_raw_output(payload)
    _ensure_exact_keys(payload, expected_keys=ASSISTANT_LLM_PUBLIC_OUTPUT_KEYS)
    if payload.get("llmOutputContractVersion") != ASSISTANT_LLM_OUTPUT_CONTRACT_VERSION:
        raise AssistantAdvisoryContractViolation(
            "assistant_llm_output_contract_version_mismatch"
        )
    if payload.get("kind") not in _VALID_ASSISTANT_LLM_AGENT_KINDS:
        raise AssistantAdvisoryContractViolation(
            "assistant_llm_output_contract_agent_kind_invalid"
        )
    if payload.get("accepted") is not True:
        raise AssistantAdvisoryContractViolation(
            "assistant_llm_output_contract_accepted_invalid"
        )
    if payload.get("mode") != "advisory_only" or payload.get("advisoryOnly") is not True:
        raise AssistantAdvisoryContractViolation(
            "assistant_llm_output_contract_not_advisory_only"
        )
    if payload.get("policyIsolation") != "assistant_advisory_policy":
        raise AssistantAdvisoryContractViolation(
            "assistant_llm_output_contract_policy_isolation_invalid"
        )
    normalize_assistant_llm_output(
        {
            key: payload.get(key)
            for key in sorted(ASSISTANT_LLM_OUTPUT_ALLOWED_KEYS)
        }
    )

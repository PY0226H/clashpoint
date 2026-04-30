from __future__ import annotations

from typing import Any

from ..domain.agents import ROLE_CHIEF_ARBITER, ROLE_FAIRNESS_SENTINEL

ASSISTANT_ADVISORY_CONTRACT_VERSION = "assistant_advisory_contract_v1"

ASSISTANT_ADVISORY_TOP_LEVEL_KEYS = frozenset(
    {
        "version",
        "agentKind",
        "sessionId",
        "caseId",
        "advisoryOnly",
        "status",
        "accepted",
        "errorCode",
        "errorMessage",
        "capabilityBoundary",
        "sharedContext",
        "advisoryContext",
        "output",
        "cacheProfile",
    }
)

ASSISTANT_ADVISORY_ALLOWED_CONTEXT_SOURCES: tuple[str, ...] = (
    "room_context_snapshot",
    "stage_summary",
    "knowledge_gateway",
)
ASSISTANT_ADVISORY_FORBIDDEN_WRITE_TARGETS: tuple[str, ...] = (
    "verdict_ledger",
    "judge_trace",
    "fairness_report",
    "official_review_queue",
)
ASSISTANT_ADVISORY_FORBIDDEN_OFFICIAL_ROLES: tuple[str, ...] = (
    ROLE_FAIRNESS_SENTINEL,
    ROLE_CHIEF_ARBITER,
)

_ASSISTANT_ADVISORY_PUBLIC_FORBIDDEN_KEYS = frozenset(
    {
        "winner",
        "verdictreason",
        "verdictledger",
        "fairnessgate",
        "trustattestation",
        "rawprompt",
        "rawtrace",
        "artifactref",
        "artifactrefs",
        "providerconfig",
    }
)

_ASSISTANT_ADVISORY_OUTPUT_FORBIDDEN_KEYS = frozenset(
    {
        *_ASSISTANT_ADVISORY_PUBLIC_FORBIDDEN_KEYS,
        "proscore",
        "conscore",
        "dimensionscores",
        "verdictevidencerefs",
        "auditalerts",
        "errorcodes",
        "degradationlevel",
        "debatesummary",
        "sideanalysis",
        "finalrationale",
        "fairnesssummary",
        "needsdrawvote",
        "reviewrequired",
        "dispatchtype",
        "judgepolicyversion",
        "rubricversion",
        "ruleversion",
        "officialverdictauthority",
        "writesverdictledger",
        "writesjudgetrace",
        "cantriggerofficialjudgeroles",
    }
)


class AssistantAdvisoryContractViolation(ValueError):
    pass


def _normalize_advisory_key(key: str) -> str:
    return "".join(char for char in key.lower() if char.isalnum())


def _find_forbidden_key(
    payload: Any,
    *,
    forbidden_keys: frozenset[str],
    path: str,
) -> str | None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            child_path = f"{path}.{key}" if path else str(key)
            if isinstance(key, str) and _normalize_advisory_key(key) in forbidden_keys:
                return child_path
            found = _find_forbidden_key(
                value,
                forbidden_keys=forbidden_keys,
                path=child_path,
            )
            if found is not None:
                return found
    if isinstance(payload, list):
        for index, item in enumerate(payload):
            found = _find_forbidden_key(
                item,
                forbidden_keys=forbidden_keys,
                path=f"{path}[{index}]",
            )
            if found is not None:
                return found
    return None


def sanitize_assistant_advisory_output(payload: Any) -> Any:
    if isinstance(payload, dict):
        sanitized: dict[Any, Any] = {}
        for key, value in payload.items():
            if (
                isinstance(key, str)
                and _normalize_advisory_key(key)
                in _ASSISTANT_ADVISORY_OUTPUT_FORBIDDEN_KEYS
            ):
                continue
            sanitized[key] = sanitize_assistant_advisory_output(value)
        return sanitized
    if isinstance(payload, list):
        return [sanitize_assistant_advisory_output(item) for item in payload]
    return payload


def validate_assistant_advisory_raw_output(payload: Any) -> None:
    found = _find_forbidden_key(
        payload,
        forbidden_keys=_ASSISTANT_ADVISORY_OUTPUT_FORBIDDEN_KEYS,
        path="output",
    )
    if found is not None:
        raise AssistantAdvisoryContractViolation(
            f"assistant_advisory_forbidden_output_key:{found}"
        )


def build_assistant_advisory_cache_profile() -> dict[str, Any]:
    return {
        "cacheable": False,
        "ttlSeconds": 0,
        "scope": "per_request",
    }


def _validate_dict_field(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise AssistantAdvisoryContractViolation(
            f"assistant_advisory_contract_{key}_not_object"
        )
    return value


def validate_assistant_advisory_contract(payload: dict[str, Any]) -> None:
    actual_keys = set(payload.keys())
    if actual_keys != ASSISTANT_ADVISORY_TOP_LEVEL_KEYS:
        extra_keys = sorted(actual_keys - ASSISTANT_ADVISORY_TOP_LEVEL_KEYS)
        missing_keys = sorted(ASSISTANT_ADVISORY_TOP_LEVEL_KEYS - actual_keys)
        raise AssistantAdvisoryContractViolation(
            "assistant_advisory_contract_top_level_keys:"
            f"extra={extra_keys}:missing={missing_keys}"
        )

    if payload.get("version") != ASSISTANT_ADVISORY_CONTRACT_VERSION:
        raise AssistantAdvisoryContractViolation(
            "assistant_advisory_contract_version_mismatch"
        )
    if payload.get("advisoryOnly") is not True:
        raise AssistantAdvisoryContractViolation(
            "assistant_advisory_contract_not_advisory_only"
        )
    if not isinstance(payload.get("sessionId"), int) or payload["sessionId"] <= 0:
        raise AssistantAdvisoryContractViolation(
            "assistant_advisory_contract_invalid_session_id"
        )
    if not isinstance(payload.get("accepted"), bool):
        raise AssistantAdvisoryContractViolation(
            "assistant_advisory_contract_accepted_not_bool"
        )

    capability_boundary = _validate_dict_field(payload, "capabilityBoundary")
    expected_boundary = {
        "mode": "advisory_only",
        "officialVerdictAuthority": False,
        "writesVerdictLedger": False,
        "writesJudgeTrace": False,
        "canTriggerOfficialJudgeRoles": False,
    }
    for key, expected_value in expected_boundary.items():
        actual_value = capability_boundary.get(key)
        if isinstance(expected_value, bool):
            matches_boundary = actual_value is expected_value
        else:
            matches_boundary = actual_value == expected_value
        if not matches_boundary:
            raise AssistantAdvisoryContractViolation(
                f"assistant_advisory_contract_capability_boundary:{key}"
            )
    if capability_boundary.get("advisoryOnly") is not True:
        raise AssistantAdvisoryContractViolation(
            "assistant_advisory_contract_capability_boundary:advisoryOnly"
        )

    output = _validate_dict_field(payload, "output")
    for key in ("sharedContext", "advisoryContext"):
        found = _find_forbidden_key(
            _validate_dict_field(payload, key),
            forbidden_keys=_ASSISTANT_ADVISORY_PUBLIC_FORBIDDEN_KEYS,
            path=key,
        )
        if found is not None:
            raise AssistantAdvisoryContractViolation(
                f"assistant_advisory_forbidden_public_key:{found}"
            )
    validate_assistant_advisory_raw_output(output)

    cache_profile = _validate_dict_field(payload, "cacheProfile")
    if cache_profile.get("cacheable") is not False or cache_profile.get("ttlSeconds") != 0:
        raise AssistantAdvisoryContractViolation(
            "assistant_advisory_contract_cache_profile_not_disabled"
        )

    if payload.get("status") == "not_ready":
        if payload.get("accepted") is not False:
            raise AssistantAdvisoryContractViolation(
                "assistant_advisory_contract_not_ready_accepted"
            )
        if payload.get("errorCode") != "agent_not_enabled":
            raise AssistantAdvisoryContractViolation(
                "assistant_advisory_contract_not_ready_error_code"
            )

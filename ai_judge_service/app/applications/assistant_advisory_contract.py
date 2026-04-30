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
ASSISTANT_ROOM_CONTEXT_SNAPSHOT_KEYS = frozenset(
    {
        "sessionId",
        "scopeId",
        "caseId",
        "workflowStatus",
        "latestDispatchType",
        "topicDomain",
        "phaseReceiptCount",
        "finalReceiptCount",
        "updatedAt",
        "officialVerdictFieldsRedacted",
    }
)
ASSISTANT_STAGE_SUMMARY_KEYS = frozenset(
    {
        "stage",
        "workflowStatus",
        "latestDispatchType",
        "hasPhaseReceipt",
        "hasFinalReceipt",
        "officialVerdictFieldsRedacted",
    }
)
ASSISTANT_CONTEXT_VERSION_KEYS = frozenset(
    {
        "ruleVersion",
        "rubricVersion",
        "judgePolicyVersion",
    }
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
ASSISTANT_ADVISORY_NOT_READY_ERROR_CODES = frozenset(
    {
        "agent_not_enabled",
        "assistant_executor_not_configured",
    }
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


def _validate_exact_keys(
    payload: dict[str, Any],
    *,
    expected_keys: frozenset[str],
    path: str,
) -> None:
    actual_keys = set(payload.keys())
    if actual_keys != expected_keys:
        extra_keys = sorted(actual_keys - expected_keys)
        missing_keys = sorted(expected_keys - actual_keys)
        raise AssistantAdvisoryContractViolation(
            f"assistant_advisory_contract_{path}_keys:"
            f"extra={extra_keys}:missing={missing_keys}"
        )


def _validate_optional_token(
    value: Any,
    *,
    path: str,
    allowed_values: frozenset[str] | None = None,
) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise AssistantAdvisoryContractViolation(
            f"assistant_advisory_contract_{path}_not_string"
        )
    if allowed_values is not None and value not in allowed_values:
        raise AssistantAdvisoryContractViolation(
            f"assistant_advisory_contract_{path}_invalid"
        )


def _validate_required_token(
    value: Any,
    *,
    path: str,
    allowed_values: frozenset[str] | None = None,
) -> None:
    if not isinstance(value, str):
        raise AssistantAdvisoryContractViolation(
            f"assistant_advisory_contract_{path}_not_string"
        )
    if allowed_values is not None and value not in allowed_values:
        raise AssistantAdvisoryContractViolation(
            f"assistant_advisory_contract_{path}_invalid"
        )


def _validate_non_negative_int(value: Any, *, path: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AssistantAdvisoryContractViolation(
            f"assistant_advisory_contract_{path}_invalid"
        )


def _validate_room_context_snapshot(
    payload: dict[str, Any],
    *,
    expected_session_id: int,
) -> None:
    _validate_exact_keys(
        payload,
        expected_keys=ASSISTANT_ROOM_CONTEXT_SNAPSHOT_KEYS,
        path="room_context_snapshot",
    )
    if payload.get("sessionId") != expected_session_id:
        raise AssistantAdvisoryContractViolation(
            "assistant_advisory_contract_room_context_snapshot_session_mismatch"
        )
    _validate_non_negative_int(payload.get("scopeId"), path="room_context_snapshot_scope_id")
    if payload.get("caseId") is not None:
        _validate_non_negative_int(
            payload.get("caseId"),
            path="room_context_snapshot_case_id",
        )
    _validate_optional_token(
        payload.get("workflowStatus"),
        path="room_context_snapshot_workflow_status",
    )
    _validate_optional_token(
        payload.get("latestDispatchType"),
        path="room_context_snapshot_latest_dispatch_type",
        allowed_values=frozenset({"phase", "final"}),
    )
    _validate_optional_token(
        payload.get("topicDomain"),
        path="room_context_snapshot_topic_domain",
    )
    _validate_optional_token(
        payload.get("updatedAt"),
        path="room_context_snapshot_updated_at",
    )
    _validate_non_negative_int(
        payload.get("phaseReceiptCount"),
        path="room_context_snapshot_phase_receipt_count",
    )
    _validate_non_negative_int(
        payload.get("finalReceiptCount"),
        path="room_context_snapshot_final_receipt_count",
    )
    if payload.get("officialVerdictFieldsRedacted") is not True:
        raise AssistantAdvisoryContractViolation(
            "assistant_advisory_contract_room_context_snapshot_not_redacted"
        )


def _validate_stage_summary(payload: dict[str, Any]) -> None:
    _validate_exact_keys(
        payload,
        expected_keys=ASSISTANT_STAGE_SUMMARY_KEYS,
        path="stage_summary",
    )
    _validate_required_token(
        payload.get("stage"),
        path="stage_summary_stage",
        allowed_values=frozenset(
            {
                "room_context_only",
                "phase_context_available",
                "final_context_available",
            }
        ),
    )
    _validate_optional_token(
        payload.get("workflowStatus"),
        path="stage_summary_workflow_status",
    )
    _validate_optional_token(
        payload.get("latestDispatchType"),
        path="stage_summary_latest_dispatch_type",
        allowed_values=frozenset({"phase", "final"}),
    )
    if not isinstance(payload.get("hasPhaseReceipt"), bool):
        raise AssistantAdvisoryContractViolation(
            "assistant_advisory_contract_stage_summary_has_phase_receipt"
        )
    if not isinstance(payload.get("hasFinalReceipt"), bool):
        raise AssistantAdvisoryContractViolation(
            "assistant_advisory_contract_stage_summary_has_final_receipt"
        )
    if payload.get("officialVerdictFieldsRedacted") is not True:
        raise AssistantAdvisoryContractViolation(
            "assistant_advisory_contract_stage_summary_not_redacted"
        )


def _validate_context_version(payload: Any) -> None:
    if payload is None:
        return
    if not isinstance(payload, dict):
        raise AssistantAdvisoryContractViolation(
            "assistant_advisory_contract_version_context_not_object"
        )
    _validate_exact_keys(
        payload,
        expected_keys=ASSISTANT_CONTEXT_VERSION_KEYS,
        path="version_context",
    )
    for key in ASSISTANT_CONTEXT_VERSION_KEYS:
        _validate_optional_token(payload.get(key), path=f"version_context_{key}")


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

    shared_context = _validate_dict_field(payload, "sharedContext")
    advisory_context = _validate_dict_field(payload, "advisoryContext")
    room_context_snapshot = _validate_dict_field(
        advisory_context,
        "roomContextSnapshot",
    )
    stage_summary = _validate_dict_field(advisory_context, "stageSummary")
    _validate_room_context_snapshot(
        shared_context,
        expected_session_id=payload["sessionId"],
    )
    _validate_room_context_snapshot(
        room_context_snapshot,
        expected_session_id=payload["sessionId"],
    )
    if shared_context != room_context_snapshot:
        raise AssistantAdvisoryContractViolation(
            "assistant_advisory_contract_room_context_snapshot_shared_mismatch"
        )
    _validate_stage_summary(stage_summary)
    _validate_context_version(advisory_context.get("versionContext"))

    output = _validate_dict_field(payload, "output")
    for key, context_payload in (
        ("sharedContext", shared_context),
        ("advisoryContext", advisory_context),
    ):
        found = _find_forbidden_key(
            context_payload,
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
        if payload.get("errorCode") not in ASSISTANT_ADVISORY_NOT_READY_ERROR_CODES:
            raise AssistantAdvisoryContractViolation(
                "assistant_advisory_contract_not_ready_error_code"
            )

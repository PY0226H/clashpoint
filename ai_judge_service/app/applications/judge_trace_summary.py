from __future__ import annotations

from typing import Any

from .judge_app_domain import JUDGE_ROLE_ORDER, validate_judge_app_domain_payload

TRACE_SUMMARY_REQUIRED_KEYS: tuple[str, ...] = (
    "dispatchType",
    "payload",
    "winner",
    "auditAlerts",
    "callbackStatus",
    "callbackError",
)
_WINNER_VALUES = {"pro", "con", "draw"}
_ROLE_NODE_STATUS_VALUES = {"completed", "pending"}
_ROLE_NODE_SECTION_BY_ROLE: dict[str, str] = {
    "clerk": "caseDossier",
    "recorder": "claimGraph",
    "claim_graph": "claimGraph",
    "evidence": "evidenceBundle",
    "panel": "panelBundle",
    "fairness_sentinel": "fairnessGate",
    "chief_arbiter": "verdict",
    "opinion_writer": "opinion",
}


def _required_keys_missing(payload: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    return [key for key in keys if key not in payload]


def _validate_role_nodes(role_nodes: list[Any]) -> None:
    if len(role_nodes) != len(JUDGE_ROLE_ORDER):
        raise ValueError("trace_report_summary_role_nodes_incomplete")
    for idx, expected_role in enumerate(JUDGE_ROLE_ORDER):
        row = role_nodes[idx]
        if not isinstance(row, dict):
            raise ValueError(f"trace_report_summary_role_node_not_dict:{idx}")
        if row.get("seq") != idx + 1:
            raise ValueError(f"trace_report_summary_role_node_seq_invalid:{idx}")
        role = str(row.get("role") or "").strip().lower()
        if role != expected_role:
            raise ValueError(f"trace_report_summary_role_node_role_order_invalid:{idx}")
        expected_section = _ROLE_NODE_SECTION_BY_ROLE.get(expected_role)
        if row.get("section") != expected_section:
            raise ValueError(f"trace_report_summary_role_node_section_invalid:{idx}")
        status = str(row.get("status") or "").strip().lower()
        if status not in _ROLE_NODE_STATUS_VALUES:
            raise ValueError(f"trace_report_summary_role_node_status_invalid:{idx}")


def validate_trace_report_summary_contract(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("trace_report_summary_not_dict")
    missing = _required_keys_missing(payload, TRACE_SUMMARY_REQUIRED_KEYS)
    if missing:
        raise ValueError(f"trace_report_summary_missing_keys:{','.join(sorted(missing))}")

    dispatch_type = str(payload.get("dispatchType") or "").strip().lower()
    if not dispatch_type:
        raise ValueError("trace_report_summary_dispatch_type_empty")
    report_payload = payload.get("payload")
    if not isinstance(report_payload, dict):
        raise ValueError("trace_report_summary_payload_not_dict")
    winner = payload.get("winner")
    if winner is not None and str(winner).strip().lower() not in _WINNER_VALUES:
        raise ValueError("trace_report_summary_winner_invalid")
    if not isinstance(payload.get("auditAlerts"), list):
        raise ValueError("trace_report_summary_audit_alerts_not_list")
    callback_status = payload.get("callbackStatus")
    if not isinstance(callback_status, str) or not callback_status.strip():
        raise ValueError("trace_report_summary_callback_status_invalid")
    callback_error = payload.get("callbackError")
    if callback_error is not None and not isinstance(callback_error, str):
        raise ValueError("trace_report_summary_callback_error_not_string")

    if dispatch_type in {"phase", "final"}:
        judge_workflow = payload.get("judgeWorkflow")
        if not isinstance(judge_workflow, dict):
            raise ValueError("trace_report_summary_judge_workflow_missing")
        validate_judge_app_domain_payload(judge_workflow)
        role_nodes = payload.get("roleNodes")
        if not isinstance(role_nodes, list) or not role_nodes:
            raise ValueError("trace_report_summary_role_nodes_missing")
        _validate_role_nodes(role_nodes)


def build_judge_workflow_role_nodes(judge_workflow: dict[str, Any]) -> list[dict[str, Any]]:
    root = (
        judge_workflow.get("judgeWorkflow")
        if isinstance(judge_workflow.get("judgeWorkflow"), dict)
        else {}
    )
    case_dossier = root.get("caseDossier") if isinstance(root.get("caseDossier"), dict) else {}
    role_order = case_dossier.get("roleOrder")
    if isinstance(role_order, list):
        role_order = [str(item or "").strip().lower() for item in role_order]
    else:
        role_order = list(JUDGE_ROLE_ORDER)

    out: list[dict[str, Any]] = []
    for idx, role in enumerate(role_order):
        role_key = str(role or "").strip().lower()
        if not role_key:
            continue
        section = _ROLE_NODE_SECTION_BY_ROLE.get(role_key)
        section_payload = root.get(section) if isinstance(section, str) else None
        has_payload = isinstance(section_payload, dict) and len(section_payload) > 0
        out.append(
            {
                "seq": idx + 1,
                "role": role_key,
                "section": section,
                "status": "completed" if has_payload else "pending",
            }
        )
    return out


def build_trace_report_summary(
    *,
    dispatch_type: str,
    payload: dict[str, Any] | None,
    callback_status: str,
    callback_error: str | None,
    judge_workflow: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report_payload = payload if isinstance(payload, dict) else {}
    alerts = report_payload.get("auditAlerts")
    if not isinstance(alerts, list):
        alerts = []
    winner = str(report_payload.get("winner") or "").strip().lower() or None
    out = {
        "dispatchType": dispatch_type,
        "payload": report_payload,
        "winner": winner,
        "auditAlerts": [item for item in alerts if isinstance(item, dict)],
        "callbackStatus": callback_status,
        "callbackError": callback_error,
    }
    if isinstance(judge_workflow, dict):
        out["judgeWorkflow"] = judge_workflow
        out["roleNodes"] = build_judge_workflow_role_nodes(judge_workflow)
    validate_trace_report_summary_contract(out)
    return out

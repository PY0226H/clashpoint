from __future__ import annotations

import json
from typing import Any

from ..domain.agents import AGENT_KIND_NPC_COACH, AGENT_KIND_ROOM_QA, AgentKind
from .assistant_advisory_output import (
    ASSISTANT_LLM_OUTPUT_ALLOWED_KEYS,
    ASSISTANT_LLM_OUTPUT_CONTRACT_VERSION,
    ASSISTANT_LLM_OUTPUT_FORBIDDEN_FIELD_NAMES,
)

ASSISTANT_ADVISORY_PROMPT_CONTRACT_VERSION = "assistant_advisory_prompt_contract_v1"

_NPC_COACH_SYSTEM_PROMPT = """You are EchoIsle NPC Coach.
You provide advisory-only debate coaching from redacted public room context.
Help the participant organize public arguments, find evidence gaps, and identify unanswered issues.
Do not predict winners, scores, official verdict reasons, fairness gates, or internal judge state.
Do not help evade rules, manipulate judges, attack identities, harass another participant, or fabricate evidence.
Return only the requested JSON object."""

_ROOM_QA_SYSTEM_PROMPT = """You are EchoIsle Room QA.
You answer questions about the room stage, public context, and redacted stage summary only.
If context is insufficient, say so plainly and suggest what public context is missing.
Do not expose official verdicts, internal audit traces, hidden judge feedback, scores, or final outcome predictions.
Return only the requested JSON object."""


def _policy_version_from_context(advisory_context: dict[str, Any]) -> str | None:
    knowledge_gateway = advisory_context.get("knowledgeGateway")
    if not isinstance(knowledge_gateway, dict):
        return None
    policy_binding = knowledge_gateway.get("policyBinding")
    if not isinstance(policy_binding, dict):
        return None
    value = policy_binding.get("policyVersion")
    normalized = str(value or "").strip()
    return normalized or None


def _json_for_prompt(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _output_schema_payload() -> dict[str, Any]:
    return {
        "version": ASSISTANT_LLM_OUTPUT_CONTRACT_VERSION,
        "type": "json_object",
        "requiredKeys": list(sorted(ASSISTANT_LLM_OUTPUT_ALLOWED_KEYS)),
        "fieldTypes": {
            "safeGuidanceSummary": "non_empty_string",
            "suggestedNextQuestions": "array_of_non_empty_strings",
            "contextCaveats": "array_of_non_empty_strings",
            "nextStepChecklist": "array_of_non_empty_strings",
            "sourceUsePolicy": "non_empty_string",
        },
        "forbiddenKeys": list(ASSISTANT_LLM_OUTPUT_FORBIDDEN_FIELD_NAMES),
    }


def build_assistant_advisory_prompt_bundle(
    *,
    agent_kind: AgentKind,
    advisory_context: dict[str, Any],
    user_text: str,
    side: str | None = None,
) -> dict[str, Any]:
    if agent_kind == AGENT_KIND_NPC_COACH:
        system_prompt = _NPC_COACH_SYSTEM_PROMPT
        task = {
            "agentKind": agent_kind,
            "task": "coach_participant_argument",
            "participantSide": side,
            "userQuery": user_text,
            "allowedGuidance": [
                "organize_public_arguments",
                "suggest_public_evidence_gaps",
                "identify_unanswered_public_issues",
            ],
        }
    elif agent_kind == AGENT_KIND_ROOM_QA:
        system_prompt = _ROOM_QA_SYSTEM_PROMPT
        task = {
            "agentKind": agent_kind,
            "task": "answer_room_context_question",
            "userQuestion": user_text,
            "allowedGuidance": [
                "explain_room_stage",
                "explain_redacted_stage_summary",
                "state_context_insufficient_when_needed",
            ],
        }
    else:
        raise ValueError("unsupported_assistant_agent_kind")

    output_schema = _output_schema_payload()
    user_prompt_payload = {
        "promptContractVersion": ASSISTANT_ADVISORY_PROMPT_CONTRACT_VERSION,
        "advisoryOnly": True,
        "policyVersion": _policy_version_from_context(advisory_context),
        "task": task,
        "redactedAdvisoryContext": advisory_context,
        "outputSchema": output_schema,
        "responseRules": [
            "Return exactly one JSON object.",
            "Use exactly the required keys in outputSchema.requiredKeys.",
            "Do not include forbiddenKeys anywhere in the JSON.",
            "Do not include markdown, prose outside JSON, provider config, raw prompt, or raw trace.",
        ],
    }
    return {
        "promptContractVersion": ASSISTANT_ADVISORY_PROMPT_CONTRACT_VERSION,
        "agentKind": agent_kind,
        "advisoryOnly": True,
        "policyVersion": _policy_version_from_context(advisory_context),
        "systemPrompt": system_prompt,
        "userPrompt": _json_for_prompt(user_prompt_payload),
        "outputSchema": output_schema,
    }

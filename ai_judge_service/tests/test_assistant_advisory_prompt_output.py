from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from app.applications.assistant_advisory_contract import (
    AssistantAdvisoryContractViolation,
)
from app.applications.assistant_advisory_output import (
    ASSISTANT_LLM_OUTPUT_ALLOWED_KEYS,
    ASSISTANT_LLM_OUTPUT_CONTRACT_VERSION,
    build_assistant_llm_public_output,
    normalize_assistant_llm_output,
)
from app.applications.assistant_advisory_prompt import (
    ASSISTANT_ADVISORY_PROMPT_CONTRACT_VERSION,
    build_assistant_advisory_prompt_bundle,
)
from app.applications.assistant_agent_routes import (
    AssistantAgentRouteError,
    build_assistant_agent_response,
)
from app.domain.agents import AGENT_KIND_NPC_COACH, AGENT_KIND_ROOM_QA


def _advisory_context(*, agent_kind: str = AGENT_KIND_NPC_COACH) -> dict:
    return {
        "advisoryOnly": True,
        "roomContextSnapshot": {
            "sessionId": 2001,
            "scopeId": 1,
            "caseId": 3001,
            "workflowStatus": "done",
            "latestDispatchType": "phase",
            "topicDomain": "public-policy",
            "phaseReceiptCount": 1,
            "finalReceiptCount": 0,
            "updatedAt": "2026-04-30T00:00:00Z",
            "officialVerdictFieldsRedacted": True,
        },
        "stageSummary": {
            "stage": "phase_context_available",
            "workflowStatus": "done",
            "latestDispatchType": "phase",
            "hasPhaseReceipt": True,
            "hasFinalReceipt": False,
            "officialVerdictFieldsRedacted": True,
        },
        "versionContext": {
            "ruleVersion": "rule-v1",
            "rubricVersion": "rubric-v1",
            "judgePolicyVersion": "judge-policy-v1",
        },
        "knowledgeGateway": {
            "useCase": agent_kind,
            "advisoryOnly": True,
            "policyBinding": {
                "policyVersion": f"{agent_kind}_advisory_policy_v1",
                "officialVerdictPolicy": False,
            },
        },
        "readPolicy": {
            "allowedSources": [
                "room_context_snapshot",
                "stage_summary",
                "knowledge_gateway",
            ],
            "forbiddenWriteTargets": ["verdict_ledger", "judge_trace"],
            "forbiddenOfficialRoles": ["fairness_sentinel", "chief_arbiter"],
            "officialJudgeFeedbackAllowed": False,
        },
    }


def _valid_llm_output() -> dict:
    return {
        "safeGuidanceSummary": "Focus on the public evidence gap and ask for one concrete citation.",
        "suggestedNextQuestions": [
            "Which claim needs the strongest public evidence?",
            "What did the other side leave unanswered?",
        ],
        "contextCaveats": ["Only redacted room context is available."],
        "nextStepChecklist": [
            "Restate the claim.",
            "Attach public evidence.",
            "Address the strongest counterpoint.",
        ],
        "sourceUsePolicy": "Use only room context, stage summary, and knowledge gateway snippets.",
    }


class AssistantAdvisoryPromptOutputTests(unittest.TestCase):
    def test_npc_prompt_bundle_should_freeze_advisory_schema(self) -> None:
        bundle = build_assistant_advisory_prompt_bundle(
            agent_kind=AGENT_KIND_NPC_COACH,
            advisory_context=_advisory_context(agent_kind=AGENT_KIND_NPC_COACH),
            user_text="How should I tighten my next argument?",
            side="pro",
        )

        self.assertEqual(
            bundle["promptContractVersion"],
            ASSISTANT_ADVISORY_PROMPT_CONTRACT_VERSION,
        )
        self.assertEqual(bundle["agentKind"], AGENT_KIND_NPC_COACH)
        self.assertTrue(bundle["advisoryOnly"])
        self.assertEqual(bundle["policyVersion"], "npc_coach_advisory_policy_v1")
        self.assertIn("Do not predict winners", bundle["systemPrompt"])
        self.assertEqual(
            set(bundle["outputSchema"]["requiredKeys"]),
            ASSISTANT_LLM_OUTPUT_ALLOWED_KEYS,
        )
        prompt_payload = json.loads(bundle["userPrompt"])
        self.assertEqual(prompt_payload["task"]["participantSide"], "pro")
        self.assertEqual(
            prompt_payload["outputSchema"]["version"],
            ASSISTANT_LLM_OUTPUT_CONTRACT_VERSION,
        )
        self.assertFalse(
            prompt_payload["redactedAdvisoryContext"]["knowledgeGateway"][
                "policyBinding"
            ]["officialVerdictPolicy"]
        )

    def test_room_qa_prompt_bundle_should_explain_context_without_verdict_authority(
        self,
    ) -> None:
        bundle = build_assistant_advisory_prompt_bundle(
            agent_kind=AGENT_KIND_ROOM_QA,
            advisory_context=_advisory_context(agent_kind=AGENT_KIND_ROOM_QA),
            user_text="What stage is the room in?",
        )

        prompt_payload = json.loads(bundle["userPrompt"])
        self.assertEqual(prompt_payload["task"]["task"], "answer_room_context_question")
        self.assertIn("If context is insufficient", bundle["systemPrompt"])
        self.assertIn("officialVerdictAuthority", bundle["outputSchema"]["forbiddenKeys"])
        self.assertEqual(
            prompt_payload["task"]["allowedGuidance"],
            [
                "explain_room_stage",
                "explain_redacted_stage_summary",
                "state_context_insufficient_when_needed",
            ],
        )

    def test_llm_output_should_build_public_output_and_outer_response(self) -> None:
        public_output = build_assistant_llm_public_output(
            agent_kind=AGENT_KIND_NPC_COACH,
            trace_id="trace-npc-llm",
            raw_output=_valid_llm_output(),
        )
        response = build_assistant_agent_response(
            agent_kind=AGENT_KIND_NPC_COACH,
            session_id=2001,
            advisory_context=_advisory_context(agent_kind=AGENT_KIND_NPC_COACH),
            execution_result=SimpleNamespace(
                status="ok",
                output=public_output,
                error_code=None,
                error_message=None,
            ),
        )

        self.assertEqual(response["status"], "ok")
        self.assertTrue(response["accepted"])
        self.assertEqual(
            response["output"]["llmOutputContractVersion"],
            ASSISTANT_LLM_OUTPUT_CONTRACT_VERSION,
        )
        self.assertEqual(
            response["output"]["safeGuidanceSummary"],
            _valid_llm_output()["safeGuidanceSummary"],
        )
        self.assertNotIn("winner", response["output"])
        self.assertNotIn("verdictReason", response["output"])

    def test_llm_output_should_fail_closed_on_forbidden_verdict_fields(self) -> None:
        output = _valid_llm_output()
        output["winner"] = "pro"

        with self.assertRaisesRegex(
            AssistantAdvisoryContractViolation,
            "assistant_advisory_forbidden_output_key",
        ):
            normalize_assistant_llm_output(output)

    def test_llm_output_should_fail_closed_on_score_or_verdict_reason(self) -> None:
        for forbidden_key in ("proScore", "verdictReason", "dimensionScores"):
            with self.subTest(forbidden_key=forbidden_key):
                output = _valid_llm_output()
                output[forbidden_key] = "blocked"
                with self.assertRaisesRegex(
                    AssistantAdvisoryContractViolation,
                    "assistant_advisory_forbidden_output_key",
                ):
                    normalize_assistant_llm_output(output)

    def test_llm_output_should_reject_non_object_empty_or_too_long_output(self) -> None:
        with self.assertRaisesRegex(
            AssistantAdvisoryContractViolation,
            "payload_not_object",
        ):
            normalize_assistant_llm_output([])

        with self.assertRaisesRegex(
            AssistantAdvisoryContractViolation,
            "assistant_llm_output_contract_keys",
        ):
            normalize_assistant_llm_output({})

        output = _valid_llm_output()
        output["safeGuidanceSummary"] = "x" * 1201
        with self.assertRaisesRegex(
            AssistantAdvisoryContractViolation,
            "safe_guidance_summary_too_long",
        ):
            normalize_assistant_llm_output(output)

    def test_outer_response_should_allow_executor_not_configured_not_ready(self) -> None:
        response = build_assistant_agent_response(
            agent_kind=AGENT_KIND_ROOM_QA,
            session_id=2001,
            advisory_context=_advisory_context(agent_kind=AGENT_KIND_ROOM_QA),
            execution_result=SimpleNamespace(
                status="not_ready",
                output={
                    "kind": AGENT_KIND_ROOM_QA,
                    "accepted": False,
                    "mode": "advisory_only",
                    "advisoryOnly": True,
                    "executorMode": "llm_canary",
                    "reason": "assistant llm_canary executor is not configured",
                },
                error_code="assistant_executor_not_configured",
                error_message="assistant llm_canary executor is not configured",
            ),
        )

        self.assertEqual(response["status"], "not_ready")
        self.assertFalse(response["accepted"])
        self.assertEqual(response["errorCode"], "assistant_executor_not_configured")

    def test_outer_response_should_reject_malformed_llm_public_output(self) -> None:
        public_output = build_assistant_llm_public_output(
            agent_kind=AGENT_KIND_NPC_COACH,
            trace_id="trace-npc-llm",
            raw_output=_valid_llm_output(),
        )
        public_output.pop("sourceUsePolicy")

        with self.assertRaises(AssistantAgentRouteError) as ctx:
            build_assistant_agent_response(
                agent_kind=AGENT_KIND_NPC_COACH,
                session_id=2001,
                advisory_context=_advisory_context(agent_kind=AGENT_KIND_NPC_COACH),
                execution_result=SimpleNamespace(
                    status="ok",
                    output=public_output,
                    error_code=None,
                    error_message=None,
                ),
            )

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(ctx.exception.detail, "assistant_advisory_contract_violation")


if __name__ == "__main__":
    unittest.main()

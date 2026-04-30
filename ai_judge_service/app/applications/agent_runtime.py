from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..domain.agents import (
    AGENT_KIND_JUDGE,
    AGENT_KIND_NPC_COACH,
    AGENT_KIND_ROOM_QA,
    JUDGE_COURTROOM_ROLE_ORDER,
    ROLE_CHIEF_ARBITER,
    ROLE_CLAIM_GRAPH,
    ROLE_CLERK,
    ROLE_EVIDENCE,
    ROLE_FAIRNESS_SENTINEL,
    ROLE_JUDGE_PANEL,
    ROLE_OPINION_WRITER,
    ROLE_RECORDER,
    AgentExecutionRequest,
    AgentExecutionResult,
    AgentExecutorPort,
    AgentKind,
    AgentProfile,
    AgentRegistryPort,
)


class _ReservedAgentExecutor(AgentExecutorPort):
    def __init__(self, *, kind: AgentKind, reason: str) -> None:
        self._kind = kind
        self._reason = reason

    async def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        return AgentExecutionResult(
            status="not_ready",
            output={
                "kind": self._kind,
                "accepted": False,
                "reason": self._reason,
                "traceId": request.trace_id,
                "mode": "advisory_only",
                "advisoryOnly": True,
                "policyIsolation": "assistant_advisory_policy",
                "allowedContextSources": [
                    "room_context_snapshot",
                    "stage_summary",
                    "knowledge_gateway",
                ],
            },
            error_code="agent_not_enabled",
            error_message=self._reason,
        )


class _JudgeCourtroomExecutor(AgentExecutorPort):
    _RUNTIME_VERSION = "courtroom_agent_runtime_mvp_v1"
    _WORKFLOW_VERSION = "courtroom_8agent_chain_v1"
    _ROLE_CONTRACT_VERSION = "courtroom_role_contract_v1"
    _WORKFLOW_CONTRACT_VERSION = "courtroom_workflow_contract_v1"
    _ARTIFACT_CONTRACT_VERSION = "courtroom_artifact_contract_v1"
    _STAGE_CONTRACT_VERSION = "courtroom_stage_contract_v1"
    _ROLE_STAGE_HINTS = {
        ROLE_CLERK: "blinded",
        ROLE_RECORDER: "case_built",
        ROLE_CLAIM_GRAPH: "claim_graph_ready",
        ROLE_EVIDENCE: "evidence_ready",
        ROLE_JUDGE_PANEL: "panel_judged",
        ROLE_FAIRNESS_SENTINEL: "fairness_checked",
        ROLE_CHIEF_ARBITER: "arbitrated",
        ROLE_OPINION_WRITER: "opinion_written",
    }
    _ROLE_RESPONSIBILITIES = {
        ROLE_CLERK: "Freeze blinded case input and runtime boundaries.",
        ROLE_RECORDER: "Normalize case dossier and timeline evidence index.",
        ROLE_CLAIM_GRAPH: "Build structured claim graph from debate messages.",
        ROLE_EVIDENCE: "Assemble retrieval and message evidence ledger.",
        ROLE_JUDGE_PANEL: "Run multi-perspective scoring and winner hints.",
        ROLE_FAIRNESS_SENTINEL: "Evaluate fairness instability and review gates.",
        ROLE_CHIEF_ARBITER: "Apply arbitration policy and winner settlement.",
        ROLE_OPINION_WRITER: "Compose user-facing verdict narrative fields.",
    }
    _PHASE_ACTIVE_ROLE_SET = {
        ROLE_CLERK,
        ROLE_RECORDER,
        ROLE_CLAIM_GRAPH,
        ROLE_EVIDENCE,
        ROLE_JUDGE_PANEL,
    }
    _ROLE_INPUT_ARTIFACTS = {
        ROLE_CLERK: (),
        ROLE_RECORDER: ("case_dossier",),
        ROLE_CLAIM_GRAPH: ("debate_timeline",),
        ROLE_EVIDENCE: ("claim_graph",),
        ROLE_JUDGE_PANEL: ("claim_graph", "evidence_bundle"),
        ROLE_FAIRNESS_SENTINEL: ("panel_decisions",),
        ROLE_CHIEF_ARBITER: ("panel_decisions", "fairness_report"),
        ROLE_OPINION_WRITER: ("final_verdict",),
    }
    _ROLE_OUTPUT_ARTIFACTS = {
        ROLE_CLERK: ("case_dossier",),
        ROLE_RECORDER: ("debate_timeline",),
        ROLE_CLAIM_GRAPH: ("claim_graph",),
        ROLE_EVIDENCE: ("evidence_bundle",),
        ROLE_JUDGE_PANEL: ("panel_decisions",),
        ROLE_FAIRNESS_SENTINEL: ("fairness_report",),
        ROLE_CHIEF_ARBITER: ("final_verdict", "verdict_ledger"),
        ROLE_OPINION_WRITER: ("opinion_pack",),
    }
    _ARTIFACT_PLAN = (
        ("case_dossier", ROLE_CLERK, (ROLE_RECORDER, ROLE_CLAIM_GRAPH, ROLE_EVIDENCE)),
        ("debate_timeline", ROLE_RECORDER, (ROLE_CLAIM_GRAPH, ROLE_EVIDENCE)),
        ("claim_graph", ROLE_CLAIM_GRAPH, (ROLE_EVIDENCE, ROLE_JUDGE_PANEL)),
        ("evidence_bundle", ROLE_EVIDENCE, (ROLE_JUDGE_PANEL,)),
        ("panel_decisions", ROLE_JUDGE_PANEL, (ROLE_FAIRNESS_SENTINEL, ROLE_CHIEF_ARBITER)),
        ("fairness_report", ROLE_FAIRNESS_SENTINEL, (ROLE_CHIEF_ARBITER,)),
        ("final_verdict", ROLE_CHIEF_ARBITER, (ROLE_OPINION_WRITER,)),
        ("opinion_pack", ROLE_OPINION_WRITER, ()),
    )

    def _activation_scope_for_role(self, *, role: str) -> str:
        if role in self._PHASE_ACTIVE_ROLE_SET:
            return "phase_and_final"
        return "final_only"

    @staticmethod
    def _normalize_dispatch_type(request: AgentExecutionRequest) -> str:
        raw_value = (
            request.metadata.get("dispatchType")
            if isinstance(request.metadata, dict)
            else None
        )
        if raw_value is None and isinstance(request.input_payload, dict):
            raw_value = (
                request.input_payload.get("dispatchType")
                or request.input_payload.get("dispatch_type")
            )
        normalized = str(raw_value or "phase").strip().lower()
        if normalized not in {"phase", "final"}:
            return "phase"
        return normalized

    def _build_role_rows(self, *, dispatch_type: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index, role in enumerate(JUDGE_COURTROOM_ROLE_ORDER, start=1):
            activation_scope = self._activation_scope_for_role(role=role)
            active = (
                role in self._PHASE_ACTIVE_ROLE_SET
                if dispatch_type == "phase"
                else True
            )
            input_artifacts = list(self._ROLE_INPUT_ARTIFACTS[role])
            output_artifacts = list(self._ROLE_OUTPUT_ARTIFACTS[role])
            stage_tag = self._ROLE_STAGE_HINTS[role]
            rows.append(
                {
                    "sequence": index,
                    "role": role,
                    "active": active,
                    "state": "active" if active else "deferred",
                    "targetStatus": stage_tag,
                    "stageTag": stage_tag,
                    "activationScope": activation_scope,
                    "responsibility": self._ROLE_RESPONSIBILITIES[role],
                    "inputArtifacts": input_artifacts,
                    "outputArtifacts": output_artifacts,
                    "contractVersion": self._ROLE_CONTRACT_VERSION,
                    "contract": {
                        "version": self._ROLE_CONTRACT_VERSION,
                        "activationScope": activation_scope,
                        "stageTag": stage_tag,
                        "inputArtifacts": input_artifacts,
                        "outputArtifacts": output_artifacts,
                    },
                }
            )
        return rows

    @staticmethod
    def _build_workflow_edges() -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []
        for index in range(len(JUDGE_COURTROOM_ROLE_ORDER) - 1):
            edges.append(
                {
                    "sequence": index + 1,
                    "fromRole": JUDGE_COURTROOM_ROLE_ORDER[index],
                    "toRole": JUDGE_COURTROOM_ROLE_ORDER[index + 1],
                    "condition": "on_success",
                }
            )
        return edges

    def _build_artifact_rows(self, *, dispatch_type: str) -> list[dict[str, Any]]:
        active_role_set = (
            self._PHASE_ACTIVE_ROLE_SET
            if dispatch_type == "phase"
            else set(JUDGE_COURTROOM_ROLE_ORDER)
        )
        rows: list[dict[str, Any]] = []
        for index, (name, producer_role, consumer_roles) in enumerate(self._ARTIFACT_PLAN, start=1):
            available = producer_role in active_role_set
            rows.append(
                {
                    "sequence": index,
                    "artifact": name,
                    "producerRole": producer_role,
                    "consumerRoles": list(consumer_roles),
                    "available": available,
                    "availability": "available" if available else "deferred",
                }
            )
        return rows

    @staticmethod
    def _collect_context(request: AgentExecutionRequest) -> dict[str, Any]:
        payload = request.input_payload if isinstance(request.input_payload, dict) else {}
        metadata = request.metadata if isinstance(request.metadata, dict) else {}
        context: dict[str, Any] = {
            "traceId": request.trace_id,
            "sessionId": request.session_id
            if request.session_id is not None
            else payload.get("sessionId"),
            "scopeId": request.scope_id if request.scope_id is not None else payload.get("scopeId"),
            "caseId": payload.get("caseId"),
            "phaseNo": metadata.get("phaseNo") if metadata.get("phaseNo") is not None else payload.get("phaseNo"),
            "phaseStartNo": (
                metadata.get("phaseStartNo")
                if metadata.get("phaseStartNo") is not None
                else payload.get("phaseStartNo")
            ),
            "phaseEndNo": (
                metadata.get("phaseEndNo")
                if metadata.get("phaseEndNo") is not None
                else payload.get("phaseEndNo")
            ),
        }
        return context

    async def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        dispatch_type = self._normalize_dispatch_type(request)
        roles = self._build_role_rows(dispatch_type=dispatch_type)
        workflow_edges = self._build_workflow_edges()
        artifacts = self._build_artifact_rows(dispatch_type=dispatch_type)
        context = self._collect_context(request)
        return AgentExecutionResult(
            status="ok",
            output={
                "kind": AGENT_KIND_JUDGE,
                "accepted": True,
                "mode": "official_verdict_plane",
                "officialVerdictAuthority": True,
                "dispatchType": dispatch_type,
                "runtimeVersion": self._RUNTIME_VERSION,
                "workflowVersion": self._WORKFLOW_VERSION,
                "roleContractVersion": self._ROLE_CONTRACT_VERSION,
                "workflowContractVersion": self._WORKFLOW_CONTRACT_VERSION,
                "artifactContractVersion": self._ARTIFACT_CONTRACT_VERSION,
                "stageContractVersion": self._STAGE_CONTRACT_VERSION,
                "roleOrder": list(JUDGE_COURTROOM_ROLE_ORDER),
                "activeRoles": [item["role"] for item in roles if item["active"]],
                "roles": roles,
                "workflowEdges": workflow_edges,
                "artifacts": artifacts,
                "context": context,
            },
        )


class StaticAgentRegistry(AgentRegistryPort):
    def __init__(
        self,
        *,
        profiles: list[AgentProfile],
        executors: dict[AgentKind, AgentExecutorPort],
    ) -> None:
        self._profiles: dict[AgentKind, AgentProfile] = {row.kind: row for row in profiles}
        self._executors = dict(executors)

    def list_profiles(self) -> list[AgentProfile]:
        return [self._profiles[key] for key in sorted(self._profiles.keys())]

    def get_profile(self, kind: AgentKind) -> AgentProfile | None:
        return self._profiles.get(kind)

    def resolve_executor(self, kind: AgentKind) -> AgentExecutorPort | None:
        return self._executors.get(kind)


@dataclass(frozen=True)
class AgentRuntime:
    registry: AgentRegistryPort

    def list_profiles(self) -> list[AgentProfile]:
        return self.registry.list_profiles()

    def get_profile(self, kind: AgentKind) -> AgentProfile | None:
        return self.registry.get_profile(kind)

    async def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        executor = self.registry.resolve_executor(request.kind)
        if executor is None:
            return AgentExecutionResult(
                status="error",
                output={
                    "kind": request.kind,
                    "accepted": False,
                    "traceId": request.trace_id,
                },
                error_code="agent_not_registered",
                error_message=f"agent '{request.kind}' is not registered",
            )
        return await executor.execute(request)


def build_agent_runtime(*, settings: Any) -> AgentRuntime:
    timeout_ms = max(100, int(getattr(settings, "openai_timeout_secs", 30.0) * 1000))
    profiles = [
        AgentProfile(
            kind=AGENT_KIND_JUDGE,
            display_name="Judge Mainline",
            description="Official judge pipeline entry managed by v3 phase/final dispatch.",
            enabled=True,
            owner="ai_judge_service",
            timeout_ms=timeout_ms,
            tags=("official", "verdict"),
        ),
        AgentProfile(
            kind=AGENT_KIND_NPC_COACH,
            display_name="NPC Coach",
            description="Reserved shell for future in-room coaching guidance agent.",
            enabled=False,
            owner="ai_judge_service",
            timeout_ms=timeout_ms,
            tags=("shell", "future", "advisory_only", "no_verdict_write"),
        ),
        AgentProfile(
            kind=AGENT_KIND_ROOM_QA,
            display_name="Room QA",
            description="Reserved shell for future room-state QA agent.",
            enabled=False,
            owner="ai_judge_service",
            timeout_ms=timeout_ms,
            tags=("shell", "future", "advisory_only", "no_verdict_write"),
        ),
    ]
    executors: dict[AgentKind, AgentExecutorPort] = {
        AGENT_KIND_JUDGE: _JudgeCourtroomExecutor(),
        AGENT_KIND_NPC_COACH: _ReservedAgentExecutor(
            kind=AGENT_KIND_NPC_COACH,
            reason="npc_coach runtime shell is reserved for future rollout",
        ),
        AGENT_KIND_ROOM_QA: _ReservedAgentExecutor(
            kind=AGENT_KIND_ROOM_QA,
            reason="room_qa runtime shell is reserved for future rollout",
        ),
    }
    return AgentRuntime(
        registry=StaticAgentRegistry(
            profiles=profiles,
            executors=executors,
        )
    )

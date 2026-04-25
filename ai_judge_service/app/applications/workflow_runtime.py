from __future__ import annotations

from dataclasses import dataclass

from app.core.workflow import WorkflowOrchestrator
from app.infra.db import DatabaseRuntime, build_database_runtime
from app.infra.facts import JudgeFactRepository
from app.infra.trust import TrustRegistryRepository
from app.infra.workflow import PostgresWorkflowStore


@dataclass(frozen=True)
class WorkflowRuntime:
    db: DatabaseRuntime
    store: PostgresWorkflowStore
    facts: JudgeFactRepository
    trust_registry: TrustRegistryRepository
    orchestrator: WorkflowOrchestrator


def build_workflow_runtime(*, settings: object) -> WorkflowRuntime:
    db = build_database_runtime(settings=settings)
    store = PostgresWorkflowStore(session_factory=db.session_factory)
    facts = JudgeFactRepository(session_factory=db.session_factory)
    trust_registry = TrustRegistryRepository(session_factory=db.session_factory)
    orchestrator = WorkflowOrchestrator(workflow_port=store)
    return WorkflowRuntime(
        db=db,
        store=store,
        facts=facts,
        trust_registry=trust_registry,
        orchestrator=orchestrator,
    )

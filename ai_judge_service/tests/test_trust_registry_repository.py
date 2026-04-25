import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.domain.trust import TrustChallengeEvent, TrustRegistrySnapshot
from app.infra.db.runtime import build_database_runtime
from app.infra.trust import TrustRegistryRepository


def _snapshot(
    *,
    case_id: int = 9701,
    dispatch_type: str = "final",
    trace_id: str = "trace-9701-final",
    registry_version: str = "trust-registry-v1",
    updated_at: datetime | None = None,
    public_verify_extra: dict | None = None,
) -> TrustRegistrySnapshot:
    component_hashes = {
        "caseCommitmentHash": f"commit-{trace_id}",
        "verdictAttestationHash": f"attest-{trace_id}",
        "challengeReviewHash": f"challenge-{trace_id}",
        "kernelVersionHash": f"kernel-{trace_id}",
        "auditAnchorHash": f"anchor-{trace_id}",
    }
    public_verify = {
        "caseId": case_id,
        "dispatchType": dispatch_type,
        "traceId": trace_id,
        "verifyPayload": {
            "caseCommitment": {"commitmentHash": component_hashes["caseCommitmentHash"]},
            "verdictAttestation": {
                "registryHash": component_hashes["verdictAttestationHash"],
                "verified": True,
            },
            "challengeReview": {
                "registryHash": component_hashes["challengeReviewHash"],
                "challengeState": "not_challenged",
            },
            "kernelVersion": {"registryHash": component_hashes["kernelVersionHash"]},
            "auditAnchor": {"anchorHash": component_hashes["auditAnchorHash"]},
        },
    }
    if public_verify_extra:
        public_verify.update(public_verify_extra)
    return TrustRegistrySnapshot(
        case_id=case_id,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        registry_version=registry_version,
        case_commitment={
            "version": "trust-phaseA-case-commitment-v1",
            "caseId": case_id,
            "dispatchType": dispatch_type,
            "traceId": trace_id,
            "commitmentHash": component_hashes["caseCommitmentHash"],
        },
        verdict_attestation={
            "version": "trust-phaseA-verdict-attestation-v1",
            "caseId": case_id,
            "dispatchType": dispatch_type,
            "traceId": trace_id,
            "registryHash": component_hashes["verdictAttestationHash"],
            "verified": True,
        },
        challenge_review={
            "version": "trust-phaseB-challenge-review-v1",
            "caseId": case_id,
            "traceId": trace_id,
            "challengeState": "not_challenged",
            "totalChallenges": 0,
            "registryHash": component_hashes["challengeReviewHash"],
        },
        kernel_version={
            "version": "trust-phaseA-kernel-version-v1",
            "caseId": case_id,
            "traceId": trace_id,
            "registryHash": component_hashes["kernelVersionHash"],
            "kernelHash": "kernel-hash-v1",
        },
        audit_anchor={
            "version": "trust-phaseA-audit-anchor-v1",
            "caseId": case_id,
            "dispatchType": dispatch_type,
            "traceId": trace_id,
            "anchorHash": component_hashes["auditAnchorHash"],
            "componentHashes": component_hashes,
        },
        public_verify=public_verify,
        component_hashes=component_hashes,
        created_at=datetime(2026, 4, 25, 0, 0, tzinfo=timezone.utc),
        updated_at=updated_at or datetime(2026, 4, 25, 0, 1, tzinfo=timezone.utc),
    )


class TrustRegistryRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        db_file = Path(self._tmpdir.name) / "trust_registry_test.db"
        settings = SimpleNamespace(
            db_url=f"sqlite+aiosqlite:///{db_file}",
            db_echo=False,
            db_pool_size=5,
            db_max_overflow=5,
        )
        self._db_runtime = build_database_runtime(settings=settings)
        await self._db_runtime.create_schema()
        self._repo = TrustRegistryRepository(session_factory=self._db_runtime.session_factory)

    async def asyncTearDown(self) -> None:
        await self._db_runtime.dispose()
        self._tmpdir.cleanup()

    async def test_trust_registry_snapshot_should_upsert_and_query_latest(self) -> None:
        first = _snapshot(
            trace_id="trace-9701-a",
            updated_at=datetime(2026, 4, 25, 0, 1, tzinfo=timezone.utc),
        )
        await self._repo.upsert_trust_registry_snapshot(snapshot=first)

        second = _snapshot(
            trace_id="trace-9701-b",
            updated_at=datetime(2026, 4, 25, 0, 3, tzinfo=timezone.utc),
        )
        await self._repo.upsert_trust_registry_snapshot(snapshot=second)

        latest = await self._repo.get_trust_registry_snapshot(
            case_id=9701,
            dispatch_type="final",
        )
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest.trace_id, "trace-9701-b")
        self.assertEqual(
            latest.component_hashes["auditAnchorHash"],
            "anchor-trace-9701-b",
        )

        rows = await self._repo.list_trust_registry_snapshots(
            case_id=9701,
            dispatch_type="final",
            limit=10,
        )
        self.assertEqual([row.trace_id for row in rows], ["trace-9701-b", "trace-9701-a"])

    async def test_trust_registry_snapshot_should_replace_same_trace_version(self) -> None:
        await self._repo.upsert_trust_registry_snapshot(snapshot=_snapshot())
        changed = _snapshot(
            public_verify_extra={
                "verifyPayload": {
                    "caseCommitment": {"commitmentHash": "commit-replaced"},
                    "verdictAttestation": {"registryHash": "attest-replaced", "verified": True},
                    "challengeReview": {"registryHash": "challenge-replaced"},
                    "kernelVersion": {"registryHash": "kernel-replaced"},
                    "auditAnchor": {"anchorHash": "anchor-replaced"},
                }
            },
            updated_at=datetime(2026, 4, 25, 0, 4, tzinfo=timezone.utc),
        )
        await self._repo.upsert_trust_registry_snapshot(snapshot=changed)

        rows = await self._repo.list_trust_registry_snapshots(case_id=9701, limit=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0].public_verify["verifyPayload"]["caseCommitment"]["commitmentHash"],
            "commit-replaced",
        )

    async def test_trust_registry_snapshot_should_reject_mismatched_component(self) -> None:
        snapshot = _snapshot()
        invalid = TrustRegistrySnapshot(
            **{
                **snapshot.__dict__,
                "verdict_attestation": {
                    **snapshot.verdict_attestation,
                    "caseId": 9702,
                },
            }
        )
        with self.assertRaisesRegex(ValueError, "verdict_attestation_case_id_mismatch"):
            await self._repo.upsert_trust_registry_snapshot(snapshot=invalid)

    async def test_trust_registry_snapshot_should_reject_public_verify_internal_fields(self) -> None:
        snapshot = _snapshot(public_verify_extra={"rawTrace": {"prompt": "hidden"}})
        with self.assertRaisesRegex(ValueError, "trust_registry_public_verify_forbidden_keys"):
            await self._repo.upsert_trust_registry_snapshot(snapshot=snapshot)

    async def test_append_challenge_event_should_preserve_registry_source(self) -> None:
        await self._repo.upsert_trust_registry_snapshot(snapshot=_snapshot())
        updated = await self._repo.append_challenge_event(
            case_id=9701,
            dispatch_type="final",
            trace_id="trace-9701-final",
            registry_version="trust-registry-v1",
            event=TrustChallengeEvent(
                event_type="trust_challenge_requested",
                challenge_id="chlg-9701-1",
                state="challenge_requested",
                actor="ops-a",
                reason_code="manual_challenge",
                reason="need verification",
                created_at=datetime(2026, 4, 25, 0, 5, tzinfo=timezone.utc),
            ),
        )
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(
            updated.challenge_review["registryEvents"][0]["eventType"],
            "trust_challenge_requested",
        )
        self.assertEqual(
            updated.challenge_review["latestRegistryEvent"]["state"],
            "challenge_requested",
        )
        self.assertEqual(updated.challenge_review["challengeState"], "challenge_requested")
        self.assertEqual(updated.challenge_review["activeChallengeId"], "chlg-9701-1")
        self.assertEqual(updated.challenge_review["totalChallenges"], 1)
        self.assertEqual(
            updated.public_verify["verifyPayload"]["challengeReview"]["challengeState"],
            "challenge_requested",
        )
        self.assertEqual(
            updated.component_hashes["challengeReviewHash"],
            updated.challenge_review["registryHash"],
        )


if __name__ == "__main__":
    unittest.main()

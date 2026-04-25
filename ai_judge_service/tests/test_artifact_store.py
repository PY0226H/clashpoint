from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.applications.artifact_pack import write_case_artifact_pack, write_trust_audit_artifact_pack
from app.domain.artifacts import ArtifactRef
from app.infra.artifacts import LocalArtifactStore


class ArtifactStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._root = Path(self._tmpdir.name) / "artifacts" / "ai_judge_service"
        self._store = LocalArtifactStore(root_dir=self._root)

    async def asyncTearDown(self) -> None:
        self._tmpdir.cleanup()

    async def test_local_store_should_put_and_get_redacted_json_ref(self) -> None:
        payload = {
            "version": "transcript-redacted-v1",
            "messageIds": [1, 2],
            "messageDigest": [
                {"messageId": 1, "side": "pro"},
                {"messageId": 2, "side": "con"},
            ],
        }

        ref = await self._store.put_json(
            case_id=9101,
            kind="transcript_snapshot",
            payload=payload,
            dispatch_type="final",
            trace_id="trace-9101",
        )

        self.assertEqual(ref.kind, "transcript_snapshot")
        self.assertEqual(ref.content_type, "application/json")
        self.assertEqual(ref.redaction_level, "redacted")
        self.assertEqual(len(ref.sha256), 64)
        self.assertTrue(ref.uri.startswith("local-artifact://ai_judge_service/"))
        self.assertNotIn(self._tmpdir.name, ref.uri)
        self.assertTrue(await self._store.exists(ref=ref))
        self.assertEqual(await self._store.get_json(ref=ref), payload)

        files = list(self._root.rglob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].resolve().is_relative_to(self._root.resolve()))

    async def test_local_store_should_reject_path_escape_and_uri_namespace_escape(self) -> None:
        with self.assertRaisesRegex(ValueError, "artifact_id_invalid"):
            await self._store.put_json(
                case_id=9102,
                kind="evidence_pack",
                payload={"version": "evidence-v1"},
                artifact_id="../escape",
            )

        ref = await self._store.put_json(
            case_id=9102,
            kind="evidence_pack",
            payload={"version": "evidence-v1"},
        )
        bad_ref = ArtifactRef(
            artifact_id=ref.artifact_id,
            kind=ref.kind,
            uri=ref.uri.replace("ai_judge_service", "other_namespace"),
            sha256=ref.sha256,
        )
        with self.assertRaisesRegex(ValueError, "artifact_uri_namespace_invalid"):
            await self._store.get_json(ref=bad_ref)

    async def test_local_store_should_reject_sensitive_payload_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "artifact_payload_forbidden_keys"):
            await self._store.put_json(
                case_id=9103,
                kind="audit_pack",
                payload={"version": "audit-v1", "rawPrompt": "internal prompt"},
                redaction_level="ops",
            )

    async def test_case_artifact_pack_should_write_refs_and_manifest(self) -> None:
        pack = await write_case_artifact_pack(
            artifact_store=self._store,
            case_id=9104,
            dispatch_type="final",
            trace_id="trace-9104",
            transcript_snapshot={"version": "transcript-v1", "messageIds": [1, 2]},
            evidence_pack={"version": "evidence-v1", "entries": [{"id": "e1"}]},
            replay_snapshot={"version": "replay-v1", "winner": "pro"},
            audit_pack={"version": "audit-v1", "alerts": [{"type": "review_gap"}]},
            metadata={"source": "unit-test"},
        )

        payload = pack.to_payload()
        self.assertEqual(
            [ref["kind"] for ref in payload["refs"]],
            [
                "transcript_snapshot",
                "evidence_pack",
                "replay_snapshot",
                "audit_pack",
            ],
        )
        self.assertEqual(payload["manifest"]["artifactCount"], 4)
        self.assertEqual(payload["manifest"]["metadata"], {"source": "unit-test"})
        self.assertEqual(len(payload["manifest"]["manifestHash"]), 64)
        self.assertEqual(
            payload["manifest"]["artifactHashes"]["audit_pack"],
            payload["refs"][3]["sha256"],
        )
        for ref in pack.refs:
            self.assertTrue(await self._store.exists(ref=ref))

    async def test_trust_audit_artifact_pack_should_redact_evidence_ref_payloads(self) -> None:
        pack = await write_trust_audit_artifact_pack(
            artifact_store=self._store,
            case_id=9105,
            dispatch_type="final",
            trace_id="trace-9105",
            request_snapshot={
                "message_start_id": 1,
                "message_end_id": 2,
                "message_count": 2,
                "messages": [{"message_id": 1, "side": "pro", "content": "raw message"}],
            },
            report_payload={
                "winner": "pro",
                "verdictEvidenceRefs": [
                    {
                        "evidenceId": "ev-1",
                        "side": "pro",
                        "type": "agent2_hit",
                        "item": "raw decisive quote",
                        "content": "raw ref content",
                    }
                ],
                "evidenceLedger": {"entries": [{"id": "ev-1", "content": "raw evidence"}]},
            },
            workflow_snapshot={"status": "callback_reported"},
            commitment={"commitmentHash": "case-hash", "version": "v1"},
            verdict_attestation={"registryHash": "verdict-hash", "version": "v1"},
            challenge_review={"registryHash": "challenge-hash", "version": "v1"},
            kernel_version={"registryHash": "kernel-hash", "version": "v1"},
        )

        evidence_ref = next(ref for ref in pack.refs if ref.kind == "evidence_pack")
        evidence_payload = await self._store.get_json(ref=evidence_ref)
        evidence_repr = str(evidence_payload)
        self.assertNotIn("raw decisive quote", evidence_repr)
        self.assertNotIn("raw ref content", evidence_repr)
        self.assertNotIn("raw evidence", evidence_repr)
        self.assertEqual(
            evidence_payload["verdictEvidenceRefs"][0]["itemHash"],
            "eb817ecdd6e8090037d4981b1e46084d977ae54ae80766593e165921cb33dbc2",
        )


if __name__ == "__main__":
    unittest.main()

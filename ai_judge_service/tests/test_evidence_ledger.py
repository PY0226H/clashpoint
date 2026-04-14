from __future__ import annotations

from app.domain.judge.evidence_ledger import EvidenceLedgerBuilder


def test_evidence_ledger_should_build_entries_and_lookup() -> None:
    builder = EvidenceLedgerBuilder()
    message_id = builder.register_message_ref(
        phase_no=1,
        side="pro",
        message_id=101,
        reason="agent1_evidence_ref",
    )
    assert message_id is not None
    chunk_id = builder.register_retrieval_chunk(
        phase_no=1,
        side="pro",
        chunk_id="chunk-a",
        reason="retrieval_snapshot",
        source_url="https://example.com/a",
        score=0.86,
        conflict=False,
    )
    assert chunk_id is not None
    miss_id = builder.register_agent2_path_item(
        phase_no=1,
        side="con",
        path_type="agent2_miss",
        item="con-miss-claim",
        reason="agent2_path_alignment",
    )
    assert miss_id is not None

    builder.mark_verdict_referenced(message_id)
    builder.mark_verdict_referenced(chunk_id)
    payload = builder.build_payload()

    assert payload["pipelineVersion"] == "v2-evidence-ledger"
    assert payload["stats"]["totalEntries"] == 3
    assert payload["stats"]["verdictReferencedCount"] == 2
    assert payload["stats"]["conflictRefCount"] == 1
    assert str(payload["refsById"][message_id]["kind"]) == "message_ref"
    assert str(payload["refsById"][chunk_id]["kind"]) == "retrieval_chunk"

    resolved = builder.resolve_reference_ids(
        phase_no=1,
        side="pro",
        message_ids=[101],
        chunk_ids=["chunk-a"],
    )
    assert message_id in resolved
    assert chunk_id in resolved

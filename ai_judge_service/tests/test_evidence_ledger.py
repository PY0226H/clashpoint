from __future__ import annotations

import json

from app.domain.judge.evidence_ledger import (
    EvidenceLedgerBuilder,
    build_citation_verification_summary,
)


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

    assert payload["pipelineVersion"] == "v3-evidence-bundle"
    assert payload["bundleMeta"]["kind"] == "evidence_bundle"
    assert payload["bundleMeta"]["officialVerdictAuthority"] is False
    assert payload["stats"]["totalEntries"] == 3
    assert payload["stats"]["verdictReferencedCount"] == 2
    assert payload["stats"]["sourceCitationCount"] == 1
    assert payload["stats"]["conflictSourceCount"] == 1
    assert payload["stats"]["reliabilityCounts"]["high"] >= 1
    assert payload["stats"]["reliabilityCounts"]["low"] >= 1
    assert payload["stats"]["verdictReferencedReliabilityCounts"]["high"] >= 1
    assert payload["stats"]["verdictReferencedReliabilityCounts"]["low"] == 0
    assert payload["stats"]["conflictReasonCounts"]["agent2_path_alignment"] == 1
    assert payload["evidenceSufficiency"]["passed"] is True
    assert payload["evidence_sufficiency"]["status"] == "sufficient"
    assert payload["reliabilityNotes"]["level"] == "high"
    assert payload["citationVerification"]["version"] == "evidence-citation-verification-v1"
    assert payload["citationVerification"]["status"] == "env_blocked"
    assert payload["citationVerification"]["citationCount"] >= 2
    assert payload["citationVerification"]["messageRefCount"] == 1
    assert payload["citationVerification"]["sourceRefCount"] == 1
    assert "citation_verifier_real_sample_env_blocked" in payload["citationVerification"]["reasonCodes"]
    assert "winner" not in payload
    assert payload["message_refs"] == payload["messageRefs"]
    assert payload["source_citations"] == payload["sourceCitations"]
    assert payload["conflict_sources"] == payload["conflictSources"]
    assert len(payload["sourceCitations"]) == 1
    assert payload["sourceCitations"][0]["sourceUrl"] == "https://example.com/a"
    assert len(payload["conflictSources"]) == 1
    assert payload["conflictSources"][0]["kind"] == "agent2_miss"
    assert payload["conflictSources"][0]["primaryReason"] == "agent2_path_alignment"
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


def test_citation_verifier_should_block_missing_and_forbidden_public_sources() -> None:
    payload = {
        "entries": [
            {
                "evidenceId": "ev-msg-pro-p1",
                "kind": "message_ref",
                "locator": {"messageId": 101},
                "reliabilityLabel": "high",
            },
            {
                "evidenceId": "ev-source-pro-p1",
                "kind": "retrieval_chunk",
                "locator": {"chunkId": "chunk-a"},
                "reliabilityLabel": "high",
            },
        ],
        "refsById": {
            "ev-msg-pro-p1": {"kind": "message_ref"},
            "ev-source-pro-p1": {"kind": "retrieval_chunk"},
        },
        "messageRefs": [
            {"evidenceId": "ev-msg-pro-p1", "messageId": 101},
        ],
        "sourceCitations": [
            {
                "evidenceId": "ev-source-pro-p1",
                "sourceId": "src-safe",
                "chunkId": "chunk-a",
                "sourceType": "web",
                "rawPrompt": "must not leave private citation verifier input",
            }
        ],
        "evidenceSufficiency": {"passed": True},
    }

    summary = build_citation_verification_summary(
        payload,
        verdict_evidence_refs=[
            {"evidenceId": "ev-source-pro-p1"},
            {"evidenceId": "ev-missing"},
        ],
        environment_mode="real",
        real_sample_ready=True,
    )

    assert summary["status"] == "blocked"
    assert summary["missingCitationCount"] == 1
    assert summary["forbiddenSourceCount"] == 1
    assert "citation_verifier_missing_evidence_refs" in summary["reasonCodes"]
    assert "citation_verifier_forbidden_source_metadata" in summary["reasonCodes"]
    summary_text = json.dumps(summary, ensure_ascii=False)
    assert "must not leave private citation verifier input" not in summary_text


def test_citation_verifier_should_warn_for_decisive_refs_without_message_or_source() -> None:
    builder = EvidenceLedgerBuilder()
    path_id = builder.register_agent2_path_item(
        phase_no=1,
        side="pro",
        path_type="agent2_hit",
        item="pro:claim-a",
        reason="agent2_path_alignment",
    )
    assert path_id is not None
    builder.mark_verdict_referenced(path_id)
    payload = builder.build_payload()

    summary = build_citation_verification_summary(
        payload,
        environment_mode="real",
        real_sample_ready=True,
    )

    assert summary["status"] == "warning"
    assert summary["weakCitationCount"] >= 1
    assert "citation_verifier_weak_citations" in summary["reasonCodes"]
    assert summary["officialVerdictAuthority"] is False

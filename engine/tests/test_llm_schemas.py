from next_signal.schemas import (
    ACHCell,
    ACHCells,
    DiscoveryText,
    EvidenceJudgement,
    EvidenceJudgements,
    ExtractedFact,
    ExtractedFacts,
    NarrativeClaim,
    NarrativeClaims,
)


def test_extracted_facts_round_trip():
    obj = ExtractedFacts(items=[
        ExtractedFact(metric="receivable_days", period="Q1FY27", value=46.0, unit="days", page=12,
                       quote="receivable days rose from 28 to 46 over the last eight quarters"),
    ])
    assert ExtractedFacts.model_validate_json(obj.model_dump_json()).items[0].value == 46.0


def test_narrative_claims_polarity_bounds():
    claim = NarrativeClaim(claim="management says growth is accelerating", metric_id_guess="rev_yoy",
                            polarity=1, period="Q1FY27", quote="we expect accelerating growth")
    assert NarrativeClaims(items=[claim]).items[0].polarity == 1


def test_ach_cells_glyph_validation():
    import pytest
    from pydantic import ValidationError

    ACHCells(items=[ACHCell(evidence_index=0, hypothesis_id="H1", glyph="CC")])
    with pytest.raises(ValidationError):
        ACHCell(evidence_index=0, hypothesis_id="H1", glyph="XX")


def test_evidence_judgements_verdict_validation():
    import pytest
    from pydantic import ValidationError

    EvidenceJudgements(items=[EvidenceJudgement(item_index=0, verdict="contradicts", quote="q", reasoning="r")])
    with pytest.raises(ValidationError):
        EvidenceJudgement(item_index=0, verdict="maybe")


def test_discovery_text_why_it_matters_bounds():
    import pytest
    from pydantic import ValidationError

    DiscoveryText(sentence="x", why_it_matters=["a", "b", "c"], counterargument="y")
    with pytest.raises(ValidationError):
        DiscoveryText(sentence="x", why_it_matters=["only one"], counterargument="y")

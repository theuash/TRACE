"""Guards the frozen contracts. If these fail, someone changed shared/ without a contract PR."""

from datetime import date
from decimal import Decimal

import pytest

from shared.config import COMPANIES, get_company, get_settings
from shared.interfaces import FAKES, PROVIDERS
from shared.schemas import (
    GENESIS_HASH,
    AuditAction,
    AuditEntry,
    DecisionType,
    ExtractedMetric,
    Extractor,
    Metric,
    MetricStatus,
    ReviewDecision,
    SourceEvidence,
    Thresholds,
    make_metric_id,
)


def _metric(**kw) -> ExtractedMetric:
    base = dict(
        ticker="aapl", metric=Metric.TOTAL_ASSETS, fiscal_year=2025, period_end=date(2025, 9, 27),
        value=Decimal("352583000000"), scale=1_000_000, raw_text="352,583",
        extractor=Extractor.TABLE, confidence=0.97,
        evidence=SourceEvidence(snippet="Total assets 352,583 364,980", matched_text="352,583",
                                location="Balance Sheet"),
    )
    base.update(kw)
    return ExtractedMetric(**base)


def test_metric_id_is_deterministic_and_uppercase():
    m = _metric()
    assert m.id == "AAPL:total_assets:2025" == make_metric_id("aapl", Metric.TOTAL_ASSETS, 2025)


def test_effective_value_rules():
    m = _metric()
    assert m.effective_value is None  # undecided
    assert m.model_copy(update={"status": MetricStatus.AUTO_APPROVED}).effective_value == m.value
    fixed = m.model_copy(update={"status": MetricStatus.CORRECTED, "reviewed_value": Decimal("1")})
    assert fixed.effective_value == Decimal("1")
    assert m.model_copy(update={"status": MetricStatus.REJECTED}).effective_value is None


def test_extra_fields_are_rejected():
    with pytest.raises(ValueError):
        _metric(confdence=0.5)  # typo must fail loudly


def test_edit_requires_corrected_value():
    with pytest.raises(ValueError):
        ReviewDecision(review_id="x", decision=DecisionType.EDIT, reviewer="r")
    ReviewDecision(review_id="x", decision=DecisionType.APPROVE, reviewer="r")


def test_thresholds_per_metric_override():
    t = Thresholds(confidence=0.85, per_metric_confidence={Metric.REVENUE: 0.7})
    assert t.is_low_confidence(Metric.NET_INCOME, 0.8)
    assert not t.is_low_confidence(Metric.REVENUE, 0.8)


def test_audit_hash_is_stable_across_json_roundtrip_and_detects_tampering():
    first = AuditEntry(seq=1, actor="alice", action=AuditAction.HUMAN_DECISION,
                       metric_id="AAPL:total_assets:2025", original_value=Decimal("352583000000"),
                       corrected_value=Decimal("352500000000"), decision=DecisionType.EDIT,
                       prev_hash=GENESIS_HASH).seal()
    reloaded = AuditEntry.model_validate_json(first.model_dump_json())  # what a DB round trip does
    assert reloaded.compute_hash() == first.hash

    second = AuditEntry(seq=2, actor="bob", action=AuditAction.HUMAN_DECISION,
                        prev_hash=first.hash).seal()
    assert second.prev_hash == first.hash

    tampered = reloaded.model_copy(update={"corrected_value": Decimal("1")})
    assert tampered.compute_hash() != first.hash


def test_five_companies_with_valid_ciks():
    assert len(COMPANIES) == 5
    assert all(len(c.cik) == 10 for c in COMPANIES)
    assert get_company("aapl").name.startswith("Apple")


def test_settings_defaults_and_threshold_bridge():
    s = get_settings()
    t = s.default_thresholds()
    assert t.confidence == s.confidence_threshold
    assert s.api_base_url.startswith("http://")


def test_provider_registry_is_consistent():
    assert set(FAKES) <= set(PROVIDERS)
    assert all(":" in v for v in {**PROVIDERS, **FAKES}.values())

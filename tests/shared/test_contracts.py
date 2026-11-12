"""The additive contract changes P2 relies on."""

import pytest
from pydantic import ValidationError

from shared.schemas import EscalationItem, RiskTier, Thresholds


def test_default_boundaries():
    t = Thresholds()
    assert t.confidence == 0.85
    assert t.confidence_critical == 0.60


def test_critical_cannot_exceed_green():
    with pytest.raises(ValidationError):
        Thresholds(confidence=0.5, confidence_critical=0.9)


def test_tier_default_is_yellow():
    assert RiskTier.GREEN.value == "green"
    assert EscalationItem.model_fields["tier"].default is RiskTier.YELLOW

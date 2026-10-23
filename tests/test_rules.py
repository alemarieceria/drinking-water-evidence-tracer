"""Numeric cross-check cases from proposal sections 11, 15, and 16."""

from decimal import Decimal

from app.rules import result_values_disagree


def test_cross_check_rejects_disagreeing_values() -> None:
    assert result_values_disagree(
        extracted_value=Decimal("13.7"),
        detection_summary_value=Decimal("3.7"),
    )


def test_cross_check_accepts_equal_decimal_values() -> None:
    assert not result_values_disagree(
        extracted_value=Decimal("3.7"),
        detection_summary_value=Decimal("3.70"),
    )

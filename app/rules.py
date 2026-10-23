"""Plain-Python evidence rules."""

from decimal import Decimal


def result_values_disagree(
    extracted_value: Decimal, detection_summary_value: Decimal
) -> bool:
    """Compare numeric values already matched to the same result and units.

    True identifies a disagreement; False allows further human review.
    """
    return extracted_value != detection_summary_value

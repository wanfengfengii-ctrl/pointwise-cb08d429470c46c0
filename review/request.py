from dataclasses import dataclass
from fractions import Fraction

from bench.calibration import SettingNames
from review.domain import ClosedSettingDomain, parse_setting_domain, parse_threshold


@dataclass(frozen=True)
class AssessmentRequest:
    benches: tuple[str, str]
    receipt_ids: tuple[int, int]
    domain: ClosedSettingDomain
    threshold: Fraction


def build_request(
    benches: tuple[str, str], receipt_ids: tuple[int, int],
    first_settings: SettingNames, second_settings: SettingNames, bounds: object, threshold: object,
) -> AssessmentRequest:
    if set(first_settings) != set(second_settings):
        raise ValueError('receipts do not share the same named settings')
    first, second = sorted(first_settings)
    return AssessmentRequest(
        tuple(benches), tuple(receipt_ids),
        parse_setting_domain((first, second), bounds), parse_threshold(threshold),
    )

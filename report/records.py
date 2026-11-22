import json
from dataclasses import dataclass
from fractions import Fraction

from review.domain import parse_setting_domain, parse_threshold
from review.request import AssessmentRequest
from review.verdict import RetestVerdict


@dataclass(frozen=True)
class ReportSnapshot:
    request: AssessmentRequest
    minimum_p: Fraction
    maximum_p: Fraction
    verdict: RetestVerdict


def encode_report(snapshot: ReportSnapshot) -> str:
    request = snapshot.request
    return json.dumps({
        'benches': request.benches,
        'receipt_ids': request.receipt_ids,
        'settings': request.domain.names,
        'bounds': {
            name: [str(lower), str(upper)]
            for name, (lower, upper) in request.domain.as_mapping().items()
        },
        'threshold': str(request.threshold),
        'minimum_p': str(snapshot.minimum_p),
        'maximum_p': str(snapshot.maximum_p),
        'verdict': snapshot.verdict.value,
    }, sort_keys=True, separators=(',', ':'))


def decode_report(payload: str) -> ReportSnapshot:
    data = json.loads(payload)
    request = AssessmentRequest(
        tuple(data['benches']), tuple(data['receipt_ids']),
        parse_setting_domain(tuple(data['settings']), data['bounds']), parse_threshold(data['threshold']),
    )
    return ReportSnapshot(
        request, Fraction(data['minimum_p']), Fraction(data['maximum_p']), RetestVerdict(data['verdict']),
    )

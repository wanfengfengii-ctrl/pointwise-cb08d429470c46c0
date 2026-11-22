from collections.abc import Callable
from fractions import Fraction
from itertools import product

from issue.codec import decode_evidence
from issue.envelope import unpack_envelope
from issue.evidence import EvidenceBody
from receipt.custody import ReceiptStore
from receipt.selection import select_receipts
from report.archive import FinalReport, ReportArchive
from report.publish import publish_report
from review.domain import ClosedSettingDomain
from review.request import build_request
from review.signed_rank import exact_signed_rank_p
from review.verdict import classify_retest


def evaluate_extrema(
    bodies: tuple[EvidenceBody, EvidenceBody], domain: ClosedSettingDomain,
) -> tuple[Fraction, Fraction]:
    aligned = []
    for body in bodies:
        x_index = 1 + body.settings.index(domain.names[0])
        y_index = 1 + body.settings.index(domain.names[1])
        aligned.extend((row[0], row[x_index], row[y_index]) for row in body.differences)

    probabilities = [
        exact_signed_rank_p(c + a * x + b * y for c, a, b in aligned)
        for x, y in product(*domain.bounds)
    ]
    return min(probabilities), max(probabilities)


def assess(
    receipts: ReceiptStore, archive: ReportArchive, benches: tuple[str, str],
    receipt_ids: tuple[int, int], bounds: object, threshold: object,
    *, before_commit: Callable[[], None] | None = None,
) -> FinalReport:
    selected = select_receipts(receipts, benches, receipt_ids)
    first, second = (decode_evidence(unpack_envelope(item.wire).body) for item in selected.records)
    request = build_request(
        (selected.first.bench, selected.second.bench),
        (selected.first.receipt_id, selected.second.receipt_id),
        first.settings, second.settings, bounds, threshold,
    )
    minimum, maximum = evaluate_extrema((first, second), request.domain)
    verdict = classify_retest(minimum, maximum, request.threshold)
    return publish_report(archive, request, minimum, maximum, verdict, selected, before_commit=before_commit)

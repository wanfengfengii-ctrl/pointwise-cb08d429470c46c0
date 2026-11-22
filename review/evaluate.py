from collections.abc import Callable
from fractions import Fraction
from itertools import combinations

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


def _candidate_lines(aligned: tuple[tuple[Fraction, Fraction, Fraction], ...]):
    """Lines across which the p value can change: zero sets of each form and of
    each pairwise sum or difference (magnitude ties), as a*u + b*v + c = 0."""
    forms = tuple((coef_u, coef_v, constant) for constant, coef_u, coef_v in aligned)
    candidates = list(forms)
    for first, second in combinations(forms, 2):
        candidates.append(tuple(f + s for f, s in zip(first, second)))
        candidates.append(tuple(f - s for f, s in zip(first, second)))
    lines = set()
    for a, b, c in candidates:
        if a == 0 and b == 0:
            continue
        scale = max(abs(a), abs(b), abs(c))
        line = (a / scale, b / scale, c / scale)
        if next(value for value in line if value != 0) < 0:
            line = tuple(-value for value in line)
        lines.add(line)
    return tuple(lines)


def _with_midpoints(values) -> tuple[Fraction, ...]:
    ordered = sorted(values)
    result = list(ordered)
    result.extend((first + second) / 2 for first, second in zip(ordered, ordered[1:]))
    return tuple(result)


def _closed_domain_extrema(
    aligned: tuple[tuple[Fraction, Fraction, Fraction], ...],
    bounds: tuple[tuple[Fraction, Fraction], tuple[Fraction, Fraction]],
) -> tuple[Fraction, Fraction]:
    """Exact extrema of the two-sided signed-rank p value over the closed rectangle.

    The p value is constant on every cell, edge and vertex of the arrangement of
    the candidate lines clipped to the rectangle, so it suffices to evaluate one
    rational sample per feature. A vertical decomposition supplies them: sample
    every critical u (line intersections and boundary crossings) plus strip
    midpoints, and along each sampled vertical line sample every crossing v plus
    interval midpoints. Degenerate rectangles (segments, points) work unchanged.
    """
    (u_lower, u_upper), (v_lower, v_upper) = bounds
    lines = _candidate_lines(aligned)

    u_values = {u_lower, u_upper}
    for (a1, b1, c1), (a2, b2, c2) in combinations(lines, 2):
        determinant = a1 * b2 - a2 * b1
        if determinant == 0:
            continue
        u = (b1 * c2 - b2 * c1) / determinant
        v = (c1 * a2 - c2 * a1) / determinant
        if u_lower <= u <= u_upper and v_lower <= v <= v_upper:
            u_values.add(u)
    for a, b, c in lines:
        if a != 0:
            for v_edge in (v_lower, v_upper):
                u = -(b * v_edge + c) / a
                if u_lower <= u <= u_upper:
                    u_values.add(u)

    probabilities = []
    for u in _with_midpoints(u_values):
        v_values = {v_lower, v_upper}
        for a, b, c in lines:
            if b != 0:
                v = -(a * u + c) / b
                if v_lower <= v <= v_upper:
                    v_values.add(v)
        for v in _with_midpoints(v_values):
            probabilities.append(exact_signed_rank_p(
                constant + coef_u * u + coef_v * v
                for constant, coef_u, coef_v in aligned
            ))
    return min(probabilities), max(probabilities)


def evaluate_extrema(
    bodies: tuple[EvidenceBody, EvidenceBody], domain: ClosedSettingDomain,
) -> tuple[Fraction, Fraction]:
    aligned = []
    for body in bodies:
        x_index = 1 + body.settings.index(domain.names[0])
        y_index = 1 + body.settings.index(domain.names[1])
        aligned.extend((row[0], row[x_index], row[y_index]) for row in body.differences)
    return _closed_domain_extrema(tuple(aligned), domain.bounds)


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

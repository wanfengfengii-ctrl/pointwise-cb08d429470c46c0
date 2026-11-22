from collections.abc import Callable
from fractions import Fraction

from receipt.selection import SelectedReceipts
from report.archive import FinalReport, ReportArchive
from report.records import ReportSnapshot
from report.trace import snapshot_parents
from review.request import AssessmentRequest
from review.verdict import RetestVerdict


def publish_report(
    archive: ReportArchive, request: AssessmentRequest, minimum: Fraction, maximum: Fraction,
    verdict: RetestVerdict, selected: SelectedReceipts, *, before_commit: Callable[[], None] | None = None,
) -> FinalReport:
    snapshot = ReportSnapshot(request, minimum, maximum, verdict)
    parents = snapshot_parents(selected)
    return archive.commit_report(snapshot, parents, before_commit=before_commit)

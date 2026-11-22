"""Check both issued revisions, a single setting and a second closed domain."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from bench.batches import BatchInput
from bench.calibration import NamedCalibration
from bench.pairing import PhysicalPair
from demo import batch_from_fixture, correction, issue_at_station, load_fixture
from receipt.admit import admit
from receipt.custody import ReceiptStore
from report.archive import ReportArchive
from report.retrieve import get_report
from report.trace import ParentRef
from review.evaluate import assess

MARKER = "BENCH_RETEST_CLOSED_DOMAIN_MISMATCH"


def interior_batch(bench, left):
    pair = PhysicalPair(
        "interior-" + bench, "local-specimen-" + bench, left, 0, "mm", "mm",
        NamedCalibration(0, {"u": 1, "v": 0}),
    )
    return BatchInput(bench, "interior", ("u", "v"), (pair,))


def run(root):
    batch_a = batch_from_fixture(load_fixture("bench-a.json"))
    batch_b = batch_from_fixture(load_fixture("bench-b.json"))
    request = load_fixture("review.json")
    path_a, path_b = root / "a.sqlite3", root / "b.sqlite3"
    original = issue_at_station(path_a, batch_a)
    other = issue_at_station(path_b, batch_b)
    amended = issue_at_station(path_a, correction(batch_a, request["amendment"], original.revision_id))
    inner_a = issue_at_station(path_a, interior_batch("A", "1/4"))
    inner_b = issue_at_station(path_b, interior_batch("B", "1/2"))
    cases = (
        ("original", (original, other), request["bounds"], ["3/4", "1", "none"]),
        ("amended", (amended, other), request["bounds"], ["1/2", "1", "some"]),
        ("original-point", (original, other), {"u": ("1/4", "1/4"), "v": (0, 0)},
         ["3/4", "3/4", "none"]),
        ("interior", (inner_a, inner_b), {"u": (-1, 1), "v": (0, 0)}, ["1/2", "1", "some"]),
    )
    center_path = root / "center.sqlite3"
    reports = []
    outcomes = []
    with closing(sqlite3.connect(center_path)) as center:
        receipts = ReceiptStore(center)
        archive = ReportArchive(center)
        receipts.initialize()
        archive.initialize()
        receipt_by_issue = {(item.bench, item.issue_id): admit(receipts, item.wire)
                            for item in (original, other, amended, inner_a, inner_b)}
        for name, issues, bounds, expected in cases:
            ids = tuple(receipt_by_issue[item.bench, item.issue_id] for item in issues)
            report = assess(receipts, archive, tuple(request["benches"]), ids, bounds, request["threshold"])
            parents = tuple(ParentRef(item.bench, receipt_id, item.issue_id, item.revision_id)
                            for item, receipt_id in zip(issues, ids))
            if report.parents != parents:
                raise RuntimeError(f"{name}: report did not retain the two received parents")
            reports.append(report)
            snapshot = report.snapshot
            actual = [str(snapshot.minimum_p), str(snapshot.maximum_p), snapshot.verdict.value]
            outcomes.append({"case": name, "actual": actual, "expected": expected})
    with closing(sqlite3.connect(center_path)) as center:
        archive = ReportArchive(center)
        for report in reports:
            if get_report(archive, report.report_id) != report:
                raise RuntimeError(f"report {report.report_id}: signed snapshot changed after reopening")

    for outcome in outcomes:
        print(json.dumps(outcome, sort_keys=True))
    if any(outcome["actual"] != outcome["expected"] for outcome in outcomes):
        print(MARKER)
        return 1
    return 0


def main():
    with TemporaryDirectory() as directory:
        return run(Path(directory))


if __name__ == "__main__":
    raise SystemExit(main())

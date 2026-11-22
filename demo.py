import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, replace
from pathlib import Path
from tempfile import TemporaryDirectory

from bench.batches import BatchInput, record
from bench.calibration import NamedCalibration
from bench.pairing import PhysicalPair
from bench.revisions import RevisionStore
from issue.register import IssueRegister, export
from receipt.admit import admit
from receipt.custody import ReceiptStore
from report.archive import ReportArchive
from report.records import encode_report
from report.retrieve import get_report
from review.evaluate import assess


def load_fixture(name):
    path = Path(__file__).resolve().parent / 'examples' / name
    return json.loads(path.read_text(encoding='utf-8'))


def batch_from_fixture(data):
    pairs = tuple(
        PhysicalPair(
            row['pair_id'], row['specimen'], row['left'], row['right'], row['left_unit'], row['right_unit'],
            NamedCalibration(row['offset'], row['coefficients']),
        )
        for row in data['pairs']
    )
    return BatchInput(data['bench'], data['batch'], tuple(data['settings']), pairs)


def issue_at_station(path, batch):
    with closing(sqlite3.connect(path)) as source:
        revisions = RevisionStore(source)
        register = IssueRegister(source)
        revisions.initialize()
        register.initialize()
        revision = record(revisions, batch)
        return export(revisions, register, batch.bench, revision)


def correction(batch, amendment, parent_id):
    target = next(pair for pair in batch.pairs if pair.pair_id == amendment['pair_id'])
    coefficients = dict(target.calibration.coefficients)
    coefficients[amendment['setting']] = amendment['coefficient']
    fixed = replace(target, calibration=replace(target.calibration, coefficients=coefficients))
    return replace(batch, pairs=tuple(fixed if pair is target else pair for pair in batch.pairs), parent_id=parent_id)


def view(report):
    return {'report_id': report.report_id, **json.loads(encode_report(report.snapshot)),
            'parents': [asdict(parent) for parent in report.parents]}


def main():
    batch_a = batch_from_fixture(load_fixture('bench-a.json'))
    batch_b = batch_from_fixture(load_fixture('bench-b.json'))
    request = load_fixture('review.json')
    with TemporaryDirectory() as directory:
        root = Path(directory)
        center_path = root / 'center.sqlite3'
        with closing(sqlite3.connect(center_path)) as center:
            receipts = ReceiptStore(center)
            archive = ReportArchive(center)
            receipts.initialize()
            archive.initialize()
            issued_a = issue_at_station(root / 'a.sqlite3', batch_a)
            issued_b = issue_at_station(root / 'b.sqlite3', batch_b)
            received_a = admit(receipts, issued_a.wire)
            received_b = admit(receipts, issued_b.wire)
            original = assess(receipts, archive, request['benches'], (received_a, received_b), request['bounds'], request['threshold'])
            updated_batch = correction(batch_a, request['amendment'], issued_a.revision_id)
            amended_issue = issue_at_station(root / 'a.sqlite3', updated_batch)
            amended_receipt = admit(receipts, amended_issue.wire)
            amended = assess(receipts, archive, request['benches'], (amended_receipt, received_b), request['bounds'], request['threshold'])
        with closing(sqlite3.connect(center_path)) as center:
            ReceiptStore(center).initialize()
            archive = ReportArchive(center)
            archive.initialize()
            historical = get_report(archive, original.report_id)
            amended_readback = get_report(archive, amended.report_id)

        actual = {
            'original': [str(original.snapshot.minimum_p), str(original.snapshot.maximum_p), original.snapshot.verdict.value],
            'amended': [str(amended.snapshot.minimum_p), str(amended.snapshot.maximum_p), amended.snapshot.verdict.value],
        }
        expected = {'original': ['3/4', '1', 'none'], 'amended': ['1/2', '1', 'some']}
        expected_parents = [[received_a, received_b], [amended_receipt, received_b]]
        actual_parents = [[parent.receipt_id for parent in report.parents] for report in (original, amended)]
        if actual != expected or actual_parents != expected_parents or historical != original or amended_readback != amended:
            raise RuntimeError('demo result differs from the hand calculation or stored reports')
        print(json.dumps({'original': view(original), 'amended': view(amended), 'retrieved': view(historical)}, sort_keys=True))
        print('POINTWISE_SCENARIO ' + json.dumps({
            'case_id': 'v6',
            'input': {'before': ['1+u', '1-u', '-1'], 'after': ['1+u', '1+u', '-1'],
                      'bounds': request['bounds'], 'threshold': request['threshold']},
            'expected': expected,
            'actual': actual,
            'downstream_expected': {'receipt_ids': expected_parents, 'old_snapshot_retrieved': True},
            'downstream_actual': {'receipt_ids': actual_parents, 'old_snapshot_retrieved': historical == original},
            'code_paths': ['bench/batches.py', 'issue/evidence.py', 'receipt/admit.py', 'review/evaluate.py', 'report/archive.py'],
            'oracle': 'Enumerate eight sign flips at each side of u=0 and at u=0 using the hand-ranked three differences. Compare the retrieved object to the original signed snapshot.',
        }, sort_keys=True))


if __name__ == '__main__':
    main()

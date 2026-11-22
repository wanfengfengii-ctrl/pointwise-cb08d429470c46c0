import sqlite3
from fractions import Fraction as F
from itertools import product

from report.retrieve import get_report
from report.trace import ParentRef
from review.verdict import RetestVerdict
from tests.fixtures import LINE, POINT, LabCase, pair


class OfflineTests(LabCase):
    def assert_result(self, report, lower, upper, verdict):
        self.assertEqual((report.snapshot.minimum_p, report.snapshot.maximum_p, report.snapshot.verdict), (lower, upper, verdict))

    def test_v3_offline_threshold_equality_parents_and_missing_report(self):
        a, ar = self.received('A', (pair('a', 1),))
        b, br = self.received('B', (pair('b', 2),))
        self.close_sources()
        report = self.assess((ar, br))
        self.assert_result(report, F(1, 2), F(1, 2), RetestVerdict.ALL)
        self.assertEqual(report.parents, (ParentRef('A', ar, a.issue_id, a.revision_id), ParentRef('B', br, b.issue_id, b.revision_id)))
        self.assertEqual(report.snapshot.request.domain.as_mapping(), {'u': (F(-1, 2), F(1, 2)), 'v': (0, 0)})
        self.assertEqual(report.snapshot.request.threshold, F(1, 2))
        self.assertEqual(get_report(self.archive, report.report_id), report)
        self.assertIsNone(get_report(self.archive, report.report_id + 100))
        self.assertEqual((self.count_reports(), self.count_parents()), (1, 2))

    def test_v5_closed_line_and_tie_point(self):
        _, ar = self.received('A', (pair('a1', 1, u=1), pair('a2', 1, u=-1)))
        _, br = self.received('B', (pair('b', -1, v=2),), settings=('v', 'u'))
        self.close_sources()
        # Off the tie the middle absolute rank is negative, with six of eight
        # flips in the tail. At the tie all eight flips reach the observed sum.
        self.assert_result(self.assess((ar, br)), F(3, 4), F(1), RetestVerdict.NONE)
        self.assert_result(self.assess((ar, br), POINT), F(1), F(1), RetestVerdict.NONE)

    def test_v5_full_rectangle_and_named_request_order(self):
        _, ar = self.received('A', (pair('a1', 1, u=1, v=1), pair('a2', 1, u=-1, v=1)))
        _, br = self.received('B', (pair('b', -1),))
        self.close_sources()
        bounds = {'u': ('-1/2', '1/2'), 'v': ('-1/4', '1/4')}
        for u, v in product(bounds['u'], bounds['v']):
            corner = self.assess((ar, br), {'u': (u, u), 'v': (v, v)})
            self.assert_result(corner, F(3, 4), F(3, 4), RetestVerdict.NONE)
        first = self.assess((ar, br), bounds)
        reordered = self.assess((ar, br), {'v': bounds['v'], 'u': bounds['u']})
        self.assert_result(first, F(1, 2), F(1), RetestVerdict.SOME)
        self.assertEqual(first.snapshot, reordered.snapshot)
        self.assertEqual(first.parents, reordered.parents)

    def test_v5_zero_point_counts_equal_pairs_and_handles_all_zero(self):
        _, ar = self.received('A', (pair('zero'), pair('positive-a', 1)))
        _, br = self.received('B', (pair('positive-b', 1),))
        _, zero_a = self.received('A', (pair('all-zero-a'),))
        _, zero_b = self.received('B', (pair('all-zero-b'),))
        self.close_sources()
        self.assert_result(self.assess((ar, br), POINT), F(1, 2), F(1, 2), RetestVerdict.ALL)
        self.assert_result(self.assess((zero_a, zero_b), POINT, 1), F(1), F(1), RetestVerdict.ALL)

    def test_v5_zero_on_closed_edge_and_vertical_domain(self):
        _, ar = self.received('A', (pair('variable', v=1), pair('positive', 1)))
        _, br = self.received('B', (pair('greater', 2),))
        self.close_sources()
        for u_bounds in ((0, 0), (-1, 1)):
            with self.subTest(u_bounds=u_bounds):
                report = self.assess((ar, br), {'u': u_bounds, 'v': (0, '1/2')}, '1/4')
                self.assert_result(report, F(1, 4), F(1, 2), RetestVerdict.SOME)

    def test_v7_wrong_bench_missing_receipt_and_invalid_request_leave_no_report(self):
        _, ar = self.received('A', (pair('a', 1),))
        _, second_a = self.received('A', (pair('a-next', 2),))
        _, br = self.received('B', (pair('b', 2),))
        _, wrong_names = self.received('B', (pair('b-other', 2),)) if False else (None, None)
        self.close_sources()
        with self.assertRaisesRegex(ValueError, 'requested benches'):
            self.assess((ar, second_a))
        with self.assertRaises(LookupError):
            self.assess((ar, br + 100))
        cases = (
            ({'u': (1, 0), 'v': (0, 0)}, '1/2'),
            ({'u': (0, 0)}, '1/2'),
            ({**LINE, 'other': (0, 0)}, '1/2'),
            ({'u': ('not rational', 1), 'v': (0, 0)}, '1/2'),
            ({'u': (False, 1), 'v': (0, 0)}, '1/2'),
            (LINE, '-1/10'),
            (LINE, '11/10'),
            (LINE, None),
        )
        for bounds, threshold in cases:
            with self.subTest(bounds=bounds, threshold=threshold), self.assertRaises(ValueError):
                self.assess((ar, br), bounds, threshold)
        self.assertEqual((self.count_reports(), self.count_parents()), (0, 0))

    def test_v7_incompatible_evidence_names_leave_no_report(self):
        from bench.calibration import NamedCalibration
        from bench.pairing import PhysicalPair

        _, ar = self.received('A', (pair('a', 1),))
        other_pair = PhysicalPair('b', 'private-b', 2, 0, 'mm', 'mm', NamedCalibration(0, {'u': 0, 'w': 0}))
        _, br = self.received('B', (other_pair,), settings=('u', 'w'))
        self.close_sources()
        with self.assertRaisesRegex(ValueError, 'share the same named settings'):
            self.assess((ar, br))
        self.assertEqual((self.count_reports(), self.count_parents()), (0, 0))

    def test_v8_precommit_failure_rolls_back_report_and_parents_then_retry(self):
        _, ar = self.received('A', (pair('a', 1),))
        _, br = self.received('B', (pair('b', 2),))
        self.close_sources()
        previous = self.assess((ar, br))
        reader = self.connection('center')

        def fail_before_commit():
            self.assertEqual((self.count_reports(), self.count_parents()), (2, 4))
            self.assertEqual(reader.execute('SELECT count(*) FROM reports').fetchone()[0], 1)
            raise sqlite3.OperationalError('publication interrupted before commit')

        with self.assertRaisesRegex(sqlite3.OperationalError, 'interrupted'):
            self.assess((ar, br), before_commit=fail_before_commit)
        self.assertEqual((self.count_reports(), self.count_parents()), (1, 2))
        self.assertEqual(get_report(self.archive, previous.report_id), previous)
        report = self.assess((ar, br))
        self.assert_result(report, F(1, 2), F(1, 2), RetestVerdict.ALL)
        self.assertEqual(report.parents, previous.parents)
        self.assertNotEqual(report.report_id, previous.report_id)
        self.assertEqual((self.count_reports(), self.count_parents()), (2, 4))
        self.assertEqual(get_report(self.archive, report.report_id), report)

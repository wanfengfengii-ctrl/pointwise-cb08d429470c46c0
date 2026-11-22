from fractions import Fraction as F

from issue.codec import decode_evidence
from issue.envelope import unpack_envelope
from receipt.admit import admit
from report.retrieve import get_report
from report.trace import ParentRef
from review.verdict import RetestVerdict
from tests.fixtures import LabCase, pair


class AmendmentTests(LabCase):
    def test_v6_same_marginals_explicit_revision_fixed_parents_and_reopen(self):
        first = pair('a1', 1, u=1)
        old_issue, old_a = self.received('A', (first, pair('a2', 1, u=-1)))
        right_issue, right_b = self.received('B', (pair('b', -1),))
        self.close_sources()
        old_report = self.assess((old_a, right_b))
        self.assertEqual((old_report.snapshot.minimum_p, old_report.snapshot.maximum_p, old_report.snapshot.verdict), (F(3, 4), F(1), RetestVerdict.NONE))

        self.open_source('A')
        amended = self.record('A', (first, pair('a2', 1, u=1)), parent=old_issue.revision_id)
        old_again = self.issue('A', old_issue.revision_id)
        new_issue = self.issue('A', amended)
        self.revisions('A').initialize()
        self.issues('A').initialize()
        self.assertEqual(self.revisions('A').find('A', amended).parent_id, old_issue.revision_id)
        self.assertEqual(self.issues('A').get(old_issue.issue_id), old_issue)
        self.assertEqual(self.issues('A').get(old_again.issue_id), old_again)
        self.assertEqual(self.issues('A').get(new_issue.issue_id), new_issue)
        self.assertEqual(self.sources['A'].execute('SELECT count(*) FROM revisions').fetchone()[0], 2)
        old_envelope = unpack_envelope(old_again.wire)
        new_envelope = unpack_envelope(new_issue.wire)
        self.assertEqual((old_envelope.revision_id, new_envelope.revision_id), (old_issue.revision_id, amended))
        self.assertEqual(old_envelope.body, unpack_envelope(old_issue.wire).body)
        old_differences = decode_evidence(old_envelope.body).differences
        new_differences = decode_evidence(new_envelope.body).differences

        def endpoint_values(differences):
            return tuple((constant - slope / 2, constant + slope / 2) for constant, slope, _ in differences)

        old_values = endpoint_values(old_differences)
        new_values = endpoint_values(new_differences)
        self.assertEqual(old_values, ((F(1, 2), F(3, 2)), (F(3, 2), F(1, 2))))
        self.assertEqual(new_values, ((F(1, 2), F(3, 2)), (F(1, 2), F(3, 2))))
        self.assertEqual(tuple(map(sorted, old_values)), tuple(map(sorted, new_values)))

        new_a = admit(self.receipts, new_issue.wire)
        self.close_sources()
        new_report = self.assess((new_a, right_b))
        self.assertEqual((new_report.snapshot.minimum_p, new_report.snapshot.maximum_p, new_report.snapshot.verdict), (F(1, 2), F(1), RetestVerdict.SOME))
        parent_b = ParentRef('B', right_b, right_issue.issue_id, right_issue.revision_id)
        self.assertEqual(old_report.parents, (ParentRef('A', old_a, old_issue.issue_id, old_issue.revision_id), parent_b))
        self.assertEqual(new_report.parents, (ParentRef('A', new_a, new_issue.issue_id, amended), parent_b))
        self.center.close()
        self.open_center()
        self.receipts.initialize()
        self.archive.initialize()
        self.assertEqual(self.receipts.find_by_id(old_a).wire, old_issue.wire)
        self.assertEqual(self.receipts.find_by_id(new_a).wire, new_issue.wire)
        self.assertEqual(self.receipts.find_by_id(right_b).wire, right_issue.wire)
        self.assertEqual(self.center.execute('SELECT count(*) FROM receipts').fetchone()[0], 3)
        self.assertEqual(get_report(self.archive, old_report.report_id), old_report)
        self.assertEqual(get_report(self.archive, new_report.report_id), new_report)
        self.assertEqual((self.count_reports(), self.count_parents()), (2, 4))
        replay = self.assess((old_a, right_b))
        self.assertEqual((replay.snapshot, replay.parents), (old_report.snapshot, old_report.parents))
        self.assertNotEqual(replay.report_id, old_report.report_id)

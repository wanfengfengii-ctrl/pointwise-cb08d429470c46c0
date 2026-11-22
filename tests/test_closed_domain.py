"""Regressions for the night-shift retest incident.

Two independent defects made the original and amended revisions report the
same [1/2, 1] / some outcome at threshold 1/2:

1. issue.evidence.build_evidence stored abs() of the two setting coefficients,
   so the frozen station item lost the signed affine differences (1-u became
   1+u) and the original revision scored like the amended one.
2. review.evaluate.evaluate_extrema sampled only the four rectangle corners,
   missing extrema at interior or edge zero/tie features of the closed domain
   (e.g. the u=0 tie point where p=1, or an interior cell minimum).
"""
from fractions import Fraction as F

from issue.codec import decode_evidence
from issue.envelope import unpack_envelope
from issue.evidence import EvidenceBody
from review.domain import parse_setting_domain
from review.evaluate import evaluate_extrema
from review.signed_rank import exact_signed_rank_p
from review.verdict import RetestVerdict
from tests.fixtures import LabCase, pair


class SignedEvidenceTests(LabCase):
    def test_signed_coefficients_survive_export(self):
        issued = self.issue('A', self.record('A', (pair('a', 1, u=-1, v='-1/3'),)))
        body = decode_evidence(unpack_envelope(issued.wire).body)
        self.assertEqual(body.settings, ('u', 'v'))
        self.assertEqual(body.differences, ((F(1), F(-1), F(-1, 3)),))
        for private_value in (b'private-a', b'left', b'right'):
            self.assertNotIn(private_value, issued.wire)

    def test_sign_flip_changes_segment_outcome(self):
        # 1+u and 1-u reach p=3/4 at the segment ends and p=1 at the interior
        # tie u=0; with the sign lost both forms read 1+u and the min drops.
        _, ar = self.received('A', (pair('a1', 1, u=1), pair('a2', 1, u=-1)))
        _, br = self.received('B', (pair('b', -1),))
        self.close_sources()
        report = self.assess((ar, br))
        self.assertEqual(
            (report.snapshot.minimum_p, report.snapshot.maximum_p, report.snapshot.verdict),
            (F(3, 4), F(1), RetestVerdict.NONE),
        )


class ClosedDomainExtremaTests(LabCase):
    def assert_result(self, report, lower, upper, verdict):
        self.assertEqual(
            (report.snapshot.minimum_p, report.snapshot.maximum_p, report.snapshot.verdict),
            (lower, upper, verdict),
        )

    def test_segment_interior_zero_and_tie_points_set_the_maximum(self):
        _, ar = self.received('A', (pair('a', '1/4', u=1),))
        _, br = self.received('B', (pair('b', '1/2', u=1),))
        self.close_sources()
        # Both corners score 1/2; the maximum 1 is reached only at the interior
        # zero points u=-1/2, u=-1/4 and the tie point u=-3/8.
        self.assert_result(self.assess((ar, br), {'u': (-1, 1), 'v': (0, 0)}), F(1, 2), F(1), RetestVerdict.SOME)

    def test_rectangle_interior_lines_set_the_maximum(self):
        _, ar = self.received('A', (pair('a', '1/4', u=1),))
        _, br = self.received('B', (pair('b', '1/2', u=1),))
        self.close_sources()
        # All four corners score 1/2; interior vertical zero/tie lines reach 1.
        self.assert_result(self.assess((ar, br), {'u': (-1, 1), 'v': (-1, 1)}), F(1, 2), F(1), RetestVerdict.SOME)

    def test_degenerate_point_domain_off_the_tie(self):
        _, ar = self.received('A', (pair('a1', 1, u=1), pair('a2', 1, u=-1)))
        _, br = self.received('B', (pair('b', -1),))
        self.close_sources()
        self.assert_result(self.assess((ar, br), {'u': ('1/4', '1/4'), 'v': (0, 0)}), F(3, 4), F(3, 4), RetestVerdict.NONE)

    def test_evaluate_extrema_aligns_named_settings(self):
        body_a = EvidenceBody(('u', 'v'), ((F(1), F(1), F(0)), (F(1), F(-1), F(0))))
        body_b = EvidenceBody(('v', 'u'), ((F(-1), F(0), F(0)),))
        domain = parse_setting_domain(('u', 'v'), {'u': ('-1/2', '1/2'), 'v': (0, 0)})
        self.assertEqual(evaluate_extrema((body_a, body_b), domain), (F(3, 4), F(1)))

    def test_interior_cell_minimum_below_every_corner(self):
        body_a = EvidenceBody(('u', 'v'), (
            (F(1), F(1), F(1)), (F(-1, 2), F(2), F(-1)), (F(0), F(1), F(-2)),
        ))
        body_b = EvidenceBody(('u', 'v'), (
            (F(3, 4), F(-1), F(0)), (F(-3, 2), F(0), F(1)), (F(2), F(-1), F(-1)),
        ))
        bounds = {'u': ('-3/2', 2), 'v': (-1, '3/2')}
        domain = parse_setting_domain(('u', 'v'), bounds)
        minimum, maximum = evaluate_extrema((body_a, body_b), domain)
        # The minimum 3/16 is attained at the interior point (17/50, 4/25);
        # the corners only reach 7/16..15/16.
        self.assertEqual((minimum, maximum), (F(3, 16), F(1)))
        aligned = tuple(body_a.differences) + tuple(body_b.differences)
        for i in range(-6, 9):
            for j in range(-4, 7):
                u, v = F(i, 4), F(j, 4)
                if F(-3, 2) <= u <= 2 and F(-1) <= v <= F(3, 2):
                    p = exact_signed_rank_p(c + a * u + b * v for c, a, b in aligned)
                    self.assertLessEqual(minimum, p)
                    self.assertLessEqual(p, maximum)

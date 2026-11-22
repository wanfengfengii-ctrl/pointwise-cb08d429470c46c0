from dataclasses import replace
from fractions import Fraction as F

from bench.calibration import NamedCalibration
from bench.pairing import PhysicalPair
from issue.codec import decode_evidence, encode_evidence
from issue.envelope import pack_envelope, unpack_envelope
from tests.fixtures import LabCase, pair


class IssueTests(LabCase):
    def test_v1_units_original_readings_and_same_value_pair_count(self):
        calibrated = PhysicalPair(
            'physical-first', 'private-specimen', '1/2', 4500, 'cm', 'um',
            NamedCalibration('1/2', {'v': '0', 'u': '1/3'}),
        )
        matching = pair('physical-second', 1, u='1/3')
        revision_id = self.record('A', (calibrated, matching))
        revision = self.revisions('A').find('A', revision_id)
        self.assertEqual((revision.bench, revision.batch, revision.parent_id), ('A', 'day', None))
        original = revision.pairs[0]
        self.assertEqual((original.left, original.left_unit, original.right, original.right_unit), (F(1, 2), 'cm', 4500, 'um'))
        self.assertEqual(original.specimen, 'private-specimen')
        issued = self.issue('A', revision_id)
        envelope = unpack_envelope(issued.wire)
        self.assertEqual((envelope.bench, envelope.issue_id, envelope.revision_id), ('A', issued.issue_id, revision_id))
        body = decode_evidence(envelope.body)
        self.assertEqual(body.settings, ('u', 'v'))
        self.assertEqual(body.differences, ((1, F(1, 3), 0), (1, F(1, 3), 0)))
        self.assertEqual(pack_envelope(replace(envelope, body=encode_evidence(body))), issued.wire)
        self.assertEqual(self.issues('A').get(issued.issue_id), issued)
        for private_value in (b'private-specimen', b'physical-first', b'physical-second', b'4500', b'left_unit'):
            self.assertNotIn(private_value, issued.wire)

    def test_v1_wrong_export_has_no_issuance(self):
        b_revision = self.record('B', (pair('b', 1),))
        for revision in (b_revision, b_revision + 100):
            with self.subTest(revision=revision), self.assertRaises(LookupError):
                self.issue('A', revision)
        self.assertEqual(self.sources['A'].execute('SELECT count(*) FROM issued').fetchone()[0], 0)

    def test_v2_duplicate_amendment_keeps_old_revision_issuable(self):
        old_id = self.record('A', (pair('old', '3/2'),))
        duplicate = (pair('duplicated', 2, u=1), pair('duplicated', 3, u=-1))
        with self.assertRaisesRegex(ValueError, 'duplicate physical pair'):
            self.record('A', duplicate, parent=old_id)
        self.assertEqual(self.sources['A'].execute('SELECT count(*) FROM revisions').fetchone()[0], 1)
        old_issue = self.issue('A', old_id)
        old_envelope = unpack_envelope(old_issue.wire)
        self.assertEqual(old_envelope.revision_id, old_id)
        self.assertEqual(decode_evidence(old_envelope.body).differences, ((F(3, 2), 0, 0),))

    def test_v2_bad_parent_and_invalid_calibration_are_rejected(self):
        old_id = self.record('A', (pair('old', 1),))
        b_id = self.record('B', (pair('b', 2),))
        with self.assertRaisesRegex(ValueError, 'parent revision'):
            self.record('A', (pair('edited', 2),), parent=old_id, batch='other')
        with self.assertRaisesRegex(ValueError, 'parent revision'):
            self.record('B', (pair('edited', 2),), parent=b_id + 100)
        for invalid in (
            pair('bad', 4, u='2/0'),
            pair('bad', 4, u=0.5),
            replace(pair('bad', 4), right_unit='unsupported'),
            replace(pair('bad', 4), left=None),
            replace(pair('bad', 4), calibration=NamedCalibration(0, {'u': 1})),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.record('A', (invalid,), parent=old_id)
        for invalid_pairs in ((), tuple(pair(str(index), index) for index in range(4))):
            with self.assertRaises(ValueError):
                self.record('A', invalid_pairs)
        self.assertEqual(self.sources['A'].execute('SELECT count(*) FROM revisions').fetchone()[0], 1)
        self.assertEqual(self.sources['B'].execute('SELECT count(*) FROM revisions').fetchone()[0], 1)
        self.assertEqual(self.issue('A', old_id).revision_id, old_id)

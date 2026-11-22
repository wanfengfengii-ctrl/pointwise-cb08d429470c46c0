import json
from dataclasses import replace
from fractions import Fraction

from issue.codec import decode_evidence, encode_evidence
from issue.envelope import pack_envelope, unpack_envelope
from receipt.admit import admit
from receipt.validate import validate_issue
from tests.fixtures import LabCase, pair


class ReceiptTests(LabCase):
    def test_v4_byte_replay_and_valid_same_number_conflict(self):
        original, receipt_id = self.received('A', (pair('a', 1),))
        self.assertEqual(admit(self.receipts, original.wire), receipt_id)
        envelope = unpack_envelope(original.wire)
        body = decode_evidence(envelope.body)
        different_body = replace(body, differences=((Fraction(2), Fraction(0), Fraction(0)),))
        different_wire = pack_envelope(replace(envelope, body=encode_evidence(different_body)))
        validated = validate_issue(different_wire)
        self.assertEqual(validated.envelope.issue_id, original.issue_id)
        self.assertNotEqual(different_wire, original.wire)
        with self.assertRaisesRegex(ValueError, 'different bytes'):
            admit(self.receipts, different_wire)
        with self.assertRaisesRegex(ValueError, 'different bytes'):
            admit(self.receipts, original.wire + b'\n')
        stored = self.receipts.find_by_issue('A', original.issue_id)
        self.assertEqual((stored.receipt_id, stored.revision_id, stored.wire), (receipt_id, original.revision_id, original.wire))
        self.assertEqual(self.center.execute('SELECT count(*) FROM receipts').fetchone()[0], 1)
        other, other_id = self.received('B', (pair('b', -1),))
        self.assertEqual(other.issue_id, original.issue_id)
        self.assertNotEqual(other_id, receipt_id)

    def test_v4_invalid_outer_and_invalid_body_do_not_admit(self):
        original, receipt_id = self.received('A', (pair('a', 1),))
        outer = json.loads(original.wire)
        bad_checksum = json.dumps(dict(outer, sha256='0' * 64)).encode()
        wrong_version = json.dumps(dict(outer, version=True)).encode()
        envelope = unpack_envelope(original.wire)
        malformed_body = pack_envelope(replace(envelope, body=b'{"settings":["u","v"],"differences":[]}'))
        duplicate_field = original.wire.replace(b'"version":1', b'"version":1,"version":1')
        for invalid in (bad_checksum, wrong_version, malformed_body, duplicate_field, b'\xff'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                admit(self.receipts, invalid)
        self.assertEqual(self.center.execute('SELECT count(*) FROM receipts').fetchone()[0], 1)
        self.assertEqual(self.receipts.find_by_id(receipt_id).wire, original.wire)

from dataclasses import dataclass

from issue.codec import decode_evidence
from issue.envelope import IssueEnvelope, unpack_envelope


@dataclass(frozen=True)
class ValidatedIssue:
    envelope: IssueEnvelope
    wire: bytes


def validate_issue(wire: bytes) -> ValidatedIssue:
    envelope = unpack_envelope(wire)
    decode_evidence(envelope.body)
    return ValidatedIssue(envelope, wire)

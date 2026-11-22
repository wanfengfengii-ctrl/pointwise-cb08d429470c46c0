import hashlib
import json
from dataclasses import dataclass

from bench.pairing import has_name


@dataclass(frozen=True)
class IssueEnvelope:
    bench: str
    issue_id: int
    revision_id: int
    body: bytes


def _unique_keys(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON field')
        result[key] = value
    return result


def load_wire_object(wire: bytes) -> dict:
    if not isinstance(wire, bytes):
        raise ValueError('expected immutable V1 bytes')
    try:
        value = json.loads(wire.decode('utf-8'), object_pairs_hook=_unique_keys)
    except (ValueError, RecursionError) as exc:
        raise ValueError('invalid V1 JSON') from exc
    if not isinstance(value, dict):
        raise ValueError('expected a V1 JSON object')
    return value


def dump_wire_object(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def is_issue_number(value: object) -> bool:
    return type(value) is int and 0 < value < (1 << 63)


def pack_envelope(envelope: IssueEnvelope) -> bytes:
    return dump_wire_object({
        'version': 1,
        'bench': envelope.bench,
        'issue_id': envelope.issue_id,
        'revision_id': envelope.revision_id,
        'body': envelope.body.decode('utf-8'),
        'sha256': hashlib.sha256(envelope.body).hexdigest(),
    })


def unpack_envelope(wire: bytes) -> IssueEnvelope:
    data = load_wire_object(wire)
    if data.keys() != {'version', 'bench', 'issue_id', 'revision_id', 'body', 'sha256'}:
        raise ValueError('invalid V1 envelope fields')
    if type(data['version']) is not int or data['version'] != 1:
        raise ValueError('unsupported issue version')
    if not has_name(data['bench']):
        raise ValueError('invalid issue bench')
    if not is_issue_number(data['issue_id']) or not is_issue_number(data['revision_id']):
        raise ValueError('invalid issue or revision number')
    if not isinstance(data['body'], str):
        raise ValueError('issue body must be JSON text')
    body = data['body'].encode('utf-8')
    if data['sha256'] != hashlib.sha256(body).hexdigest():
        raise ValueError('issue body checksum mismatch')
    return IssueEnvelope(data['bench'], data['issue_id'], data['revision_id'], body)

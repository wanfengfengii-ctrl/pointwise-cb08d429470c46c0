from bench.calibration import parse_rational, setting_names
from issue.envelope import dump_wire_object, load_wire_object
from issue.evidence import EvidenceBody


def encode_evidence(evidence: EvidenceBody) -> bytes:
    return dump_wire_object({
        'settings': evidence.settings,
        'differences': [[str(value) for value in difference] for difference in evidence.differences],
    })


def decode_evidence(wire: bytes) -> EvidenceBody:
    data = load_wire_object(wire)
    if data.keys() != {'settings', 'differences'}:
        raise ValueError('invalid evidence fields')
    names = setting_names(data['settings'])
    rows = data['differences']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 3:
        raise ValueError('evidence needs one to three physical contributions')
    differences = []
    for row in rows:
        if not isinstance(row, list) or len(row) != 3 or not all(isinstance(x, str) for x in row):
            raise ValueError('expected a constant and two rational setting coefficients')
        constant, first, second = map(parse_rational, row)
        differences.append((constant, first, second))
    return EvidenceBody(names, tuple(differences))

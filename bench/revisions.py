import json
import sqlite3
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType

from bench.calibration import NamedCalibration, SettingNames
from bench.pairing import PhysicalPair


@dataclass(frozen=True)
class Revision:
    revision_id: int
    bench: str
    batch: str
    parent_id: int | None
    settings: SettingNames
    pairs: tuple[PhysicalPair, ...]


def _encode_payload(settings: SettingNames, pairs: tuple[PhysicalPair, ...]) -> str:
    return json.dumps({
        'settings': settings,
        'pairs': [
            {
                'pair_id': pair.pair_id,
                'specimen': pair.specimen,
                'left': str(pair.left),
                'right': str(pair.right),
                'left_unit': pair.left_unit,
                'right_unit': pair.right_unit,
                'offset': str(pair.calibration.offset),
                'coefficients': {name: str(pair.calibration.coefficients[name]) for name in settings},
            }
            for pair in pairs
        ],
    })


def _decode_payload(payload: str) -> tuple[SettingNames, tuple[PhysicalPair, ...]]:
    data = json.loads(payload)
    first, second = data['settings']
    pairs = tuple(
        PhysicalPair(
            pair['pair_id'], pair['specimen'], Fraction(pair['left']), Fraction(pair['right']),
            pair['left_unit'], pair['right_unit'], NamedCalibration(
                Fraction(pair['offset']),
                MappingProxyType({name: Fraction(value) for name, value in pair['coefficients'].items()}),
            ),
        )
        for pair in data['pairs']
    )
    return (first, second), pairs


class RevisionStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self) -> None:
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS revisions (
                revision_id INTEGER PRIMARY KEY,
                bench TEXT NOT NULL,
                batch TEXT NOT NULL,
                parent_id INTEGER REFERENCES revisions (revision_id),
                payload TEXT NOT NULL
            )
        ''')

    def find(self, bench: str, revision_id: int) -> Revision | None:
        if type(revision_id) is not int or not 0 < revision_id < (1 << 63):
            return None
        row = self.connection.execute(
            'SELECT batch, parent_id, payload FROM revisions WHERE bench = ? AND revision_id = ?',
            (bench, revision_id),
        ).fetchone()
        if row is None:
            return None
        batch, parent_id, payload = row
        settings, pairs = _decode_payload(payload)
        return Revision(revision_id, bench, batch, parent_id, settings, pairs)

    def insert(
        self, bench: str, batch: str, settings: SettingNames,
        pairs: tuple[PhysicalPair, ...], parent_id: int | None = None,
    ) -> int:
        payload = _encode_payload(settings, pairs)
        self.connection.execute('BEGIN IMMEDIATE')
        with self.connection:
            cursor = self.connection.execute(
                'INSERT INTO revisions (bench, batch, parent_id, payload) VALUES (?, ?, ?, ?)',
                (bench, batch, parent_id, payload),
            )
            revision_id = cursor.lastrowid
        return revision_id

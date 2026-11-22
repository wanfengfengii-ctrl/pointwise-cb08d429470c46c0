from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bench.calibration import NamedCalibration

RationalInput = int | str | Fraction


@dataclass(frozen=True)
class PhysicalPair:
    pair_id: str
    specimen: str
    left: RationalInput
    right: RationalInput
    left_unit: str
    right_unit: str
    calibration: NamedCalibration


def has_name(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_pairs(pairs: object) -> tuple[PhysicalPair, ...]:
    if not isinstance(pairs, (tuple, list)) or not 1 <= len(pairs) <= 3:
        raise ValueError('a revision needs one to three physical pairs')
    seen = set()
    for pair in pairs:
        if not isinstance(pair, PhysicalPair):
            raise ValueError('invalid physical pair')
        if not has_name(pair.pair_id) or not has_name(pair.specimen):
            raise ValueError('physical pair and private specimen names are required')
        if pair.pair_id in seen:
            raise ValueError('duplicate physical pair')
        seen.add(pair.pair_id)
    return tuple(pairs)

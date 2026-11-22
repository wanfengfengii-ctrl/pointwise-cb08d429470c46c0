from collections.abc import Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from types import MappingProxyType

from bench.pairing import PhysicalPair, RationalInput, has_name, validate_pairs

UNIT_IN_MM = {'mm': Fraction(1), 'cm': Fraction(10), 'um': Fraction(1, 1000)}
SettingNames = tuple[str, str]
AffineDifference = tuple[Fraction, Fraction, Fraction]


@dataclass(frozen=True)
class NamedCalibration:
    offset: RationalInput
    coefficients: Mapping[str, RationalInput]


def parse_rational(value: object) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, str, Fraction)):
        raise ValueError('expected an exact rational number')
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError('invalid rational number') from exc


def setting_names(values: object) -> SettingNames:
    if not isinstance(values, (tuple, list)) or len(values) != 2:
        raise ValueError('exactly two setting names are required')
    first, second = values
    if not has_name(first) or not has_name(second) or first == second:
        raise ValueError('setting names must be nonempty and distinct')
    return first, second


def normalize_calibration(calibration: NamedCalibration, names: SettingNames) -> NamedCalibration:
    if not isinstance(calibration, NamedCalibration):
        raise ValueError('named calibration is required')
    coefficients = calibration.coefficients
    if not isinstance(coefficients, Mapping) or coefficients.keys() != set(names):
        raise ValueError('calibration must provide both named coefficients')
    return NamedCalibration(
        parse_rational(calibration.offset),
        MappingProxyType({name: parse_rational(coefficients[name]) for name in names}),
    )


def unit_in_mm(unit: object) -> Fraction:
    if not isinstance(unit, str) or unit not in UNIT_IN_MM:
        raise ValueError('unsupported measurement unit')
    return UNIT_IN_MM[unit]


def normalize_pairs(pairs: object, names: SettingNames) -> tuple[PhysicalPair, ...]:
    normalized = []
    for pair in validate_pairs(pairs):
        unit_in_mm(pair.left_unit)
        unit_in_mm(pair.right_unit)
        normalized.append(replace(
            pair,
            left=parse_rational(pair.left),
            right=parse_rational(pair.right),
            calibration=normalize_calibration(pair.calibration, names),
        ))
    return tuple(normalized)


def calibrated_difference(pair: PhysicalPair, names: SettingNames) -> AffineDifference:
    calibration = normalize_calibration(pair.calibration, names)
    left = parse_rational(pair.left) * unit_in_mm(pair.left_unit)
    right = parse_rational(pair.right) * unit_in_mm(pair.right_unit)
    first, second = names
    return left - right + calibration.offset, calibration.coefficients[first], calibration.coefficients[second]

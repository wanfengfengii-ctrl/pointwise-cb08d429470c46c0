from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from bench.calibration import SettingNames, parse_rational, setting_names

ClosedInterval = tuple[Fraction, Fraction]


@dataclass(frozen=True)
class ClosedSettingDomain:
    names: SettingNames
    bounds: tuple[ClosedInterval, ClosedInterval]

    def as_mapping(self) -> dict[str, ClosedInterval]:
        return dict(zip(self.names, self.bounds))


def parse_setting_domain(names: SettingNames, bounds: object) -> ClosedSettingDomain:
    names = setting_names(names)
    if not isinstance(bounds, Mapping) or bounds.keys() != set(names):
        raise ValueError('request bounds must match the two setting names')
    parsed = []
    for name in names:
        interval = bounds[name]
        if not isinstance(interval, (tuple, list)) or len(interval) != 2:
            raise ValueError('each setting needs two closed bounds')
        lower, upper = map(parse_rational, interval)
        if lower > upper:
            raise ValueError('setting bounds are reversed')
        parsed.append((lower, upper))
    return ClosedSettingDomain(names, (parsed[0], parsed[1]))


def parse_threshold(value: object) -> Fraction:
    threshold = parse_rational(value)
    if not 0 <= threshold <= 1:
        raise ValueError('threshold is outside [0,1]')
    return threshold

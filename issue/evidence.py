from dataclasses import dataclass

from bench.calibration import AffineDifference, SettingNames, calibrated_difference
from issue.freeze import FrozenRevision


@dataclass(frozen=True)
class EvidenceBody:
    settings: SettingNames
    differences: tuple[AffineDifference, ...]


def build_evidence(snapshot: FrozenRevision) -> EvidenceBody:
    differences = []
    for pair in snapshot.pairs:
        center, first, second = calibrated_difference(pair, snapshot.settings)
        differences.append((center, first, second))
    return EvidenceBody(snapshot.settings, tuple(differences))

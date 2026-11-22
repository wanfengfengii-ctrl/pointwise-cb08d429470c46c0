from bench.calibration import SettingNames, normalize_pairs
from bench.pairing import PhysicalPair
from bench.revisions import RevisionStore


def build_amendment(
    store: RevisionStore, bench: str, batch: str, parent_id: int,
    settings: SettingNames, pairs: object,
) -> tuple[PhysicalPair, ...]:
    parent = store.find(bench, parent_id)
    if parent is None or parent.batch != batch:
        raise ValueError('parent revision must belong to the same bench and batch')
    return normalize_pairs(pairs, settings)

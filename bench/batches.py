from dataclasses import dataclass

from bench.amendments import build_amendment
from bench.calibration import SettingNames, normalize_pairs, setting_names
from bench.pairing import PhysicalPair, has_name
from bench.revisions import RevisionStore


@dataclass(frozen=True)
class BatchInput:
    bench: str
    batch: str
    settings: SettingNames
    pairs: tuple[PhysicalPair, ...]
    parent_id: int | None = None


def record(store: RevisionStore, submission: BatchInput) -> int:
    if not isinstance(submission, BatchInput):
        raise ValueError('expected a batch submission')
    if not has_name(submission.bench) or not has_name(submission.batch):
        raise ValueError('bench and batch names are required')
    names = setting_names(submission.settings)
    if submission.parent_id is None:
        pairs = normalize_pairs(submission.pairs, names)
    else:
        pairs = build_amendment(
            store, submission.bench, submission.batch, submission.parent_id, names, submission.pairs,
        )
    return store.insert(submission.bench, submission.batch, names, pairs, submission.parent_id)

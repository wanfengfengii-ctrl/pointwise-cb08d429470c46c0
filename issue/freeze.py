from dataclasses import dataclass

from bench.calibration import SettingNames
from bench.pairing import PhysicalPair, has_name
from bench.revisions import RevisionStore


@dataclass(frozen=True)
class FrozenRevision:
    bench: str
    revision_id: int
    settings: SettingNames
    pairs: tuple[PhysicalPair, ...]


def freeze_revision(store: RevisionStore, bench: str, revision_id: int) -> FrozenRevision:
    if not has_name(bench):
        raise ValueError('bench name is required')
    revision = store.find(bench, revision_id)
    if revision is None:
        raise LookupError('revision does not exist at the requested bench')
    return FrozenRevision(revision.bench, revision.revision_id, revision.settings, revision.pairs)

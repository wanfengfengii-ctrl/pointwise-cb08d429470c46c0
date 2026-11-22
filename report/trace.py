from collections.abc import Iterable
from dataclasses import dataclass

from receipt.selection import SelectedReceipts


@dataclass(frozen=True)
class ParentRef:
    bench: str
    receipt_id: int
    issue_id: int
    revision_id: int


def snapshot_parents(selected: SelectedReceipts) -> tuple[ParentRef, ParentRef]:
    first, second = (
        ParentRef(item.bench, item.receipt_id, item.issue_id, item.revision_id)
        for item in selected.records
    )
    return first, second


def restore_parent_refs(rows: Iterable[tuple[str, int, int, int]]) -> tuple[ParentRef, ParentRef]:
    parents = tuple(ParentRef(*row) for row in rows)
    if len(parents) != 2:
        raise RuntimeError('stored report is missing its two parent references')
    return parents[0], parents[1]

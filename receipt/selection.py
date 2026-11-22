from dataclasses import dataclass

from bench.pairing import has_name
from receipt.custody import ReceiptRecord, ReceiptStore


@dataclass(frozen=True)
class SelectedReceipts:
    first: ReceiptRecord
    second: ReceiptRecord

    @property
    def records(self) -> tuple[ReceiptRecord, ReceiptRecord]:
        return self.first, self.second


def select_receipts(
    store: ReceiptStore, benches: tuple[str, str], receipt_ids: tuple[int, int],
) -> SelectedReceipts:
    if not isinstance(benches, (list, tuple)) or len(benches) != 2:
        raise ValueError('two bench names are required')
    if not all(has_name(bench) for bench in benches) or benches[0] == benches[1]:
        raise ValueError('two distinct benches are required')
    if not isinstance(receipt_ids, (list, tuple)) or len(receipt_ids) != 2:
        raise ValueError('two receipt numbers are required')
    first, second = (store.find_by_id(receipt_id) for receipt_id in receipt_ids)
    if first is None or second is None:
        raise LookupError('requested receipt does not exist')
    if (first.bench, second.bench) != tuple(benches):
        raise ValueError('receipts do not belong to the two requested benches in order')
    return SelectedReceipts(first, second)

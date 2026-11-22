from receipt.custody import ReceiptStore
from receipt.validate import validate_issue


def admit(store: ReceiptStore, wire: bytes) -> int:
    validated = validate_issue(wire)
    envelope = validated.envelope
    with store.transaction():
        previous = store.find_by_issue(envelope.bench, envelope.issue_id)
        if previous is not None:
            if previous.wire != validated.wire:
                raise ValueError('different bytes for an already received issue')
            return previous.receipt_id
        return store.insert(envelope.bench, envelope.issue_id, envelope.revision_id, validated.wire)

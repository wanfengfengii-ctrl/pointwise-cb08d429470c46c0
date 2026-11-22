import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class ReceiptRecord:
    receipt_id: int
    bench: str
    issue_id: int
    revision_id: int
    wire: bytes


class ReceiptStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self) -> None:
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS receipts (
                receipt_id INTEGER PRIMARY KEY,
                bench TEXT NOT NULL,
                issue_id INTEGER NOT NULL,
                revision_id INTEGER NOT NULL,
                wire BLOB NOT NULL,
                UNIQUE (bench, issue_id)
            )
        ''')

    def transaction(self) -> sqlite3.Connection:
        self.connection.execute('BEGIN IMMEDIATE')
        return self.connection

    def find_by_issue(self, bench: str, issue_id: int) -> ReceiptRecord | None:
        row = self.connection.execute(
            'SELECT receipt_id, bench, issue_id, revision_id, wire FROM receipts WHERE bench = ? AND issue_id = ?',
            (bench, issue_id),
        ).fetchone()
        return None if row is None else ReceiptRecord(*row)

    def find_by_id(self, receipt_id: int) -> ReceiptRecord | None:
        if type(receipt_id) is not int or not 0 < receipt_id < (1 << 63):
            raise ValueError('invalid receipt number')
        row = self.connection.execute(
            'SELECT receipt_id, bench, issue_id, revision_id, wire FROM receipts WHERE receipt_id = ?',
            (receipt_id,),
        ).fetchone()
        return None if row is None else ReceiptRecord(*row)

    def insert(self, bench: str, issue_id: int, revision_id: int, wire: bytes) -> int:
        if not self.connection.in_transaction:
            raise RuntimeError('receipt insertion requires an active transaction')
        cursor = self.connection.execute(
            'INSERT INTO receipts (bench, issue_id, revision_id, wire) VALUES (?, ?, ?, ?)',
            (bench, issue_id, revision_id, wire),
        )
        return cursor.lastrowid

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

from report.records import ReportSnapshot, decode_report, encode_report
from report.trace import ParentRef, restore_parent_refs


@dataclass(frozen=True)
class FinalReport:
    report_id: int
    snapshot: ReportSnapshot
    parents: tuple[ParentRef, ParentRef]


class ReportArchive:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self) -> None:
        self.connection.execute('PRAGMA foreign_keys = ON')
        self.connection.execute('BEGIN IMMEDIATE')
        with self.connection:
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS reports (
                    report_id INTEGER PRIMARY KEY,
                    snapshot TEXT NOT NULL
                )
            ''')
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS report_parents (
                    report_id INTEGER NOT NULL REFERENCES reports (report_id),
                    position INTEGER NOT NULL CHECK (position IN (0, 1)),
                    bench TEXT NOT NULL,
                    receipt_id INTEGER NOT NULL,
                    issue_id INTEGER NOT NULL,
                    revision_id INTEGER NOT NULL,
                    PRIMARY KEY (report_id, position)
                )
            ''')

    def commit_report(
        self, snapshot: ReportSnapshot, parents: tuple[ParentRef, ParentRef],
        *, before_commit: Callable[[], None] | None = None,
    ) -> FinalReport:
        request = snapshot.request
        if (len(parents) != 2 or tuple(parent.bench for parent in parents) != request.benches
                or tuple(parent.receipt_id for parent in parents) != request.receipt_ids):
            raise ValueError('report parents do not match the assessed receipts')
        payload = encode_report(snapshot)
        self.connection.execute('BEGIN IMMEDIATE')
        with self.connection:
            cursor = self.connection.execute('INSERT INTO reports (snapshot) VALUES (?)', (payload,))
            report_id = cursor.lastrowid
            self.connection.executemany(
                '''INSERT INTO report_parents
                   (report_id, position, bench, receipt_id, issue_id, revision_id) VALUES (?, ?, ?, ?, ?, ?)''',
                ((report_id, position, parent.bench, parent.receipt_id, parent.issue_id, parent.revision_id)
                 for position, parent in enumerate(parents)),
            )
            if before_commit is not None:
                before_commit()
        return FinalReport(report_id, snapshot, parents)

    def find_report(self, report_id: int) -> FinalReport | None:
        if type(report_id) is not int or not 0 < report_id < (1 << 63):
            raise ValueError('invalid report number')
        row = self.connection.execute('SELECT snapshot FROM reports WHERE report_id = ?', (report_id,)).fetchone()
        if row is None:
            return None
        parent_rows = self.connection.execute(
            '''SELECT bench, receipt_id, issue_id, revision_id FROM report_parents
               WHERE report_id = ? ORDER BY position''', (report_id,),
        )
        return FinalReport(report_id, decode_report(row[0]), restore_parent_refs(parent_rows))

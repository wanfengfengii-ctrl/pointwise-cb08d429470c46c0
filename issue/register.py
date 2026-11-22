import sqlite3
from dataclasses import dataclass

from bench.revisions import RevisionStore
from issue.codec import encode_evidence
from issue.envelope import IssueEnvelope, is_issue_number, pack_envelope
from issue.evidence import build_evidence
from issue.freeze import freeze_revision


@dataclass(frozen=True)
class IssuedEvidence:
    bench: str
    issue_id: int
    revision_id: int
    wire: bytes


class IssueRegister:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def initialize(self) -> None:
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS issued (
                issue_id INTEGER PRIMARY KEY,
                bench TEXT NOT NULL,
                revision_id INTEGER NOT NULL,
                wire BLOB NOT NULL
            )
        ''')

    def append(self, bench: str, revision_id: int, body: bytes) -> IssuedEvidence:
        self.connection.execute('BEGIN IMMEDIATE')
        with self.connection:
            last_id, = self.connection.execute('SELECT COALESCE(MAX(issue_id), 0) FROM issued').fetchone()
            issue_id = last_id + 1
            wire = pack_envelope(IssueEnvelope(bench, issue_id, revision_id, body))
            self.connection.execute(
                'INSERT INTO issued (issue_id, bench, revision_id, wire) VALUES (?, ?, ?, ?)',
                (issue_id, bench, revision_id, wire),
            )
        return IssuedEvidence(bench, issue_id, revision_id, wire)

    def get(self, issue_id: int) -> IssuedEvidence | None:
        if not is_issue_number(issue_id):
            raise ValueError('invalid issue number')
        row = self.connection.execute(
            'SELECT bench, revision_id, wire FROM issued WHERE issue_id = ?', (issue_id,),
        ).fetchone()
        if row is None:
            return None
        bench, revision_id, wire = row
        return IssuedEvidence(bench, issue_id, revision_id, wire)


def export(revisions: RevisionStore, register: IssueRegister, bench: str, revision_id: int) -> IssuedEvidence:
    snapshot = freeze_revision(revisions, bench, revision_id)
    body = encode_evidence(build_evidence(snapshot))
    return register.append(snapshot.bench, snapshot.revision_id, body)

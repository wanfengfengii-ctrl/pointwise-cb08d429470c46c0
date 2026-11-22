import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bench.batches import BatchInput, record
from bench.calibration import NamedCalibration
from bench.pairing import PhysicalPair
from bench.revisions import RevisionStore
from issue.register import IssueRegister, export
from receipt.admit import admit
from receipt.custody import ReceiptStore
from report.archive import ReportArchive
from review.evaluate import assess


LINE = {'u': ('-1/2', '1/2'), 'v': (0, 0)}
POINT = {'u': (0, 0), 'v': (0, 0)}


def pair(name, constant=0, *, u=0, v=0):
    return PhysicalPair(name, 'private-' + name, constant, 0, 'mm', 'mm', NamedCalibration(0, {'u': u, 'v': v}))


class LabCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.sources = {}
        self.open_source('A')
        self.open_source('B')
        self.open_center()

    def connection(self, name):
        connection = sqlite3.connect(self.root / (name + '.sqlite3'))
        self.addCleanup(connection.close)
        return connection

    def open_source(self, bench):
        connection = self.connection(bench)
        self.sources[bench] = connection
        self.revisions(bench).initialize()
        self.issues(bench).initialize()

    def open_center(self):
        self.center = self.connection('center')
        self.receipts = ReceiptStore(self.center)
        self.archive = ReportArchive(self.center)
        self.receipts.initialize()
        self.archive.initialize()

    def close_sources(self):
        for connection in self.sources.values():
            connection.close()
        self.sources.clear()

    def revisions(self, bench):
        return RevisionStore(self.sources[bench])

    def issues(self, bench):
        return IssueRegister(self.sources[bench])

    def record(self, bench, pairs, *, parent=None, batch='day', settings=('u', 'v')):
        return record(self.revisions(bench), BatchInput(bench, batch, settings, tuple(pairs), parent))

    def issue(self, bench, revision):
        return export(self.revisions(bench), self.issues(bench), bench, revision)

    def received(self, bench, pairs, **kwargs):
        issue = self.issue(bench, self.record(bench, pairs, **kwargs))
        return issue, admit(self.receipts, issue.wire)

    def assess(self, ids, bounds=LINE, threshold='1/2', **kwargs):
        return assess(self.receipts, self.archive, ('A', 'B'), ids, bounds, threshold, **kwargs)

    def count_reports(self):
        return self.center.execute('SELECT count(*) FROM reports').fetchone()[0]

    def count_parents(self):
        return self.center.execute('SELECT count(*) FROM report_parents').fetchone()[0]

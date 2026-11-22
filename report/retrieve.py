from report.archive import FinalReport, ReportArchive


def get_report(archive: ReportArchive, report_id: int) -> FinalReport | None:
    return archive.find_report(report_id)

import pytest

from lacis.graph.progress import ExpansionProgress, ProgressTracker


def test_the_tracker_counts_requests_and_new_entities() -> None:
    reports: list[ExpansionProgress] = []
    tracker = ProgressTracker(reports.append)
    tracker.request_made()
    tracker.entities_found(3)
    tracker.request_made()
    tracker.entities_found(2)
    assert reports == [
        ExpansionProgress(1, 0),
        ExpansionProgress(1, 3),
        ExpansionProgress(2, 3),
        ExpansionProgress(2, 5),
    ]
    assert tracker.progress == ExpansionProgress(2, 5)


@pytest.mark.parametrize(
    ("progress", "summary"),
    [
        (ExpansionProgress(), "0 requête, 0 nouvelle entité"),
        (ExpansionProgress(1, 1), "1 requête, 1 nouvelle entité"),
        (ExpansionProgress(4, 12), "4 requêtes, 12 nouvelles entités"),
    ],
)
def test_the_progress_reads_in_french(progress: ExpansionProgress, summary: str) -> None:
    assert progress.summary == summary

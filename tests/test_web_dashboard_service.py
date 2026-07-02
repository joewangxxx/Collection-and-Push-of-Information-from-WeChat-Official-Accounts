from pathlib import Path

from market_info.web.services.dashboard_service import find_latest_report, mask_error


def test_find_latest_report_returns_newest_xlsx(tmp_path: Path) -> None:
    older = tmp_path / "market_info_weekly_20260624_102824.xlsx"
    newer = tmp_path / "market_info_weekly_20260629_103132.xlsx"
    ignored = tmp_path / "notes.txt"
    older.write_bytes(b"older")
    newer.write_bytes(b"newer")
    ignored.write_text("ignore", encoding="utf-8")

    report = find_latest_report(tmp_path)

    assert report is not None
    assert report.name == newer.name
    assert report.path == newer
    assert report.size_bytes == len(b"newer")


def test_find_latest_report_returns_none_when_dir_missing(tmp_path: Path) -> None:
    report = find_latest_report(tmp_path / "missing")

    assert report is None


def test_mask_error_is_short_and_single_line() -> None:
    error = mask_error(RuntimeError("line one\nline two with a very long message" * 40))

    assert "\n" not in error
    assert len(error) <= 180

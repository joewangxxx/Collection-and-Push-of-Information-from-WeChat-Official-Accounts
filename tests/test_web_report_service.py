from pathlib import Path

import pytest

from market_info.web.services.report_service import list_reports, resolve_report_path


def test_list_reports_only_returns_xlsx_sorted_newest_first(tmp_path: Path) -> None:
    old = tmp_path / "market_info_weekly_20260624_102824.xlsx"
    new = tmp_path / "market_info_weekly_20260629_103132.xlsx"
    ignored = tmp_path / "notes.txt"
    old.write_bytes(b"old")
    new.write_bytes(b"new")
    ignored.write_text("ignore", encoding="utf-8")

    rows = list_reports(tmp_path)

    assert [row.name for row in rows] == [new.name, old.name]
    assert rows[0].size_bytes == len(b"new")


def test_resolve_report_path_rejects_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Invalid report name"):
        resolve_report_path("../.env", tmp_path)


def test_resolve_report_path_requires_xlsx(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Only .xlsx reports"):
        resolve_report_path("notes.txt", tmp_path)


def test_resolve_report_path_requires_existing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_report_path("missing.xlsx", tmp_path)

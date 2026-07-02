from dataclasses import dataclass
from pathlib import Path

from market_info.config import Settings


@dataclass(frozen=True)
class ReportListItem:
    name: str
    path: Path
    size_bytes: int
    modified_at: float


def list_reports(export_dir: Path | None = None) -> list[ReportListItem]:
    root = export_dir or Path(Settings().export_dir)
    if not root.exists() or not root.is_dir():
        return []
    reports = []
    for path in root.iterdir():
        if not path.is_file() or path.suffix.lower() != ".xlsx":
            continue
        stat = path.stat()
        reports.append(
            ReportListItem(
                name=path.name,
                path=path,
                size_bytes=stat.st_size,
                modified_at=stat.st_mtime,
            )
        )
    return sorted(reports, key=lambda item: (item.modified_at, item.name), reverse=True)


def resolve_report_path(report_name: str, export_dir: Path | None = None) -> Path:
    if Path(report_name).name != report_name:
        raise ValueError("Invalid report name")
    if Path(report_name).suffix.lower() != ".xlsx":
        raise ValueError("Only .xlsx reports can be downloaded")
    root = (export_dir or Path(Settings().export_dir)).resolve()
    candidate = (root / report_name).resolve()
    if root not in candidate.parents and candidate != root:
        raise ValueError("Invalid report path")
    if not candidate.is_file():
        raise FileNotFoundError(report_name)
    return candidate

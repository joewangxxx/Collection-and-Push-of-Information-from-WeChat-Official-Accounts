import sys

import pytest

from scripts import smoke_extract_articles, smoke_ingest_account


@pytest.mark.parametrize(
    ("module", "argv"),
    [
        (smoke_extract_articles, ["smoke_extract_articles.py", "--limit", "0"]),
        (
            smoke_ingest_account,
            ["smoke_ingest_account.py", "--account-name", "demo", "--limit", "-1"],
        ),
    ],
)
def test_smoke_scripts_reject_non_positive_limit(monkeypatch, module, argv) -> None:
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit) as exc_info:
        module.parse_args()

    assert exc_info.value.code == 2

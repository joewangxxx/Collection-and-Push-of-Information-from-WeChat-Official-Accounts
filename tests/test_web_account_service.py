from pathlib import Path
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from market_info.db.base import Base
from market_info.db.models import MpAccount, SourceArticle
from market_info.web.services import account_service


@pytest.fixture()
def sqlite_session(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "accounts.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    @contextmanager
    def get_test_session():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(account_service, "get_session", get_test_session)
    return SessionLocal


def test_mask_fakeid_hides_middle() -> None:
    assert account_service._mask_fakeid("MzA123456789") == "MzA1...6789"
    assert account_service._mask_fakeid("short") == "****"


def test_sync_accounts_from_config_creates_and_updates(sqlite_session, tmp_path: Path) -> None:
    config_path = tmp_path / "accounts.yml"
    config_path.write_text(
        """
accounts:
  - name: Alpha
    fakeid: MzA123456789
    enabled: true
  - name: Beta
    fakeid: MzB987654321
    enabled: false
""".strip(),
        encoding="utf-8",
    )

    result = account_service.sync_accounts_from_config(config_path)

    assert result.created == 2
    assert result.updated == 0
    assert result.disabled_missing == 0

    config_path.write_text(
        """
accounts:
  - name: Alpha Updated
    fakeid: MzA123456789
    enabled: false
""".strip(),
        encoding="utf-8",
    )

    result = account_service.sync_accounts_from_config(config_path)

    assert result.created == 0
    assert result.updated == 1
    assert result.disabled_missing == 0
    [account] = sqlite_session().query(MpAccount).filter_by(fakeid="MzA123456789").all()
    assert account.name == "Alpha Updated"
    assert account.enabled is False


def test_list_accounts_masks_fakeid_and_counts_articles(sqlite_session) -> None:
    session = sqlite_session()
    account = MpAccount(name="Alpha", fakeid="MzA123456789", enabled=True)
    session.add(account)
    session.commit()
    session.add(
        SourceArticle(
            account_id=account.id,
            account_name="Alpha",
            title="Project",
            article_url="https://example.com/a",
            normalized_url="https://example.com/a",
            content_text="body",
            content_hash="hash",
            processing_status="pending",
        )
    )
    session.commit()
    session.close()

    items = account_service.list_accounts()

    assert len(items) == 1
    assert items[0].name == "Alpha"
    assert items[0].masked_fakeid == "MzA1...6789"
    assert items[0].article_count == 1


def test_set_account_enabled(sqlite_session) -> None:
    session = sqlite_session()
    account = MpAccount(name="Alpha", fakeid="MzA123456789", enabled=True)
    session.add(account)
    session.commit()
    account_id = account.id
    session.close()

    updated = account_service.set_account_enabled(account_id, False)

    assert updated is not None
    assert updated.enabled is False
    assert sqlite_session().get(MpAccount, account_id).enabled is False

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import func

from market_info.config import Settings, load_accounts_config
from market_info.db.models import MpAccount, SourceArticle
from market_info.db.session import get_session


@dataclass(frozen=True)
class AccountListItem:
    id: int
    name: str
    masked_fakeid: str
    enabled: bool
    last_fetch_at: datetime | None
    article_count: int
    created_at: datetime | None


@dataclass(frozen=True)
class AccountSyncResult:
    created: int
    updated: int
    disabled_missing: int


def list_accounts() -> list[AccountListItem]:
    with get_session() as session:
        article_counts = dict(
            session.query(SourceArticle.account_id, func.count(SourceArticle.id))
            .group_by(SourceArticle.account_id)
            .all()
        )
        accounts = session.query(MpAccount).order_by(MpAccount.name.asc()).all()
        return [_to_item(account, article_counts.get(account.id, 0)) for account in accounts]


def sync_accounts_from_config(config_path: Path | str | None = None) -> AccountSyncResult:
    path = Path(config_path or Settings().accounts_config_path)
    configured_accounts = load_accounts_config(path)
    created = 0
    updated = 0

    with get_session() as session:
        existing_by_fakeid = {
            account.fakeid: account for account in session.query(MpAccount).all()
        }
        for configured in configured_accounts:
            account = existing_by_fakeid.get(configured.fakeid)
            if account is None:
                session.add(
                    MpAccount(
                        name=configured.name,
                        fakeid=configured.fakeid,
                        enabled=configured.enabled,
                    )
                )
                created += 1
                continue

            changed = account.name != configured.name or account.enabled != configured.enabled
            account.name = configured.name
            account.enabled = configured.enabled
            if changed:
                updated += 1

        session.commit()

    return AccountSyncResult(created=created, updated=updated, disabled_missing=0)


def set_account_enabled(account_id: int, enabled: bool) -> AccountListItem | None:
    with get_session() as session:
        account = session.get(MpAccount, account_id)
        if account is None:
            return None
        account.enabled = enabled
        session.commit()
        session.refresh(account)
        article_count = (
            session.query(SourceArticle)
            .filter(SourceArticle.account_id == account.id)
            .count()
        )
        return _to_item(account, article_count)


def _mask_fakeid(fakeid: str) -> str:
    if len(fakeid) < 10:
        return "****"
    return f"{fakeid[:4]}...{fakeid[-4:]}"


def _to_item(account: MpAccount, article_count: int) -> AccountListItem:
    return AccountListItem(
        id=account.id,
        name=account.name,
        masked_fakeid=_mask_fakeid(account.fakeid),
        enabled=account.enabled,
        last_fetch_at=account.last_fetch_at,
        article_count=article_count,
        created_at=account.created_at,
    )

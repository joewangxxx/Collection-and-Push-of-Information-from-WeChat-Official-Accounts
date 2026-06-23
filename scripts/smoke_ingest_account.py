from argparse import ArgumentParser, Namespace
from pathlib import Path
import sys

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from market_info.config import Settings, load_accounts_config
from market_info.db.models import MpAccount
from market_info.db.session import get_session
from market_info.ingest.article_ingestor import ArticleIngestor
from market_info.wechat.exporter_client import WechatExporterClient, WechatExporterError


def parse_args() -> Namespace:
    parser = ArgumentParser(description="Smoke test one WeChat account ingestion.")
    parser.add_argument("--account-name", required=True)
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()
    settings = Settings()

    client = WechatExporterClient(
        settings.wechat_exporter_base_url,
        settings.wechat_exporter_auth_key,
    )
    try:
        auth_valid = client.check_auth()
    except WechatExporterError as exc:
        print(f"wechat exporter interface/network error while checking auth: {exc}")
        return 1

    if not auth_valid:
        print(
            "wechat exporter auth invalid; please open the exporter, scan login again, "
            "then update WECHAT_EXPORTER_AUTH_KEY in .env"
        )
        return 1

    accounts = load_accounts_config(Path(settings.accounts_config_path))
    account_config = next(
        (account for account in accounts if account.name == args.account_name and account.enabled),
        None,
    )
    if account_config is None:
        print(f"enabled account not found in {settings.accounts_config_path}: {args.account_name}")
        return 1

    with get_session() as session:
        account = (
            session.query(MpAccount)
            .filter_by(fakeid=account_config.fakeid)
            .first()
        )
        if account is None:
            account = MpAccount(
                name=account_config.name,
                fakeid=account_config.fakeid,
                enabled=account_config.enabled,
            )
            session.add(account)
            session.flush()
        else:
            account.name = account_config.name
            account.enabled = account_config.enabled

        try:
            result = ArticleIngestor(client, session).ingest_account(account, limit=args.limit)
        except WechatExporterError as exc:
            print(f"wechat exporter interface/network error while listing articles: {exc}")
            return 1

    print(f"inserted={result.inserted_articles}")
    print(f"skipped={result.skipped_articles}")
    print(f"failed={result.failed_articles}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

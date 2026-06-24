import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from market_info.ai.extractor import ProjectExtractionError, ProjectExtractor
from market_info.config import Settings
from market_info.db.models import SourceArticle
from market_info.db.session import get_session


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("--limit must be a positive integer")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test AI extraction from source_articles.")
    parser.add_argument("--limit", type=positive_int, default=3, help="Number of recent articles to extract.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(PROJECT_ROOT / ".env")
    settings = Settings()

    if not (
        settings.ai_base_url
        and settings.ai_api_key
        and settings.ai_extraction_model
    ):
        print("请在 .env 中配置 AI_BASE_URL、AI_API_KEY、AI_EXTRACTION_MODEL。")
        return 1

    extractor = ProjectExtractor(
        base_url=settings.ai_base_url,
        api_key=settings.ai_api_key,
        model=settings.ai_extraction_model,
    )

    with get_session() as session:
        articles = (
            session.query(SourceArticle)
            .order_by(SourceArticle.created_at.desc())
            .limit(args.limit)
            .all()
        )

    if not articles:
        print("source_articles 中暂无文章。")
        return 0

    for article in articles:
        print(f"文章标题: {article.title}")
        try:
            projects = extractor.extract(article.title or "", article.content_text or "")
        except ProjectExtractionError as exc:
            print(f"抽取失败: {exc}")
            continue

        print(f"抽取项目数量: {len(projects)}")
        for project in projects:
            print(
                "- "
                f"project_name={project.project_name}, "
                f"company_name={project.company_name}, "
                f"investment_amount_yi={project.investment_amount_yi}, "
                f"status={project.status}, "
                f"confidence={project.confidence}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

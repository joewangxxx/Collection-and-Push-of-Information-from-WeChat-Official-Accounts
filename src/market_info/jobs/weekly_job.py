from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from market_info.ai.embeddings import EmbeddingClient, build_project_semantic_text
from market_info.ai.extractor import ProjectExtractor
from market_info.config import Settings, load_accounts_config
from market_info.db.models import MpAccount, Project, ProjectEvent, ProjectRecord, SourceArticle
from market_info.db.session import get_session
from market_info.dedupe.matcher import apply_match_decision, choose_best_match
from market_info.dedupe.rule_score import calculate_rule_score
from market_info.dedupe.vector_search import VectorSearch
from market_info.ingest.article_ingestor import ArticleIngestor
from market_info.notify.email_sender import EmailSendError, send_report_email
from market_info.reports.excel_report import generate_weekly_excel
from market_info.wechat.exporter_client import WechatExporterClient


class WeeklyJobError(Exception):
    """Raised when weekly job orchestration cannot complete."""


@dataclass(frozen=True)
class IngestAccountResult:
    account_name: str
    inserted_articles: int
    skipped_articles: int
    failed_articles: int


@dataclass(frozen=True)
class ProcessingResult:
    new_projects: int = 0
    merged_projects: int = 0
    review_projects: int = 0
    status_events: int = 0
    project_total: int = 0


@dataclass(frozen=True)
class WeeklyRunSummary:
    new_articles: int
    new_projects: int
    merged_projects: int
    review_projects: int
    project_total: int
    status_events: int
    excel_path: Path
    email_sent: bool

    def to_email_summary(self) -> dict[str, object]:
        return {
            "new_projects": self.new_projects,
            "merged_projects": self.merged_projects,
            "review_projects": self.review_projects,
            "project_total": self.project_total,
            "status_events": self.status_events,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }


def check_wechat_auth(
    settings: Settings | None = None,
    client: WechatExporterClient | None = None,
) -> bool:
    settings = settings or Settings()
    client = client or WechatExporterClient(
        settings.wechat_exporter_base_url,
        settings.wechat_exporter_auth_key,
    )
    return client.check_auth()


def ingest_enabled_accounts(
    limit: int = 20,
    settings: Settings | None = None,
    client: WechatExporterClient | None = None,
) -> list[IngestAccountResult]:
    settings = settings or Settings()
    client = client or WechatExporterClient(
        settings.wechat_exporter_base_url,
        settings.wechat_exporter_auth_key,
    )
    account_configs = [
        account
        for account in load_accounts_config(Path(settings.accounts_config_path))
        if account.enabled
    ]

    results: list[IngestAccountResult] = []
    with get_session() as session:
        for account_config in account_configs:
            account = _sync_account(session, account_config)
            result = ArticleIngestor(client, session).ingest_account(account, limit=limit)
            results.append(
                IngestAccountResult(
                    account_name=account.name,
                    inserted_articles=result.inserted_articles,
                    skipped_articles=result.skipped_articles,
                    failed_articles=result.failed_articles,
                )
            )
    return results


def send_report(excel_path: Path) -> None:
    send_report_email(
        excel_path,
        {
            "new_projects": 0,
            "merged_projects": 0,
            "review_projects": 0,
            "project_total": 0,
            "status_events": 0,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


def run_weekly(limit: int = 20) -> WeeklyRunSummary:
    settings = Settings()
    client = WechatExporterClient(
        settings.wechat_exporter_base_url,
        settings.wechat_exporter_auth_key,
    )
    if not check_wechat_auth(settings=settings, client=client):
        raise WeeklyJobError("wechat exporter auth invalid; please scan login again")

    ingest_results = ingest_enabled_accounts(limit=limit, settings=settings, client=client)
    new_articles = sum(result.inserted_articles for result in ingest_results)

    with get_session() as session:
        processing_result = process_pending_articles(session, settings)
        session.commit()
        excel_path = generate_weekly_excel(
            session,
            Path(settings.export_dir),
            run_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
        )

    summary = WeeklyRunSummary(
        new_articles=new_articles,
        new_projects=processing_result.new_projects,
        merged_projects=processing_result.merged_projects,
        review_projects=processing_result.review_projects,
        project_total=processing_result.project_total,
        status_events=processing_result.status_events,
        excel_path=excel_path,
        email_sent=False,
    )

    try:
        send_report_email(excel_path, summary.to_email_summary())
    except EmailSendError as exc:
        raise WeeklyJobError("email sending failed") from exc

    return WeeklyRunSummary(
        new_articles=summary.new_articles,
        new_projects=summary.new_projects,
        merged_projects=summary.merged_projects,
        review_projects=summary.review_projects,
        project_total=summary.project_total,
        status_events=summary.status_events,
        excel_path=summary.excel_path,
        email_sent=True,
    )


def process_pending_articles(session: Session, settings: Settings) -> ProcessingResult:
    _validate_ai_settings(settings)
    extractor = ProjectExtractor(
        settings.ai_base_url,
        settings.ai_api_key,
        settings.ai_extraction_model,
    )
    embedding_client = EmbeddingClient(
        settings.ai_base_url,
        settings.ai_api_key,
        settings.ai_embedding_model,
        dimensions=settings.embedding_dim,
    )
    vector_search = VectorSearch(session)

    status_events_before = session.query(ProjectEvent).count()
    new_projects = 0
    merged_projects = 0
    review_projects = 0

    for article in _pending_articles(session):
        extracted_projects = extractor.extract(article.title, article.content_text)
        for extracted_project in extracted_projects:
            semantic_text = build_project_semantic_text(extracted_project)
            embedding = embedding_client.embed(semantic_text)
            record = ProjectRecord(
                source_article=article,
                project_name=extracted_project.project_name,
                project_info=extracted_project.project_info,
                province=extracted_project.province,
                city=extracted_project.city,
                detailed_address=extracted_project.detailed_address,
                company_name=extracted_project.company_name,
                investment_amount_yi=extracted_project.investment_amount_yi,
                industry=extracted_project.industry,
                field=extracted_project.field,
                market=extracted_project.market,
                status=extracted_project.status,
                confidence=extracted_project.confidence,
                semantic_text=semantic_text,
                embedding=embedding,
            )
            session.add(record)
            session.flush()

            candidates = vector_search.find_candidates(embedding, extracted_project.province)
            existing_projects = _load_candidate_projects(session, candidates)
            rule_scores = {
                project.id: calculate_rule_score(record, project)
                for project in existing_projects
                if project.id is not None
            }
            decision = choose_best_match(candidates, rule_scores)
            apply_match_decision(session, record, decision)

            if decision.decision == "new":
                new_projects += 1
            elif decision.decision == "merge":
                merged_projects += 1
            elif decision.decision == "review":
                review_projects += 1

    status_events_after = session.query(ProjectEvent).count()
    return ProcessingResult(
        new_projects=new_projects,
        merged_projects=merged_projects,
        review_projects=review_projects,
        status_events=status_events_after - status_events_before,
        project_total=session.query(Project).count(),
    )


def _sync_account(session: Session, account_config) -> MpAccount:
    account = session.query(MpAccount).filter_by(fakeid=account_config.fakeid).first()
    if account is None:
        account = MpAccount(
            name=account_config.name,
            fakeid=account_config.fakeid,
            enabled=account_config.enabled,
        )
        session.add(account)
        session.flush()
        return account

    account.name = account_config.name
    account.enabled = account_config.enabled
    session.flush()
    return account


def _pending_articles(session: Session) -> list[SourceArticle]:
    return (
        session.query(SourceArticle)
        .outerjoin(ProjectRecord, SourceArticle.id == ProjectRecord.source_article_id)
        .filter(ProjectRecord.id.is_(None))
        .order_by(SourceArticle.created_at)
        .all()
    )


def _load_candidate_projects(session: Session, candidates) -> list[Project]:
    project_ids = [candidate.project_id for candidate in candidates]
    if not project_ids:
        return []
    return session.query(Project).filter(Project.id.in_(project_ids)).all()


def _validate_ai_settings(settings: Settings) -> None:
    missing = []
    if not settings.ai_base_url:
        missing.append("AI_BASE_URL")
    if not settings.ai_api_key:
        missing.append("AI_API_KEY")
    if not settings.ai_extraction_model:
        missing.append("AI_EXTRACTION_MODEL")
    if not settings.ai_embedding_model:
        missing.append("AI_EMBEDDING_MODEL")
    if missing:
        raise WeeklyJobError(f"Missing required AI config: {', '.join(missing)}")

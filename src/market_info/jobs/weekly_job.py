from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from market_info.ai.embeddings import EmbeddingClient, build_project_semantic_text
from market_info.ai.extractor import ProjectExtractionError, ProjectExtractor
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
class ArticleProcessingInput:
    article_id: int
    title: str
    content_text: str


@dataclass(frozen=True)
class ProjectExtractionOutput:
    extracted_project: object
    semantic_text: str
    embedding: list[float] | None


@dataclass(frozen=True)
class ArticleProcessingOutcome:
    article_id: int
    success: bool
    projects: list[ProjectExtractionOutput]
    error_message: str | None = None


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


ProgressCallback = Callable[[str], None]


def run_weekly(
    limit: int = 20,
    progress_callback: ProgressCallback | None = None,
) -> WeeklyRunSummary:
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
        processing_result = process_pending_articles(
            session,
            settings,
            max_articles=max(new_articles, limit),
            progress_callback=progress_callback,
        )
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


def process_pending_articles(
    session: Session,
    settings: Settings,
    max_articles: int | None = None,
    progress_callback: ProgressCallback | None = None,
) -> ProcessingResult:
    _validate_ai_settings(settings)
    vector_search = VectorSearch(session)

    status_events_before = session.query(ProjectEvent).count()
    new_projects = 0
    merged_projects = 0
    review_projects = 0

    articles = _pending_articles(session, max_articles=max_articles)
    total_articles = len(articles)
    concurrency = settings.ai_concurrency
    _emit_progress(
        progress_callback,
        f"AI processing articles: total={total_articles} concurrency={concurrency}",
    )

    article_inputs = [
        ArticleProcessingInput(
            article_id=article.id,
            title=article.title,
            content_text=article.content_text or "",
        )
        for article in articles
    ]

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(_process_article_ai, article_input, settings)
            for article_input in article_inputs
        ]
        for completed_count, future in enumerate(as_completed(futures), start=1):
            outcome = future.result()
            article = session.get(SourceArticle, outcome.article_id)
            if article is None:
                continue

            article.extraction_attempts = (article.extraction_attempts or 0) + 1
            if not outcome.success:
                _mark_article_failed(article, outcome.error_message)
                session.commit()
                _emit_progress(
                    progress_callback,
                    f"completed {completed_count}/{total_articles}: "
                    f"article_id={outcome.article_id} status=failed",
                )
                continue

            for project_output in outcome.projects:
                extracted_project = project_output.extracted_project

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
                    semantic_text=project_output.semantic_text,
                    embedding=project_output.embedding,
                )
                session.add(record)
                session.flush()

                candidates = vector_search.find_candidates(
                    project_output.embedding,
                    extracted_project.province,
                )
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

            _mark_article_processed(article)
            session.commit()
            _emit_progress(
                progress_callback,
                f"completed {completed_count}/{total_articles}: "
                f"article_id={outcome.article_id} "
                f"projects={len(outcome.projects)} status=processed",
            )

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


def _pending_articles(
    session: Session,
    max_articles: int | None = None,
) -> list[SourceArticle]:
    query = (
        session.query(SourceArticle)
        .filter(
            or_(
                SourceArticle.processing_status == "pending",
                and_(
                    SourceArticle.processing_status == "failed",
                    SourceArticle.extraction_attempts < 3,
                ),
            )
        )
    )
    if max_articles is not None:
        query = query.order_by(SourceArticle.created_at.desc()).limit(max_articles)
    else:
        query = query.order_by(SourceArticle.created_at)
    return query.all()


def _mark_article_processed(article: SourceArticle) -> None:
    article.processing_status = "processed"
    article.processed_at = datetime.now(timezone.utc)
    article.extraction_error = None


def _mark_article_failed(article: SourceArticle, exc: Exception | str | None = None) -> None:
    article.processing_status = "failed"
    article.processed_at = datetime.now(timezone.utc)
    article.extraction_error = _error_summary(exc) if exc is not None else None


def _error_summary(exc: Exception | str | None, max_length: int = 500) -> str:
    if exc is None:
        return ""
    message = " ".join(str(exc).split())
    return message[:max_length]


def _emit_progress(callback: ProgressCallback | None, message: str) -> None:
    if callback is not None:
        callback(message)


def _process_article_ai(
    article_input: ArticleProcessingInput,
    settings: Settings,
) -> ArticleProcessingOutcome:
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

    try:
        extracted_projects = extractor.extract(
            article_input.title,
            article_input.content_text,
        )
    except ProjectExtractionError as exc:
        return ArticleProcessingOutcome(
            article_id=article_input.article_id,
            success=False,
            projects=[],
            error_message=_error_summary(exc),
        )
    except Exception as exc:
        return ArticleProcessingOutcome(
            article_id=article_input.article_id,
            success=False,
            projects=[],
            error_message=_error_summary(exc),
        )

    projects: list[ProjectExtractionOutput] = []
    embedding_errors: list[str] = []
    for extracted_project in extracted_projects:
        semantic_text = build_project_semantic_text(extracted_project)
        try:
            embedding = embedding_client.embed(semantic_text)
        except Exception as exc:
            embedding_errors.append(_error_summary(exc))
            continue
        projects.append(
            ProjectExtractionOutput(
                extracted_project=extracted_project,
                semantic_text=semantic_text,
                embedding=embedding,
            )
        )

    error_message = "; ".join(embedding_errors) if embedding_errors else None
    return ArticleProcessingOutcome(
        article_id=article_input.article_id,
        success=True,
        projects=projects,
        error_message=error_message,
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

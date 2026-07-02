from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import or_

from market_info.db.models import Project, ProjectEvent, ProjectRecord
from market_info.db.session import get_session


@dataclass(frozen=True)
class ProjectListItem:
    id: int
    project_name: str
    company_name: str
    province: str
    city: str
    industry: str
    market: str
    status: str
    investment_amount_yi: Decimal | float | None
    first_seen_at: datetime | None
    last_seen_at: datetime | None


@dataclass(frozen=True)
class ProjectRecordSummary:
    id: int
    article_title: str
    article_url: str
    account_name: str
    published_at: datetime | None
    decision: str
    score: float | None
    status: str
    created_at: datetime | None


@dataclass(frozen=True)
class ProjectEventSummary:
    id: int
    event_status: str
    previous_status: str
    change_label: str
    event_date: datetime | None
    article_title: str
    article_url: str


@dataclass(frozen=True)
class ProjectDetail:
    project: ProjectListItem
    records: list[ProjectRecordSummary]
    events: list[ProjectEventSummary]


def list_projects(
    query: str | None = None,
    province: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[ProjectListItem]:
    with get_session() as session:
        projects = session.query(Project)
        if query:
            pattern = f"%{query.strip()}%"
            projects = projects.filter(
                or_(
                    Project.canonical_project_name.ilike(pattern),
                    Project.canonical_company_name.ilike(pattern),
                )
            )
        if province:
            projects = projects.filter(Project.province == province)
        if status:
            projects = projects.filter(Project.current_status == status)
        rows = (
            projects.order_by(Project.last_seen_at.desc().nullslast(), Project.id.desc())
            .limit(limit)
            .all()
        )
        return [_to_project_item(project) for project in rows]


def get_project_detail(project_id: int) -> ProjectDetail:
    with get_session() as session:
        project = session.get(Project, project_id)
        if project is None:
            raise ValueError("Project not found")
        records = (
            session.query(ProjectRecord)
            .join(ProjectRecord.source_article)
            .filter(ProjectRecord.project_id == project_id)
            .order_by(ProjectRecord.source_article.property.mapper.class_.published_at.desc().nullslast(), ProjectRecord.id.desc())
            .all()
        )
        events = (
            session.query(ProjectEvent)
            .join(ProjectEvent.source_article)
            .filter(ProjectEvent.project_id == project_id)
            .order_by(ProjectEvent.event_date.desc().nullslast(), ProjectEvent.id.desc())
            .all()
        )
        return ProjectDetail(
            project=_to_project_item(project),
            records=[_to_record_summary(record) for record in records],
            events=[_to_event_summary(event) for event in events],
        )


def _to_project_item(project: Project) -> ProjectListItem:
    return ProjectListItem(
        id=project.id,
        project_name=project.canonical_project_name or "",
        company_name=project.canonical_company_name or "",
        province=project.province or "",
        city=project.city or "",
        industry=project.industry or "",
        market=project.market or "",
        status=project.current_status or "",
        investment_amount_yi=project.investment_amount_yi,
        first_seen_at=project.first_seen_at,
        last_seen_at=project.last_seen_at,
    )


def _to_record_summary(record: ProjectRecord) -> ProjectRecordSummary:
    article = record.source_article
    return ProjectRecordSummary(
        id=record.id,
        article_title=article.title,
        article_url=article.article_url,
        account_name=article.account_name,
        published_at=article.published_at,
        decision=record.dedupe_decision or "",
        score=record.dedupe_score,
        status=record.status or "",
        created_at=record.created_at,
    )


def _to_event_summary(event: ProjectEvent) -> ProjectEventSummary:
    article = event.source_article
    return ProjectEventSummary(
        id=event.id,
        event_status=event.event_status,
        previous_status=event.previous_status or "",
        change_label=event.change_label or "",
        event_date=event.event_date,
        article_title=article.title,
        article_url=article.article_url,
    )

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import or_

from market_info.db.models import Project, ProjectRecord, SourceArticle
from market_info.db.session import get_session
from market_info.dedupe.matcher import MatchDecision, apply_match_decision


ReviewDecision = Literal["new", "merge"]


@dataclass(frozen=True)
class ReviewQueueItem:
    id: int
    project_name: str
    company_name: str
    province: str
    city: str
    status: str
    dedupe_score: float | None
    article_title: str
    article_url: str
    account_name: str
    published_at: datetime | None
    created_at: datetime | None


@dataclass(frozen=True)
class ReviewCandidateItem:
    id: int
    project_name: str
    company_name: str
    province: str
    city: str
    status: str
    last_seen_at: datetime | None
    score_hint: str


@dataclass(frozen=True)
class ReviewResolutionResult:
    record_id: int
    decision: ReviewDecision
    project_id: int | None


def list_review_records(limit: int = 100) -> list[ReviewQueueItem]:
    with get_session() as session:
        rows = (
            session.query(ProjectRecord)
            .join(ProjectRecord.source_article)
            .filter(ProjectRecord.dedupe_decision == "review")
            .order_by(ProjectRecord.created_at.desc(), ProjectRecord.id.desc())
            .limit(limit)
            .all()
        )
        return [_to_review_item(record) for record in rows]


def get_review_record(record_id: int) -> ReviewQueueItem:
    with get_session() as session:
        record = _get_pending_review_record(session, record_id)
        return _to_review_item(record)


def list_project_candidates(
    record_id: int,
    query: str | None = None,
    limit: int = 8,
) -> list[ReviewCandidateItem]:
    with get_session() as session:
        record = _get_pending_review_record(session, record_id)
        projects = session.query(Project)
        if query:
            pattern = f"%{query.strip()}%"
            projects = projects.filter(
                or_(
                    Project.canonical_project_name.ilike(pattern),
                    Project.canonical_company_name.ilike(pattern),
                )
            )
        elif record.province:
            projects = projects.filter(Project.province == record.province)

        rows = (
            projects.order_by(Project.last_seen_at.desc().nullslast(), Project.id.desc())
            .limit(limit)
            .all()
        )
        return [_to_candidate_item(project, record) for project in rows]


def resolve_review_record(
    record_id: int,
    decision: ReviewDecision,
    project_id: int | None = None,
) -> ReviewResolutionResult:
    if decision == "merge" and project_id is None:
        raise ValueError("Merge decision requires project_id")
    with get_session() as session:
        record = session.get(ProjectRecord, record_id)
        if record is None:
            raise ValueError("Review record not found")
        if record.dedupe_decision != "review":
            raise ValueError("Record is not pending review")
        match_decision = MatchDecision(
            decision=decision,
            final_score=record.dedupe_score or 100.0,
            project_id=project_id,
            rule_score=0.0,
            vector_score=0.0,
        )
        project = apply_match_decision(session, record, match_decision)
        session.commit()
        return ReviewResolutionResult(
            record_id=record.id,
            decision=decision,
            project_id=project.id if project is not None else record.project_id,
        )


def _get_pending_review_record(session, record_id: int) -> ProjectRecord:
    record = (
        session.query(ProjectRecord)
        .join(ProjectRecord.source_article)
        .filter(ProjectRecord.id == record_id, ProjectRecord.dedupe_decision == "review")
        .one_or_none()
    )
    if record is None:
        raise ValueError("Review record not found")
    return record


def _to_review_item(record: ProjectRecord) -> ReviewQueueItem:
    article: SourceArticle = record.source_article
    return ReviewQueueItem(
        id=record.id,
        project_name=record.project_name or "",
        company_name=record.company_name or "",
        province=record.province or "",
        city=record.city or "",
        status=record.status or "",
        dedupe_score=record.dedupe_score,
        article_title=article.title,
        article_url=article.article_url,
        account_name=article.account_name,
        published_at=article.published_at,
        created_at=record.created_at,
    )


def _to_candidate_item(project: Project, record: ProjectRecord) -> ReviewCandidateItem:
    return ReviewCandidateItem(
        id=project.id,
        project_name=project.canonical_project_name or "",
        company_name=project.canonical_company_name or "",
        province=project.province or "",
        city=project.city or "",
        status=project.current_status or "",
        last_seen_at=project.last_seen_at,
        score_hint="same province" if project.province == record.province else "search match",
    )

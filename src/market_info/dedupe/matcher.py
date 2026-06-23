from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from market_info.db.models import Project, ProjectEvent, ProjectRecord
from market_info.dedupe.rule_score import RuleScoreBreakdown
from market_info.dedupe.vector_search import VectorCandidate


DecisionLiteral = Literal["merge", "review", "new"]


@dataclass(frozen=True)
class MatchDecision:
    decision: DecisionLiteral
    final_score: float
    project_id: int | None
    rule_score: float
    vector_score: float


class ProjectMergeError(Exception):
    """Raised when a merge decision cannot be applied to a project."""


def calculate_final_score(rule_score: float, vector_score: float) -> float:
    return rule_score * 0.65 + vector_score * 0.35


def classify_score(final_score: float) -> DecisionLiteral:
    if final_score >= 85:
        return "merge"
    if final_score >= 70:
        return "review"
    return "new"


def choose_best_match(
    candidates: list[VectorCandidate],
    rule_score_by_project_id: dict[int, float | RuleScoreBreakdown],
) -> MatchDecision:
    if not candidates:
        return MatchDecision(
            decision="new",
            final_score=0,
            project_id=None,
            rule_score=0,
            vector_score=0,
        )

    best_decision: MatchDecision | None = None
    for candidate in candidates:
        rule_score = _extract_rule_score(rule_score_by_project_id.get(candidate.project_id))
        vector_score = candidate.vector_similarity * 100
        final_score = calculate_final_score(rule_score, vector_score)
        decision_label = classify_score(final_score)
        decision = MatchDecision(
            decision=decision_label,
            final_score=final_score,
            project_id=candidate.project_id if decision_label != "new" else None,
            rule_score=rule_score,
            vector_score=vector_score,
        )
        if best_decision is None or decision.final_score > best_decision.final_score:
            best_decision = decision

    return best_decision


def _extract_rule_score(score: float | RuleScoreBreakdown | None) -> float:
    if score is None:
        return 0.0
    if isinstance(score, RuleScoreBreakdown):
        return score.total
    return float(score)


def apply_match_decision(
    session,
    record: ProjectRecord,
    decision: MatchDecision,
) -> Project | None:
    if decision.decision == "new":
        return _apply_new_decision(session, record, decision)

    if decision.decision == "merge":
        return _apply_merge_decision(session, record, decision)

    if decision.decision == "review":
        record.project = None
        record.project_id = None
        record.dedupe_decision = "review"
        record.dedupe_score = decision.final_score
        session.flush()
        return None

    raise ProjectMergeError(f"Unsupported match decision: {decision.decision}")


def _apply_new_decision(
    session,
    record: ProjectRecord,
    decision: MatchDecision,
) -> Project:
    seen_at = _record_event_date(record)
    project = Project(
        canonical_project_name=record.project_name,
        canonical_company_name=record.company_name,
        province=record.province,
        city=record.city,
        detailed_address=record.detailed_address,
        investment_amount_yi=record.investment_amount_yi,
        industry=record.industry,
        field=record.field,
        market=record.market,
        current_status=record.status,
        first_seen_at=seen_at,
        last_seen_at=seen_at,
        semantic_text=record.semantic_text,
        embedding=record.embedding,
    )
    record.project = project
    record.dedupe_decision = "new"
    record.dedupe_score = decision.final_score
    session.add(project)
    session.flush()
    return project


def _apply_merge_decision(
    session,
    record: ProjectRecord,
    decision: MatchDecision,
) -> Project:
    if decision.project_id is None:
        raise ProjectMergeError("merge decision requires project_id")

    existing_project = session.get(Project, decision.project_id)
    if existing_project is None:
        raise ProjectMergeError(f"project_id {decision.project_id} not found")

    record.project = existing_project
    record.dedupe_decision = "merge"
    record.dedupe_score = decision.final_score
    existing_project.last_seen_at = _record_event_date(record)

    if _should_create_status_event(record.status, existing_project.current_status):
        previous_status = existing_project.current_status
        event_status = record.status
        event = ProjectEvent(
            project_id=existing_project.id,
            source_article_id=record.source_article_id,
            previous_status=previous_status,
            event_status=event_status,
            event_date=_record_event_date(record),
            change_label=f"{previous_status} -> {event_status}",
        )
        session.add(event)
        existing_project.current_status = event_status

    session.flush()
    return existing_project


def _record_event_date(record: ProjectRecord) -> datetime | None:
    source_article = getattr(record, "source_article", None)
    if source_article is not None and source_article.published_at is not None:
        return source_article.published_at
    return record.created_at


def _should_create_status_event(
    record_status: str | None,
    current_status: str | None,
) -> bool:
    if not record_status or record_status == "未知":
        return False
    return record_status != current_status

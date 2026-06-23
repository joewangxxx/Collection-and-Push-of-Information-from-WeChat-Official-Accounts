from dataclasses import dataclass
from typing import Literal

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

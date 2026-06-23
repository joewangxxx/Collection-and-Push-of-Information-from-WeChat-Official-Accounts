import pytest

from market_info.dedupe.matcher import (
    MatchDecision,
    calculate_final_score,
    choose_best_match,
    classify_score,
)
from market_info.dedupe.rule_score import RuleScoreBreakdown
from market_info.dedupe.vector_search import VectorCandidate


def test_calculate_final_score_uses_weighted_rule_and_vector_scores() -> None:
    assert calculate_final_score(89, 91) == pytest.approx(89.7)
    assert calculate_final_score(66, 88) == pytest.approx(73.7)


def test_classify_score_thresholds() -> None:
    assert classify_score(89.7) == "merge"
    assert classify_score(73.7) == "review"
    assert classify_score(69.99) == "new"


def test_choose_best_match_selects_highest_final_score() -> None:
    candidates = [
        VectorCandidate(project_id=1, vector_similarity=0.95),
        VectorCandidate(project_id=2, vector_similarity=0.82),
        VectorCandidate(project_id=3, vector_similarity=0.9),
    ]
    rule_scores = {
        1: 60.0,
        2: 91.0,
        3: 80.0,
    }

    decision = choose_best_match(candidates, rule_scores)

    assert decision == MatchDecision(
        decision="merge",
        final_score=pytest.approx(87.85),
        project_id=2,
        rule_score=91.0,
        vector_score=82.0,
    )


def test_choose_best_match_accepts_rule_score_breakdown() -> None:
    candidates = [VectorCandidate(project_id=7, vector_similarity=0.91)]
    breakdown = RuleScoreBreakdown(
        project_name=30,
        company_name=25,
        province_city=15,
        detailed_address=10,
        investment_amount_yi=10,
        industry_field=0,
        total=90,
    )

    decision = choose_best_match(candidates, {7: breakdown})

    assert decision.decision == "merge"
    assert decision.project_id == 7
    assert decision.rule_score == 90
    assert decision.vector_score == 91
    assert decision.final_score == pytest.approx(90.35)


def test_choose_best_match_returns_new_when_no_candidates() -> None:
    assert choose_best_match([], {}) == MatchDecision(
        decision="new",
        final_score=0,
        project_id=None,
        rule_score=0,
        vector_score=0,
    )


def test_choose_best_match_returns_new_without_project_id_when_score_is_low() -> None:
    decision = choose_best_match(
        [VectorCandidate(project_id=9, vector_similarity=0.8)],
        {},
    )

    assert decision.decision == "new"
    assert decision.project_id is None
    assert decision.rule_score == 0
    assert decision.vector_score == 80
    assert decision.final_score == pytest.approx(28)

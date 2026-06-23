from types import SimpleNamespace

import pytest

from market_info.dedupe.normalizers import (
    normalize_address,
    normalize_company_name,
    normalize_project_name,
)
from market_info.dedupe.rule_score import RuleScoreBreakdown, calculate_rule_score


def make_new_record(**kwargs):
    defaults = {
        "project_name": "盐城光伏组件扩产项目",
        "company_name": "江苏示例新能源有限公司",
        "province": "江苏省",
        "city": "盐城市",
        "detailed_address": "盐城经开区",
        "investment_amount_yi": 10.0,
        "industry": "新能源",
        "field": "光伏",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_existing_project(**kwargs):
    defaults = {
        "canonical_project_name": "盐城光伏组件扩产",
        "canonical_company_name": "江苏示例新能源",
        "province": "江苏省",
        "city": "盐城市",
        "detailed_address": "盐城经济技术开发区",
        "investment_amount_yi": 10.4,
        "industry": "新能源",
        "field": "光伏",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_normalizers_remove_stage_words_suffixes_and_standardize_address() -> None:
    assert normalize_project_name("  盐城 光伏组件 建设项目 环评公示  ") == "盐城 光伏组件"
    assert normalize_company_name("江苏示例新能源有限责任公司") == "江苏示例新能源"
    assert normalize_company_name("江苏示例新能源股份有限公司") == "江苏示例新能源"
    assert normalize_address(" 盐城 经开区 高新区 ") == "盐城 经济技术开发区 高新技术产业开发区"


def test_rule_score_gives_high_total_for_matching_project() -> None:
    score = calculate_rule_score(make_new_record(), make_existing_project())

    assert isinstance(score, RuleScoreBreakdown)
    assert score.project_name > 25
    assert score.company_name == pytest.approx(25)
    assert score.province_city == 15
    assert score.detailed_address == pytest.approx(10)
    assert score.investment_amount_yi == 10
    assert score.industry_field == 10
    assert score.total == pytest.approx(
        score.project_name
        + score.company_name
        + score.province_city
        + score.detailed_address
        + score.investment_amount_yi
        + score.industry_field
    )


def test_rule_score_investment_amount_thresholds() -> None:
    new_record = make_new_record(investment_amount_yi=100)

    assert calculate_rule_score(
        new_record,
        make_existing_project(investment_amount_yi=105),
    ).investment_amount_yi == 10
    assert calculate_rule_score(
        new_record,
        make_existing_project(investment_amount_yi=115),
    ).investment_amount_yi == 5
    assert calculate_rule_score(
        new_record,
        make_existing_project(investment_amount_yi=116),
    ).investment_amount_yi == 0
    assert calculate_rule_score(
        new_record,
        make_existing_project(investment_amount_yi=None),
    ).investment_amount_yi == 0


def test_rule_score_partial_province_city_and_industry_field() -> None:
    score = calculate_rule_score(
        make_new_record(city="盐城市", industry="新能源", field="储能"),
        make_existing_project(city="苏州市", industry="新能源", field="光伏"),
    )

    assert score.province_city == 8
    assert score.industry_field == 5


def test_rule_score_uses_zero_for_missing_text_fields() -> None:
    score = calculate_rule_score(
        make_new_record(project_name=None, company_name=None, detailed_address=None),
        make_existing_project(
            canonical_project_name=None,
            canonical_company_name=None,
            detailed_address=None,
        ),
    )

    assert score.project_name == 0
    assert score.company_name == 0
    assert score.detailed_address == 0

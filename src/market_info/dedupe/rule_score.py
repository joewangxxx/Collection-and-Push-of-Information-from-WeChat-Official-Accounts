from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from rapidfuzz import fuzz

from market_info.dedupe.normalizers import (
    normalize_address,
    normalize_company_name,
    normalize_project_name,
)


@dataclass(frozen=True)
class RuleScoreBreakdown:
    project_name: float
    company_name: float
    province_city: float
    detailed_address: float
    investment_amount_yi: float
    industry_field: float
    total: float


def calculate_rule_score(new_record: object, existing_project: object) -> RuleScoreBreakdown:
    project_name = _similarity_score(
        normalize_project_name(_get(new_record, "project_name")),
        normalize_project_name(
            _get(existing_project, "canonical_project_name")
            or _get(existing_project, "project_name")
        ),
        30,
    )
    company_name = _similarity_score(
        normalize_company_name(_get(new_record, "company_name")),
        normalize_company_name(
            _get(existing_project, "canonical_company_name")
            or _get(existing_project, "company_name")
        ),
        25,
    )
    province_city = _province_city_score(new_record, existing_project)
    detailed_address = _similarity_score(
        normalize_address(_get(new_record, "detailed_address")),
        normalize_address(_get(existing_project, "detailed_address")),
        10,
    )
    investment_amount_yi = _investment_score(
        _get(new_record, "investment_amount_yi"),
        _get(existing_project, "investment_amount_yi"),
    )
    industry_field = _industry_field_score(new_record, existing_project)

    total = (
        project_name
        + company_name
        + province_city
        + detailed_address
        + investment_amount_yi
        + industry_field
    )
    return RuleScoreBreakdown(
        project_name=project_name,
        company_name=company_name,
        province_city=province_city,
        detailed_address=detailed_address,
        investment_amount_yi=investment_amount_yi,
        industry_field=industry_field,
        total=total,
    )


def _similarity_score(left: str, right: str, weight: float) -> float:
    if not left or not right:
        return 0.0
    return fuzz.ratio(left, right) / 100 * weight


def _province_city_score(new_record: object, existing_project: object) -> float:
    new_province = _normalized_text(_get(new_record, "province"))
    existing_province = _normalized_text(_get(existing_project, "province"))
    if not new_province or not existing_province or new_province != existing_province:
        return 0.0

    new_city = _normalized_text(_get(new_record, "city"))
    existing_city = _normalized_text(_get(existing_project, "city"))
    if new_city and existing_city and new_city == existing_city:
        return 15.0
    return 8.0


def _investment_score(new_value: object, existing_value: object) -> float:
    new_amount = _to_decimal(new_value)
    existing_amount = _to_decimal(existing_value)
    if new_amount is None or existing_amount is None or new_amount == 0:
        return 0.0

    difference_ratio = abs(new_amount - existing_amount) / abs(new_amount)
    if difference_ratio <= Decimal("0.05"):
        return 10.0
    if difference_ratio <= Decimal("0.15"):
        return 5.0
    return 0.0


def _industry_field_score(new_record: object, existing_project: object) -> float:
    industry_matches = _values_match(
        _get(new_record, "industry"),
        _get(existing_project, "industry"),
    )
    field_matches = _values_match(
        _get(new_record, "field"),
        _get(existing_project, "field"),
    )
    if industry_matches and field_matches:
        return 10.0
    if industry_matches or field_matches:
        return 5.0
    return 0.0


def _values_match(left: object, right: object) -> bool:
    left_text = _normalized_text(left)
    right_text = _normalized_text(right)
    return bool(left_text and right_text and left_text == right_text)


def _normalized_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _get(source: object, name: str) -> object:
    return getattr(source, name, None)

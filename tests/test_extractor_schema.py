import pytest
from pydantic import ValidationError

from market_info.ai.schemas import ExtractedProject


def test_extracted_project_accepts_known_status() -> None:
    project = ExtractedProject(
        project_name="光伏项目",
        project_info="建设光伏组件生产线",
        province="江苏省",
        city="盐城市",
        detailed_address=None,
        company_name="测试新能源有限公司",
        investment_amount_yi=12.5,
        industry="新能源",
        field="光伏",
        market="工业项目",
        status="环评公示",
        confidence=0.88,
    )

    assert project.status == "环评公示"


def test_status_defaults_to_unknown_when_missing() -> None:
    project = ExtractedProject(confidence=0.5)

    assert project.status == "未知"


def test_empty_string_fields_become_none() -> None:
    project = ExtractedProject(
        project_name=" ",
        project_info="",
        province="\t",
        city=" 盐城市 ",
        status="",
        confidence=0.5,
    )

    assert project.project_name is None
    assert project.project_info is None
    assert project.province is None
    assert project.city == "盐城市"
    assert project.status == "未知"


def test_confidence_must_be_between_zero_and_one() -> None:
    with pytest.raises(ValidationError):
        ExtractedProject(status="未知", confidence=-0.1)

    with pytest.raises(ValidationError):
        ExtractedProject(status="未知", confidence=1.1)


def test_investment_amount_cannot_be_negative() -> None:
    with pytest.raises(ValidationError):
        ExtractedProject(
            status="未知",
            confidence=0.5,
            investment_amount_yi=-1,
        )

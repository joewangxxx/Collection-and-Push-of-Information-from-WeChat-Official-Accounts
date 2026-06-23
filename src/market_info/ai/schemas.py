from typing import Literal

from pydantic import BaseModel, Field, field_validator


StatusLiteral = Literal[
    "拟建",
    "备案",
    "环评公示",
    "环评批复",
    "招标",
    "开工",
    "建设中",
    "投产",
    "停缓建",
    "未知",
]

ALLOWED_STATUSES = {
    "拟建",
    "备案",
    "环评公示",
    "环评批复",
    "招标",
    "开工",
    "建设中",
    "投产",
    "停缓建",
    "未知",
}


class ExtractedProject(BaseModel):
    project_name: str | None = None
    project_info: str | None = None
    province: str | None = None
    city: str | None = None
    detailed_address: str | None = None
    company_name: str | None = None
    investment_amount_yi: float | None = Field(default=None, ge=0)
    industry: str | None = None
    field: str | None = None
    market: str | None = None
    status: StatusLiteral = "未知"
    confidence: float = Field(ge=0, le=1)

    @field_validator(
        "project_name",
        "project_info",
        "province",
        "city",
        "detailed_address",
        "company_name",
        "industry",
        "field",
        "market",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: object) -> str:
        if not isinstance(value, str):
            return "未知"

        stripped = value.strip()
        if stripped in ALLOWED_STATUSES:
            return stripped
        return "未知"

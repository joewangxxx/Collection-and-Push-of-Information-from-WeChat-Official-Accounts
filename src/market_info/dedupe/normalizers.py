import re


PROJECT_STAGE_WORDS = (
    "建设项目",
    "公告",
    "公示",
    "环评",
    "批复",
    "备案",
    "开工",
    "项目",
)

COMPANY_SUFFIXES = (
    "有限责任公司",
    "股份有限公司",
    "有限公司",
    "集团",
    "公司",
)


def normalize_project_name(value: str | None) -> str:
    text = _normalize_whitespace(value)
    for word in PROJECT_STAGE_WORDS:
        text = text.replace(word, "")
    return _collapse_whitespace(text)


def normalize_company_name(value: str | None) -> str:
    text = _normalize_whitespace(value)
    for suffix in COMPANY_SUFFIXES:
        text = text.replace(suffix, "")
    return _collapse_whitespace(text)


def normalize_address(value: str | None) -> str:
    text = _normalize_whitespace(value)
    text = text.replace("经开区", "经济技术开发区")
    text = text.replace("高新区", "高新技术产业开发区")
    return _collapse_whitespace(text)


def _normalize_whitespace(value: str | None) -> str:
    if value is None:
        return ""
    return _collapse_whitespace(str(value).strip())


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()

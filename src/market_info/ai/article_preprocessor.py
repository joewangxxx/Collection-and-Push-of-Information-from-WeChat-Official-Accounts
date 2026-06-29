PROJECT_KEYWORDS = (
    "项目",
    "基地",
    "开工",
    "投产",
    "备案",
    "环评",
    "招标",
    "中标",
    "签约",
    "并网",
    "建设",
    "扩产",
    "投资",
    "亿元",
    "万元",
    "GW",
    "MW",
    "GWh",
    "产能",
    "装机",
    "EPC",
    "园区",
    "示范区",
)

NOISE_KEYWORDS = (
    "点击关注",
    "在小说阅读器读本章",
    "去阅读",
    "分享",
    "点赞",
    "广告合作",
    "设为星标",
    "点个在看",
)


def prepare_article_text_for_extraction(article_text: str, max_chars: int = 12000) -> str:
    if not article_text or not article_text.strip():
        return ""

    if len(article_text) <= max_chars:
        return article_text

    paragraphs = _split_paragraphs(article_text)
    business_paragraphs = [
        paragraph for paragraph in paragraphs if not _is_noise_paragraph(paragraph)
    ]
    matched_indices = [
        index
        for index, paragraph in enumerate(business_paragraphs)
        if has_project_signal(paragraph)
    ]
    if not matched_indices:
        return ""

    selected_indices: set[int] = set()
    for index in matched_indices:
        for neighbor_index in (index - 1, index, index + 1):
            if 0 <= neighbor_index < len(business_paragraphs):
                selected_indices.add(neighbor_index)

    ordered_indices = sorted(selected_indices)
    return _join_with_limit(
        business_paragraphs,
        ordered_indices,
        set(matched_indices),
        max_chars,
    )


def _split_paragraphs(article_text: str) -> list[str]:
    normalized_text = article_text.replace("\r\n", "\n").replace("\r", "\n")
    return [
        paragraph.strip()
        for paragraph in normalized_text.split("\n")
        if paragraph.strip()
    ]


def _is_noise_paragraph(paragraph: str) -> bool:
    return any(keyword in paragraph for keyword in NOISE_KEYWORDS)


def has_project_signal(text: str) -> bool:
    normalized_text = text.lower()
    return any(keyword.lower() in normalized_text for keyword in PROJECT_KEYWORDS)


def _join_with_limit(
    paragraphs: list[str],
    ordered_indices: list[int],
    matched_indices: set[int],
    max_chars: int,
) -> str:
    output_parts: list[str] = []
    current_length = 0
    for position, paragraph_index in enumerate(ordered_indices):
        paragraph = paragraphs[paragraph_index]
        is_matched = paragraph_index in matched_indices
        if not is_matched and _has_future_matched_paragraph(
            ordered_indices,
            matched_indices,
            position,
        ):
            next_matched_length = _next_matched_paragraph_length(
                paragraphs,
                ordered_indices,
                matched_indices,
                position,
            )
            separator_length = 1 if output_parts else 0
            next_separator_length = 1 if output_parts or paragraph else 0
            needed_length = (
                current_length
                + separator_length
                + len(paragraph)
                + next_separator_length
                + min(next_matched_length, max_chars)
            )
            if needed_length > max_chars:
                continue

        separator_length = 1 if output_parts else 0
        available = max_chars - current_length - separator_length
        if available <= 0:
            break
        if len(paragraph) > available:
            if is_matched and available > 0:
                output_parts.append(paragraph[:available])
            break
        output_parts.append(paragraph)
        current_length += len(paragraph) + separator_length
    return "\n".join(output_parts)


def _has_future_matched_paragraph(
    ordered_indices: list[int],
    matched_indices: set[int],
    position: int,
) -> bool:
    return any(index in matched_indices for index in ordered_indices[position + 1 :])


def _next_matched_paragraph_length(
    paragraphs: list[str],
    ordered_indices: list[int],
    matched_indices: set[int],
    position: int,
) -> int:
    for index in ordered_indices[position + 1 :]:
        if index in matched_indices:
            return len(paragraphs[index])
    return 0

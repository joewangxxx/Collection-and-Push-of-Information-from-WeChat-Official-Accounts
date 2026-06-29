from market_info.ai.article_preprocessor import prepare_article_text_for_extraction


def test_short_article_text_is_returned_unchanged() -> None:
    text = "点击关注\n这是一篇短文，提到行业新闻但长度很短。"

    assert prepare_article_text_for_extraction(text, max_chars=100) == text


def test_long_article_keeps_project_paragraphs_and_adjacent_context() -> None:
    paragraphs = [
        "行业背景段落，介绍当地新能源发展情况。",
        "江苏某公司在盐城投资建设光伏组件基地项目，总投资20亿元。",
        "该项目建成后将形成5GW组件产能。",
        " unrelated market news " * 30,
        "另一个普通段落，没有更多业务信息。",
    ]
    text = "\n".join(paragraphs)

    prepared = prepare_article_text_for_extraction(text, max_chars=180)

    assert "行业背景段落" in prepared
    assert "光伏组件基地项目" in prepared
    assert "5GW组件产能" in prepared
    assert "unrelated market news" not in prepared
    assert prepared.index("行业背景段落") < prepared.index("光伏组件基地项目")


def test_long_article_without_project_signal_returns_empty_string() -> None:
    text = "\n".join(
        [
            "今日行业价格走势整体平稳，企业观点分歧较大。" * 20,
            "会议嘉宾分享了产品效率和市场趋势。" * 20,
            "欢迎读者留言交流。" * 20,
        ]
    )

    assert prepare_article_text_for_extraction(text, max_chars=120) == ""


def test_noise_paragraphs_are_removed_from_long_article() -> None:
    text = "\n".join(
        [
            "点击关注，设为星标。",
            "前情摘要。",
            "某新能源企业签约建设储能示范区项目，投资5亿元。",
            "广告合作请联系后台。",
            "分享，点赞，在看。",
        ]
    )

    prepared = prepare_article_text_for_extraction(text, max_chars=60)

    assert "储能示范区项目" in prepared
    assert "点击关注" not in prepared
    assert "广告合作" not in prepared
    assert "点赞" not in prepared


def test_common_share_like_words_do_not_remove_project_reporting_paragraph() -> None:
    text = "\n".join(
        [
            "前情摘要。",
            "专家分享称，某新能源企业投资建设光伏基地项目，总投资8亿元。",
            "点赞、分享、在看。",
            "普通资讯。" * 100,
        ]
    )

    prepared = prepare_article_text_for_extraction(text, max_chars=120)

    assert "专家分享称" in prepared
    assert "光伏基地项目" in prepared
    assert "点赞" not in prepared


def test_preprocessed_text_never_exceeds_max_chars() -> None:
    text = "\n".join(
        [
            "背景段落" * 50,
            "某公司备案建设光伏项目，总投资10亿元，计划开工。" * 50,
            "后续影响" * 50,
        ]
    )

    prepared = prepare_article_text_for_extraction(text, max_chars=120)

    assert prepared
    assert len(prepared) <= 120


def test_long_context_cannot_consume_budget_before_matched_paragraph() -> None:
    text = "\n".join(
        [
            "很长的背景介绍" * 100,
            "某公司备案建设光伏项目，总投资10亿元。",
        ]
    )

    prepared = prepare_article_text_for_extraction(text, max_chars=80)

    assert "光伏项目" in prepared
    assert not prepared.startswith("很长的背景介绍")
    assert len(prepared) <= 80

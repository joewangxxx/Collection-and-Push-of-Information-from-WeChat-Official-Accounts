from market_info.ai.embeddings import build_project_semantic_text
from market_info.ai.schemas import ExtractedProject


def test_semantic_text_contains_core_project_fields() -> None:
    project = ExtractedProject(
        project_name="宁夏光伏基地项目",
        company_name="示例新能源有限公司",
        province="宁夏回族自治区",
        city="银川市",
        detailed_address="贺兰县产业园",
        investment_amount_yi=12.5,
        industry="新能源",
        field="光伏",
        market="电力",
        status="备案",
        project_info="建设光伏电站及配套储能设施",
        confidence=0.9,
    )

    semantic_text = build_project_semantic_text(project)

    assert "项目名称：宁夏光伏基地项目" in semantic_text
    assert "企业名称：示例新能源有限公司" in semantic_text
    assert "地点：宁夏回族自治区 银川市 贺兰县产业园" in semantic_text
    assert "投资额：12.5亿元" in semantic_text
    assert "产业：新能源" in semantic_text
    assert "领域：光伏" in semantic_text
    assert "市场：电力" in semantic_text
    assert "状态：备案" in semantic_text
    assert "项目信息：建设光伏电站及配套储能设施" in semantic_text


def test_semantic_text_does_not_include_source_metadata() -> None:
    project = ExtractedProject(
        project_name="组件扩产项目",
        company_name="示例组件有限公司",
        province="江苏省",
        city="盐城市",
        detailed_address=None,
        investment_amount_yi=None,
        industry=None,
        field="光伏组件",
        market=None,
        status="未知",
        project_info="新增高效组件产线",
        confidence=0.8,
    )

    semantic_text = build_project_semantic_text(project)

    assert "光伏前沿" not in semantic_text
    assert "https://mp.weixin.qq.com" not in semantic_text
    assert "文章标题" not in semantic_text
    assert "发布时间" not in semantic_text

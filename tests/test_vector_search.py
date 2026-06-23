from market_info.dedupe.vector_search import VectorCandidate, VectorSearch


class FakeResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def mappings(self) -> "FakeResult":
        return self

    def all(self) -> list[object]:
        return self.rows


class FakeSession:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.statement = None
        self.params = None
        self.execute_count = 0

    def execute(self, statement, params):
        self.execute_count += 1
        self.statement = statement
        self.params = params
        return FakeResult(self.rows)


def test_vector_search_executes_pgvector_query_with_province_filter() -> None:
    session = FakeSession([{"project_id": 7, "vector_similarity": 0.91}])
    search = VectorSearch(session)

    candidates = search.find_candidates([0.1, 0.2, 0.3], province="江苏省", limit=5)

    statement_text = str(session.statement)
    assert "1 - (embedding <=> CAST(:embedding AS vector)) AS vector_similarity" in statement_text
    assert "province = :province" in statement_text
    assert "ORDER BY embedding <=> CAST(:embedding AS vector)" in statement_text
    assert session.params == {
        "embedding": "[0.1,0.2,0.3]",
        "province": "江苏省",
        "limit": 5,
    }
    assert candidates == [VectorCandidate(project_id=7, vector_similarity=0.91)]


def test_vector_search_omits_province_filter_when_province_is_empty() -> None:
    session = FakeSession([{"project_id": 8, "vector_similarity": 0.82}])
    search = VectorSearch(session)

    candidates = search.find_candidates([0.1, 0.2], province=None)

    statement_text = str(session.statement)
    assert "province = :province" not in statement_text
    assert session.params == {"embedding": "[0.1,0.2]", "limit": 20}
    assert candidates == [VectorCandidate(project_id=8, vector_similarity=0.82)]


def test_vector_search_returns_empty_for_empty_embedding() -> None:
    session = FakeSession([{"project_id": 9, "vector_similarity": 0.7}])
    search = VectorSearch(session)

    assert search.find_candidates([], province=None) == []
    assert session.execute_count == 0

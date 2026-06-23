from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class VectorCandidate:
    project_id: int
    vector_similarity: float


class VectorSearch:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_candidates(
        self,
        embedding: list[float],
        province: str | None,
        limit: int = 20,
    ) -> list[VectorCandidate]:
        if not embedding:
            return []

        where_clauses = ["embedding IS NOT NULL"]
        params: dict[str, object] = {
            "embedding": _format_vector(embedding),
            "limit": limit,
        }

        if province:
            where_clauses.append("province = :province")
            params["province"] = province

        statement = text(
            f"""
            SELECT
                id AS project_id,
                1 - (embedding <=> CAST(:embedding AS vector)) AS vector_similarity
            FROM projects
            WHERE {" AND ".join(where_clauses)}
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
            """
        )

        rows = self.session.execute(statement, params).mappings().all()
        return [
            VectorCandidate(
                project_id=int(row["project_id"]),
                vector_similarity=float(row["vector_similarity"]),
            )
            for row in rows
        ]


def _format_vector(embedding: list[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in embedding) + "]"

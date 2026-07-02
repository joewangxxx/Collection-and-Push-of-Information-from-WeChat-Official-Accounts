from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from market_info.db.base import Base


PROCESSING_STATUS_VALUES = ("pending", "processed", "failed")
processing_status_type = Enum(
    *PROCESSING_STATUS_VALUES,
    name="source_article_processing_status",
    native_enum=False,
    validate_strings=True,
    length=50,
)


class MpAccount(Base):
    __tablename__ = "mp_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    fakeid: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_fetch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    articles: Mapped[list["SourceArticle"]] = relationship(back_populates="account")


class SourceArticle(Base):
    __tablename__ = "source_articles"
    __table_args__ = (
        Index("ix_source_articles_normalized_url", "normalized_url", unique=True),
        Index("ix_source_articles_content_hash", "content_hash"),
        Index("ix_source_articles_processing_status", "processing_status"),
        CheckConstraint(
            "processing_status in ('pending', 'processed', 'failed')",
            name="ck_source_articles_processing_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("mp_accounts.id"),
        nullable=False,
    )
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    article_url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    processing_status: Mapped[str] = mapped_column(
        processing_status_type,
        nullable=False,
        default="pending",
        server_default="pending",
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extraction_error: Mapped[str | None] = mapped_column(Text)
    extraction_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    account: Mapped[MpAccount] = relationship(back_populates="articles")
    project_records: Mapped[list["ProjectRecord"]] = relationship(
        back_populates="source_article",
    )


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_province", "province"),
        Index("ix_projects_city", "city"),
        Index(
            "ix_projects_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_project_name: Mapped[str | None] = mapped_column(String(500))
    canonical_company_name: Mapped[str | None] = mapped_column(String(500))
    province: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    detailed_address: Mapped[str | None] = mapped_column(String(500))
    investment_amount_yi: Mapped[float | None] = mapped_column(Numeric(14, 4))
    industry: Mapped[str | None] = mapped_column(String(255))
    field: Mapped[str | None] = mapped_column(String(255))
    market: Mapped[str | None] = mapped_column(String(255))
    current_status: Mapped[str | None] = mapped_column(String(100))
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    semantic_text: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    records: Mapped[list["ProjectRecord"]] = relationship(back_populates="project")
    events: Mapped[list["ProjectEvent"]] = relationship(back_populates="project")


class ProjectRecord(Base):
    __tablename__ = "project_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_article_id: Mapped[int] = mapped_column(
        ForeignKey("source_articles.id"),
        nullable=False,
    )
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    project_name: Mapped[str | None] = mapped_column(String(500))
    project_info: Mapped[str | None] = mapped_column(Text)
    province: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    detailed_address: Mapped[str | None] = mapped_column(String(500))
    company_name: Mapped[str | None] = mapped_column(String(500))
    investment_amount_yi: Mapped[float | None] = mapped_column(Numeric(14, 4))
    industry: Mapped[str | None] = mapped_column(String(255))
    field: Mapped[str | None] = mapped_column(String(255))
    market: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float | None] = mapped_column(Float)
    semantic_text: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    dedupe_decision: Mapped[str | None] = mapped_column(String(50))
    dedupe_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    source_article: Mapped[SourceArticle] = relationship(back_populates="project_records")
    project: Mapped[Project | None] = relationship(back_populates="records")


class ProjectEvent(Base):
    __tablename__ = "project_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    source_article_id: Mapped[int] = mapped_column(
        ForeignKey("source_articles.id"),
        nullable=False,
    )
    event_status: Mapped[str] = mapped_column(String(100), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(100))
    event_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_label: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped[Project] = relationship(back_populates="events")
    source_article: Mapped[SourceArticle] = relationship()


class PushLog(Base):
    __tablename__ = "push_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str | None] = mapped_column(String(100))
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    recipient: Mapped[str | None] = mapped_column(String(500))
    subject: Mapped[str | None] = mapped_column(String(500))
    message: Mapped[str | None] = mapped_column(Text)
    artifact_path: Mapped[str | None] = mapped_column(String(1000))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class OpsJobRun(Base):
    __tablename__ = "ops_job_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    params_json: Mapped[str | None] = mapped_column(Text)
    result_json: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    logs_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

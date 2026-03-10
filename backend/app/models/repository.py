from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_language: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    forks: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending | queued | processing | processed | failed
    processed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_commits: Mapped[int] = mapped_column(Integer, default=0)
    total_contributors: Mapped[int] = mapped_column(Integer, default=0)
    created_in_db: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_in_db: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Repository {self.full_name}>"

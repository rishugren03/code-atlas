from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Contributor(Base):
    __tablename__ = "contributors"
    __table_args__ = (
        UniqueConstraint("repo_id", "email", name="uq_contributor_repo_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[int] = mapped_column(Integer, ForeignKey("repositories.id"), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_commits: Mapped[int] = mapped_column(Integer, default=0)
    total_additions: Mapped[int] = mapped_column(Integer, default=0)
    total_deletions: Mapped[int] = mapped_column(Integer, default=0)
    first_commit_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_commit_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Contributor {self.name} ({self.email})>"

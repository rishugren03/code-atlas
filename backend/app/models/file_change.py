from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class FileChange(Base):
    __tablename__ = "file_changes"
    __table_args__ = (
        Index("idx_file_changes_path", "repo_id", "file_path"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    commit_id: Mapped[int] = mapped_column(Integer, ForeignKey("commits.id"), nullable=False)
    repo_id: Mapped[int] = mapped_column(Integer, ForeignKey("repositories.id"), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    change_type: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # added | modified | deleted | renamed
    additions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<FileChange {self.file_path} ({self.change_type})>"

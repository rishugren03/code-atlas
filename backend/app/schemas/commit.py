"""Pydantic schemas for commit endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field


class CommitResponse(BaseModel):
    """Single commit response."""

    id: int
    commit_hash: str
    author_name: str | None = None
    author_email: str | None = None
    committed_at: datetime | None = None
    message: str | None = None
    files_changed: int = 0
    additions: int = 0
    deletions: int = 0
    parent_hash: str | None = None

    model_config = {"from_attributes": True}


class CommitListResponse(BaseModel):
    """Paginated list of commits."""

    items: list[CommitResponse]
    total: int
    page: int = Field(1, ge=1)
    per_page: int = Field(50, ge=1, le=200)
    total_pages: int = 0

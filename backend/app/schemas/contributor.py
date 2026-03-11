"""Pydantic schemas for contributor endpoints."""

from datetime import datetime

from pydantic import BaseModel


class ContributorResponse(BaseModel):
    """Single contributor response."""

    id: int
    name: str | None = None
    email: str | None = None
    total_commits: int = 0
    total_additions: int = 0
    total_deletions: int = 0
    first_commit_at: datetime | None = None
    last_commit_at: datetime | None = None

    model_config = {"from_attributes": True}


class ContributorListResponse(BaseModel):
    """List of contributors."""

    items: list[ContributorResponse]
    total: int

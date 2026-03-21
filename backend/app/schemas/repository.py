"""Pydantic schemas for repository endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


# ─── Request Schemas ────────────────────────────────────────


class RepoAnalyzeRequest(BaseModel):
    """Request body for POST /api/repos/analyze."""

    url: HttpUrl = Field(..., description="GitHub repository URL to analyze. The system is highly optimized and can process massive repositories with hundreds of thousands of commits (like React or VSCode) in few minutes.")


# ─── Response Schemas ───────────────────────────────────────


class RepoAnalyzeResponse(BaseModel):
    """Response after submitting a repo for analysis."""

    id: int
    full_name: str
    status: str
    message: str


class RepoStatusResponse(BaseModel):
    """Processing status response."""

    id: int
    full_name: str
    status: str
    progress: float = Field(0.0, description="Processing progress 0-100")
    commits_processed: int = 0
    total_commits_found: int = 0
    message: str = ""


class RepoDetailResponse(BaseModel):
    """Full repository details."""

    id: int
    owner: str
    name: str
    full_name: str
    url: str
    description: str | None = None
    primary_language: str | None = None
    stars: int = 0
    forks: int = 0
    created_at: datetime | None = None
    last_commit_sha: str | None = None
    processing_status: str
    processed_at: datetime | None = None
    total_commits: int = 0
    total_contributors: int = 0
    created_in_db: datetime | None = None
    updated_in_db: datetime | None = None

    model_config = {"from_attributes": True}

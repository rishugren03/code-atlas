"""Repository API router — submit repos for analysis and check status."""

import json

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.schemas.repository import (
    RepoAnalyzeRequest,
    RepoAnalyzeResponse,
    RepoDetailResponse,
    RepoStatusResponse,
)
from app.services.repository import (
    create_or_get_repository,
    get_repository,
    update_processing_status,
)
from app.utils.github import parse_github_url
from app.workers.tasks import analyze_repository

router = APIRouter(prefix="/api/repos", tags=["repositories"])


@router.post("/analyze", response_model=RepoAnalyzeResponse)
async def submit_repo_for_analysis(
    request: RepoAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit a GitHub repository URL for analysis.

    - If the repo is new, create a record and queue a Celery task.
    - If the repo is already processing/queued, return the current status.
    - If the repo was previously processed/failed, re-queue for analysis.
    """
    # Parse the GitHub URL
    try:
        owner, name = parse_github_url(str(request.url))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create or get existing repo
    repo = await create_or_get_repository(db, owner, name, str(request.url))
    await db.commit()

    # Determine action based on current status
    if repo.processing_status in ("queued", "processing"):
        return RepoAnalyzeResponse(
            id=repo.id,
            full_name=repo.full_name,
            status=repo.processing_status,
            message=f"Repository is already {repo.processing_status}.",
        )

    # Queue the analysis (new, processed, or failed repos)
    repo = await update_processing_status(db, repo.id, "queued")
    await db.commit()

    # Dispatch Celery task
    analyze_repository.delay(repo.id)

    return RepoAnalyzeResponse(
        id=repo.id,
        full_name=repo.full_name,
        status="queued",
        message="Repository analysis queued. Use GET /api/repos/{id}/status to check progress.",
    )


@router.get("/{repo_id}", response_model=RepoDetailResponse)
async def get_repo_details(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get full details of a repository."""
    repo = await get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return RepoDetailResponse.model_validate(repo)


@router.get("/{repo_id}/status", response_model=RepoStatusResponse)
async def get_repo_status(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get the processing status of a repository.

    Returns progress information from Redis if available,
    otherwise returns the status from the database.
    """
    repo = await get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Try to get live progress from Redis
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        progress_data = await redis_client.get(f"repo:{repo_id}:progress")
        await redis_client.aclose()

        if progress_data:
            data = json.loads(progress_data)
            return RepoStatusResponse(
                id=repo.id,
                full_name=repo.full_name,
                status=data.get("status", repo.processing_status),
                progress=data.get("progress", 0),
                commits_processed=data.get("commits_processed", 0),
                total_commits_found=data.get("total_commits_found", 0),
                message=data.get("message", ""),
            )
    except Exception:
        pass  # Fall back to DB status

    # Fallback: return status from database
    return RepoStatusResponse(
        id=repo.id,
        full_name=repo.full_name,
        status=repo.processing_status,
        progress=100.0 if repo.processing_status == "processed" else 0.0,
        commits_processed=repo.total_commits,
        total_commits_found=repo.total_commits,
        message=_status_message(repo.processing_status),
    )


def _status_message(status: str) -> str:
    """Human-readable message for a given status."""
    messages = {
        "pending": "Waiting to be queued.",
        "queued": "Queued for processing.",
        "processing": "Analysis in progress...",
        "processed": "Analysis complete.",
        "failed": "Analysis failed. Please retry.",
    }
    return messages.get(status, "Unknown status.")

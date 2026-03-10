"""Repository service layer — business logic for repo operations."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repository import Repository


async def create_or_get_repository(
    db: AsyncSession,
    owner: str,
    name: str,
    url: str,
) -> Repository:
    """Find an existing repo or create a new one.

    If the repo already exists and is in a terminal state (processed/failed),
    it can be re-queued. If it's currently processing/queued, return as-is.
    """
    full_name = f"{owner}/{name}"

    result = await db.execute(
        select(Repository).where(Repository.full_name == full_name)
    )
    repo = result.scalar_one_or_none()

    if repo is not None:
        return repo

    # Create new repository record
    repo = Repository(
        owner=owner,
        name=name,
        full_name=full_name,
        url=url,
        processing_status="pending",
    )
    db.add(repo)
    await db.flush()  # get the ID without committing
    await db.refresh(repo)
    return repo


async def get_repository(db: AsyncSession, repo_id: int) -> Repository | None:
    """Fetch a repository by ID."""
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    return result.scalar_one_or_none()


async def update_processing_status(
    db: AsyncSession,
    repo_id: int,
    status: str,
    processed_at: datetime | None = None,
) -> Repository | None:
    """Update the processing status of a repository."""
    repo = await get_repository(db, repo_id)
    if repo is None:
        return None

    repo.processing_status = status
    if processed_at:
        repo.processed_at = processed_at
    repo.updated_in_db = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(repo)
    return repo

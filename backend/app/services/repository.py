"""Repository service layer — business logic for repo operations."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commit import Commit
from app.models.contributor import Contributor
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


async def get_repository_by_name(
    db: AsyncSession, owner: str, name: str
) -> Repository | None:
    """Fetch a repository by owner/name."""
    full_name = f"{owner}/{name}"
    result = await db.execute(
        select(Repository).where(Repository.full_name == full_name)
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


async def get_repo_commits(
    db: AsyncSession,
    repo_id: int,
    page: int = 1,
    per_page: int = 50,
    author: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[Commit], int]:
    """Get paginated commits for a repository with optional filters.

    Returns (commits_list, total_count).
    """
    # Base query
    query = select(Commit).where(Commit.repo_id == repo_id)
    count_query = select(func.count(Commit.id)).where(Commit.repo_id == repo_id)

    # Apply filters
    if author:
        author_filter = f"%{author}%"
        query = query.where(
            (Commit.author_name.ilike(author_filter))
            | (Commit.author_email.ilike(author_filter))
        )
        count_query = count_query.where(
            (Commit.author_name.ilike(author_filter))
            | (Commit.author_email.ilike(author_filter))
        )

    if date_from:
        query = query.where(Commit.committed_at >= date_from)
        count_query = count_query.where(Commit.committed_at >= date_from)

    if date_to:
        query = query.where(Commit.committed_at <= date_to)
        count_query = count_query.where(Commit.committed_at <= date_to)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination (newest first)
    offset = (page - 1) * per_page
    query = query.order_by(Commit.committed_at.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    commits = list(result.scalars().all())

    return commits, total


async def get_repo_contributors(
    db: AsyncSession,
    repo_id: int,
) -> list[Contributor]:
    """Get all contributors for a repository, sorted by commit count descending."""
    result = await db.execute(
        select(Contributor)
        .where(Contributor.repo_id == repo_id)
        .order_by(Contributor.total_commits.desc())
    )
    return list(result.scalars().all())

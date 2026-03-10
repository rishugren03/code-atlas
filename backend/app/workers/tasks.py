"""Celery tasks for repository processing.

Uses PyDriller to parse commit history and stores results in PostgreSQL.
"""

import logging
import os
import shutil
from datetime import datetime, timezone

import redis
from pydriller import Repository as PyDrillerRepo
from sqlalchemy import select

from app.config import settings
from app.db.database import SyncSessionLocal
from app.models.commit import Commit
from app.models.contributor import Contributor
from app.models.file_change import FileChange
from app.models.repository import Repository
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Redis client for publishing progress
_redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def _publish_progress(repo_id: int, data: dict):
    """Store progress in Redis and publish to a channel for WebSocket consumers."""
    import json

    key = f"repo:{repo_id}:progress"
    _redis.set(key, json.dumps(data), ex=3600)  # expire after 1 hour
    _redis.publish(f"repo:{repo_id}:updates", json.dumps(data))


@celery_app.task(bind=True, name="analyze_repository", max_retries=2)
def analyze_repository(self, repo_id: int):
    """Main task: clone a repo, parse commits with PyDriller, and store in DB.

    Steps:
        1. Update status → processing
        2. Clone the repo
        3. Traverse commits with PyDriller
        4. Batch-insert commits, file changes, and contributors
        5. Update status → processed
    """
    session = SyncSessionLocal()
    clone_path = None

    try:
        # ─── Step 1: Fetch repo and update status ──────────
        repo = session.execute(
            select(Repository).where(Repository.id == repo_id)
        ).scalar_one_or_none()

        if repo is None:
            logger.error(f"Repository {repo_id} not found")
            return {"error": "Repository not found"}

        repo.processing_status = "processing"
        session.commit()

        _publish_progress(repo_id, {
            "status": "processing",
            "progress": 0,
            "message": "Cloning repository...",
            "commits_processed": 0,
            "total_commits_found": 0,
        })

        # ─── Step 2: Clone the repository ──────────────────
        clone_path = os.path.join(settings.CLONE_DIR, repo.owner, repo.name)
        os.makedirs(os.path.dirname(clone_path), exist_ok=True)

        # Remove existing clone if present
        if os.path.exists(clone_path):
            shutil.rmtree(clone_path)

        _publish_progress(repo_id, {
            "status": "processing",
            "progress": 5,
            "message": f"Cloning {repo.full_name}...",
            "commits_processed": 0,
            "total_commits_found": 0,
        })

        # ─── Step 3: Parse commits with PyDriller ──────────
        # Determine if we need incremental update
        from_commit = repo.last_commit_sha if repo.last_commit_sha else None

        if not from_commit:
            # Fresh start: clear any existing data from partial/failed runs/retries
            from sqlalchemy import delete
            session.execute(delete(FileChange).where(FileChange.repo_id == repo_id))
            session.execute(delete(Commit).where(Commit.repo_id == repo_id))
            session.execute(delete(Contributor).where(Contributor.repo_id == repo_id))
            session.commit()

        pydriller_kwargs = {"path_to_repo": repo.url}
        if from_commit:
            pydriller_kwargs["from_commit"] = from_commit

        # First pass: count total commits for progress reporting
        logger.info(f"Starting analysis of {repo.full_name}")

        commits_data = []
        contributor_map = {}  # email -> contributor data
        total_processed = 0
        last_commit_sha = None

        commit_batch = []
        file_change_batch = []
        BATCH_SIZE = 500

        for commit in PyDrillerRepo(**pydriller_kwargs).traverse_commits():
            # Skip the starting commit if we are doing an incremental run
            if from_commit and commit.hash == from_commit:
                continue

            # Safety: cap the max number of commits
            if total_processed >= settings.MAX_COMMITS:
                logger.warning(
                    f"Reached max commit limit ({settings.MAX_COMMITS}) for {repo.full_name}"
                )
                break

            total_processed += 1
            last_commit_sha = commit.hash

            # Build commit record
            commit_record = Commit(
                repo_id=repo_id,
                commit_hash=commit.hash,
                author_name=commit.author.name if commit.author else None,
                author_email=commit.author.email if commit.author else None,
                committed_at=commit.committer_date,
                message=commit.msg[:2000] if commit.msg else None,  # truncate long messages
                files_changed=commit.files,
                additions=commit.insertions,
                deletions=commit.deletions,
                parent_hash=commit.parents[0] if commit.parents else None,
            )
            commit_batch.append(commit_record)

            # Collect file changes
            for mod in commit.modified_files:
                change_type = _get_change_type(mod.change_type)
                file_change_batch.append({
                    "file_path": mod.new_path or mod.old_path or "unknown",
                    "change_type": change_type,
                    "additions": mod.added_lines,
                    "deletions": mod.deleted_lines,
                    "commit_hash": commit.hash,
                })

            # Track contributors
            if commit.author and commit.author.email:
                email = commit.author.email
                if email not in contributor_map:
                    contributor_map[email] = {
                        "name": commit.author.name,
                        "email": email,
                        "total_commits": 0,
                        "total_additions": 0,
                        "total_deletions": 0,
                        "first_commit_at": commit.committer_date,
                        "last_commit_at": commit.committer_date,
                    }
                contrib = contributor_map[email]
                contrib["total_commits"] += 1
                contrib["total_additions"] += commit.insertions
                contrib["total_deletions"] += commit.deletions
                if commit.committer_date < contrib["first_commit_at"]:
                    contrib["first_commit_at"] = commit.committer_date
                if commit.committer_date > contrib["last_commit_at"]:
                    contrib["last_commit_at"] = commit.committer_date

            # Batch insert commits every BATCH_SIZE
            if len(commit_batch) >= BATCH_SIZE:
                _flush_commit_batch(session, repo_id, commit_batch, file_change_batch)
                commit_batch = []
                file_change_batch = []

                # Publish progress
                _publish_progress(repo_id, {
                    "status": "processing",
                    "progress": min(90, 10 + (total_processed / max(total_processed + 100, 1)) * 80),
                    "message": f"Processed {total_processed} commits...",
                    "commits_processed": total_processed,
                    "total_commits_found": total_processed,
                })

        # Flush remaining batch
        if commit_batch:
            _flush_commit_batch(session, repo_id, commit_batch, file_change_batch)

        # ─── Step 4: Insert contributors ───────────────────
        _publish_progress(repo_id, {
            "status": "processing",
            "progress": 92,
            "message": "Saving contributor data...",
            "commits_processed": total_processed,
            "total_commits_found": total_processed,
        })

        from sqlalchemy.dialects.postgresql import insert as pg_insert

        for email, data in contributor_map.items():
            stmt = pg_insert(Contributor).values(
                repo_id=repo_id,
                name=data["name"],
                email=data["email"],
                total_commits=data["total_commits"],
                total_additions=data["total_additions"],
                total_deletions=data["total_deletions"],
                first_commit_at=data["first_commit_at"],
                last_commit_at=data["last_commit_at"],
            )
            # Upsert on conflict
            stmt = stmt.on_conflict_do_update(
                index_elements=["repo_id", "email"],
                set_={
                    "total_commits": Contributor.total_commits + stmt.excluded.total_commits,
                    "total_additions": Contributor.total_additions + stmt.excluded.total_additions,
                    "total_deletions": Contributor.total_deletions + stmt.excluded.total_deletions,
                    "last_commit_at": stmt.excluded.last_commit_at,
                }
            )
            session.execute(stmt)

        session.commit()

        # ─── Step 5: Update repo stats ─────────────────────
        repo.total_commits = total_processed
        repo.total_contributors = len(contributor_map)
        repo.last_commit_sha = last_commit_sha
        repo.processing_status = "processed"
        repo.processed_at = datetime.now(timezone.utc)
        session.commit()

        _publish_progress(repo_id, {
            "status": "processed",
            "progress": 100,
            "message": f"Complete! {total_processed} commits, {len(contributor_map)} contributors.",
            "commits_processed": total_processed,
            "total_commits_found": total_processed,
        })

        logger.info(
            f"✅ Finished analyzing {repo.full_name}: "
            f"{total_processed} commits, {len(contributor_map)} contributors"
        )

        return {
            "repo_id": repo_id,
            "commits": total_processed,
            "contributors": len(contributor_map),
            "status": "processed",
        }

    except Exception as exc:
        logger.exception(f"❌ Failed to analyze repo {repo_id}: {exc}")
        session.rollback()

        # Update status to failed
        try:
            repo = session.execute(
                select(Repository).where(Repository.id == repo_id)
            ).scalar_one_or_none()
            if repo:
                repo.processing_status = "failed"
                session.commit()
        except Exception:
            session.rollback()

        _publish_progress(repo_id, {
            "status": "failed",
            "progress": 0,
            "message": f"Error: {str(exc)[:500]}",
            "commits_processed": 0,
            "total_commits_found": 0,
        })

        raise self.retry(exc=exc, countdown=60)

    finally:
        session.close()
        # Clean up cloned repo
        if clone_path and os.path.exists(clone_path):
            shutil.rmtree(clone_path, ignore_errors=True)


def _flush_commit_batch(session, repo_id: int, commits: list, file_changes: list):
    """Flush a batch of commits and their file changes to the database."""
    # Insert commits
    session.add_all(commits)
    session.flush()  # get IDs assigned

    # Build a hash → ID mapping for file changes
    hash_to_id = {c.commit_hash: c.id for c in commits}

    # Insert file changes
    for fc_data in file_changes:
        commit_id = hash_to_id.get(fc_data["commit_hash"])
        if commit_id:
            fc = FileChange(
                commit_id=commit_id,
                repo_id=repo_id,
                file_path=fc_data["file_path"],
                change_type=fc_data["change_type"],
                additions=fc_data["additions"],
                deletions=fc_data["deletions"],
            )
            session.add(fc)

    session.commit()


def _get_change_type(change_type) -> str:
    """Convert PyDriller's ModificationType to a string."""
    if change_type is None:
        return "modified"

    name = change_type.name.lower()
    mapping = {
        "add": "added",
        "delete": "deleted",
        "modify": "modified",
        "rename": "renamed",
        "copy": "added",
    }
    return mapping.get(name, "modified")

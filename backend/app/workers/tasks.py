"""Celery tasks for repository processing.

Uses raw git commands to parse commit history and stores results in PostgreSQL
effectively scaling to hundreds of thousands of commits.

Performance Strategy:
  - Phase 1: Fast commit metadata via --shortstat (~10x faster than --numstat)
  - Phase 2: Detailed file changes via --numstat (deferred / lazy)
  - Batch DB inserts with ON CONFLICT for idempotent re-runs
  - Batch contributor upserts (single statement instead of N)
"""

import json
import logging
import os
import shutil
import subprocess
import urllib.request
from datetime import datetime, timezone

import redis
from sqlalchemy import select, delete, func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

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
    key = f"repo:{repo_id}:progress"
    payload = json.dumps(data)
    _redis.set(key, payload, ex=3600)  # expire after 1 hour
    _redis.publish(f"repo:{repo_id}:updates", payload)


# ---------------------------------------------------------------------------
# Phase 1: Fast parsing – commit metadata + aggregate stats (--shortstat)
# ---------------------------------------------------------------------------

def _parse_git_log_fast(clone_path: str, from_commit: str = None):
    """Parse git log with --shortstat for fast aggregate stats per commit.

    Uses --shortstat instead of --numstat: avoids per-file diff computation,
    yielding ~10x speedup on large repositories.

    Yields dicts with: hash, author_name, author_email, date, parents, message,
    files_changed, additions, deletions.
    """
    # Format: [COMMIT] marker, then hash, author name, email, date ISO, parents, body, [STAT] marker
    cmd = [
        "git",
        "log",
        "--shortstat",
        "--topo-order",
        "--reverse",
        "--format=[COMMIT]%n%H%n%an%n%ae%n%cI%n%P%n%B%n[STAT]"
    ]
    if from_commit:
        cmd.append(f"{from_commit}..HEAD")
    else:
        cmd.append("HEAD")

    process = subprocess.Popen(
        cmd,
        cwd=clone_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    current_commit = None
    parsing_stat = False

    for line in process.stdout:
        line = line.rstrip("\n")

        if line == "[COMMIT]":
            if current_commit:
                yield current_commit
            current_commit = {
                "hash": "",
                "author_name": "",
                "author_email": "",
                "date": "",
                "parents": "",
                "message": [],
                "files_changed": 0,
                "additions": 0,
                "deletions": 0,
            }
            try:
                current_commit["hash"] = next(process.stdout).rstrip("\n")
                current_commit["author_name"] = next(process.stdout).rstrip("\n")
                current_commit["author_email"] = next(process.stdout).rstrip("\n")
                current_commit["date"] = next(process.stdout).rstrip("\n")
                current_commit["parents"] = next(process.stdout).rstrip("\n")
            except StopIteration:
                break
            parsing_stat = False
            continue

        if line == "[STAT]":
            parsing_stat = True
            continue

        if not parsing_stat:
            current_commit["message"].append(line)
        else:
            # --shortstat output looks like:
            #  " 3 files changed, 10 insertions(+), 2 deletions(-)"
            # or partial variants like " 1 file changed, 5 insertions(+)"
            line_stripped = line.strip()
            if not line_stripped:
                continue
            # Parse the shortstat line
            import re
            files_m = re.search(r"(\d+) files? changed", line_stripped)
            ins_m = re.search(r"(\d+) insertions?\(\+\)", line_stripped)
            del_m = re.search(r"(\d+) deletions?\(-\)", line_stripped)
            if files_m:
                current_commit["files_changed"] = int(files_m.group(1))
            if ins_m:
                current_commit["additions"] = int(ins_m.group(1))
            if del_m:
                current_commit["deletions"] = int(del_m.group(1))

    if current_commit:
        yield current_commit

    process.wait()
    if process.returncode != 0:
        err = process.stderr.read()
        logger.error(f"git log error: {err}")
        raise RuntimeError(f"git log failed: {err}")


# ---------------------------------------------------------------------------
# Phase 2: Detailed file changes (--numstat) — deferred / on-demand
# ---------------------------------------------------------------------------

def _parse_git_log_numstat(clone_path: str, from_commit: str = None):
    """Parse git log with --numstat for per-file change details.

    This is slower but provides file-level granularity needed for
    code replay and file evolution features.
    """
    cmd = [
        "git",
        "log",
        "--numstat",
        "--topo-order",
        "--reverse",
        "--format=[COMMIT]%n%H%n[STAT]"
    ]
    if from_commit:
        cmd.append(f"{from_commit}..HEAD")
    else:
        cmd.append("HEAD")

    process = subprocess.Popen(
        cmd,
        cwd=clone_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    current_hash = None
    parsing_stat = False
    file_changes = []

    for line in process.stdout:
        line = line.rstrip("\n")

        if line == "[COMMIT]":
            if current_hash and file_changes:
                yield current_hash, file_changes
            file_changes = []
            try:
                current_hash = next(process.stdout).rstrip("\n")
            except StopIteration:
                break
            parsing_stat = False
            continue

        if line == "[STAT]":
            parsing_stat = True
            continue

        if parsing_stat and line:
            parts = line.split("\t")
            if len(parts) >= 3:
                adds = int(parts[0]) if parts[0] != "-" else 0
                dels = int(parts[1]) if parts[1] != "-" else 0
                path = parts[2]
                file_changes.append({
                    "file_path": path,
                    "change_type": "modified",
                    "additions": adds,
                    "deletions": dels,
                })

    if current_hash and file_changes:
        yield current_hash, file_changes

    process.wait()
    if process.returncode != 0:
        err = process.stderr.read()
        logger.error(f"git log numstat error: {err}")


# ---------------------------------------------------------------------------
# GitHub API helper
# ---------------------------------------------------------------------------

def _fetch_github_metadata(owner: str, name: str, max_retries: int = 2) -> dict | None:
    """Fetch repository metadata from GitHub API with retries."""
    import time

    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(f"https://api.github.com/repos/{owner}/{name}")
            req.add_header("User-Agent", "CodeAtlas-App")
            if settings.GITHUB_TOKEN:
                req.add_header("Authorization", f"token {settings.GITHUB_TOKEN}")
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            if attempt < max_retries:
                logger.warning(
                    f"GitHub API attempt {attempt + 1} failed for {owner}/{name}: {e}. Retrying..."
                )
                time.sleep(2 ** attempt)  # exponential backoff: 1s, 2s
            else:
                logger.warning(f"Could not fetch GitHub API for {owner}/{name} after {max_retries + 1} attempts: {e}")
                return None


# ---------------------------------------------------------------------------
# Main Celery task
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name="analyze_repository", max_retries=2)
def analyze_repository(self, repo_id: int):
    session = SyncSessionLocal()
    clone_path = None

    try:
        # Step 1: Fetch repo and update status
        repo = session.execute(
            select(Repository).where(Repository.id == repo_id)
        ).scalar_one_or_none()

        if repo is None:
            logger.error(f"Repository {repo_id} not found")
            return {"error": "Repository not found"}

        # Fetch GitHub metadata (stars, forks, description, created_at) with retry
        repo_data = _fetch_github_metadata(repo.owner, repo.name)
        if repo_data:
            repo.stars = repo_data.get("stargazers_count", repo.stars or 0)
            repo.forks = repo_data.get("forks_count", repo.forks or 0)
            repo.description = repo_data.get("description") or repo.description
            repo.primary_language = repo_data.get("language") or repo.primary_language
            # Set created_at from GitHub API
            created_str = repo_data.get("created_at")
            if created_str and not repo.created_at:
                try:
                    repo.created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                except ValueError:
                    pass

        repo.processing_status = "processing"
        session.commit()

        _publish_progress(repo_id, {
            "status": "processing",
            "progress": 0,
            "message": "Cloning repository...",
            "commits_processed": 0,
            "total_commits_found": 0,
        })

        # Step 2: Clone the repository
        clone_path = os.path.join(settings.CLONE_DIR, repo.owner, repo.name)
        os.makedirs(os.path.dirname(clone_path), exist_ok=True)

        if os.path.exists(clone_path) and not os.path.exists(os.path.join(clone_path, ".git")):
            shutil.rmtree(clone_path, ignore_errors=True)

        if not os.path.exists(clone_path):
            _publish_progress(repo_id, {
                "status": "processing",
                "progress": 5,
                "message": f"Cloning {repo.full_name}...",
                "commits_processed": 0,
                "total_commits_found": 0,
            })
            subprocess.run(
                ["git", "clone", "--bare", repo.url, clone_path],
                check=True,
                capture_output=True
            )

        # Step 3: Parse commits (Phase 1 — fast, --shortstat)
        from_commit = repo.last_commit_sha if repo.last_commit_sha else None

        if not from_commit:
            # Fresh analysis: clean slate
            session.execute(delete(FileChange).where(FileChange.repo_id == repo_id))
            session.execute(delete(Commit).where(Commit.repo_id == repo_id))
            session.execute(delete(Contributor).where(Contributor.repo_id == repo_id))
            session.commit()
            # BUG FIX: Reset total_commits for fresh analysis so += doesn't double
            repo.total_commits = 0

        logger.info(f"Starting analysis of {repo.full_name} (from_commit={from_commit})")

        contributor_map = {}
        total_processed = 0
        last_commit_sha = None

        commit_batch = []
        BATCH_SIZE = 5000

        for commit in _parse_git_log_fast(clone_path, from_commit):
            if total_processed >= settings.MAX_COMMITS:
                logger.warning(
                    f"Reached max commit limit ({settings.MAX_COMMITS}) for {repo.full_name}"
                )
                break

            total_processed += 1
            last_commit_sha = commit["hash"]

            # Parse date safely
            try:
                committed_at = datetime.fromisoformat(commit["date"])
            except ValueError:
                committed_at = datetime.now(timezone.utc)

            commit_msg = "\n".join(commit["message"])[:2000]

            commit_dict = {
                "repo_id": repo_id,
                "commit_hash": commit["hash"],
                "author_name": commit["author_name"],
                "author_email": commit["author_email"],
                "committed_at": committed_at,
                "message": commit_msg,
                "files_changed": commit["files_changed"],
                "additions": commit["additions"],
                "deletions": commit["deletions"],
                "parent_hash": commit["parents"].split()[0] if commit["parents"] else None,
            }
            commit_batch.append(commit_dict)

            # Accumulate contributor stats in memory
            email = commit["author_email"] or "unknown@example.com"
            if email not in contributor_map:
                contributor_map[email] = {
                    "name": commit["author_name"] or "Unknown",
                    "email": email,
                    "total_commits": 0,
                    "total_additions": 0,
                    "total_deletions": 0,
                    "first_commit_at": committed_at,
                    "last_commit_at": committed_at,
                }
            contrib = contributor_map[email]
            contrib["total_commits"] += 1
            contrib["total_additions"] += commit["additions"]
            contrib["total_deletions"] += commit["deletions"]

            if committed_at < contrib["first_commit_at"]:
                contrib["first_commit_at"] = committed_at
            if committed_at > contrib["last_commit_at"]:
                contrib["last_commit_at"] = committed_at

            if len(commit_batch) >= BATCH_SIZE:
                _flush_commit_batch(session, repo_id, commit_batch)
                commit_batch.clear()

                if contributor_map:
                    _flush_contributors_batch(session, repo_id, contributor_map)
                    contributor_map.clear()

                _publish_progress(repo_id, {
                    "status": "processing",
                    "progress": min(90, 10 + (total_processed / max(total_processed + 1000, 1)) * 80),
                    "message": f"Processed {total_processed} commits...",
                    "commits_processed": total_processed,
                    "total_commits_found": total_processed,
                })

        if commit_batch:
            _flush_commit_batch(session, repo_id, commit_batch)

        # Step 4: Flush remaining contributors
        _publish_progress(repo_id, {
            "status": "processing",
            "progress": 92,
            "message": "Saving contributor data...",
            "commits_processed": total_processed,
            "total_commits_found": total_processed,
        })

        if contributor_map:
            _flush_contributors_batch(session, repo_id, contributor_map)

        # Step 5: Update repo stats
        # BUG FIX: Use DB count for accurate total_contributors instead of in-memory set
        contrib_count = session.execute(
            select(func.count(Contributor.id)).where(Contributor.repo_id == repo_id)
        ).scalar() or 0

        repo.total_commits += total_processed
        repo.total_contributors = contrib_count
        repo.last_commit_sha = last_commit_sha or repo.last_commit_sha
        repo.processing_status = "processed"
        repo.processed_at = datetime.now(timezone.utc)
        session.commit()

        _publish_progress(repo_id, {
            "status": "processed",
            "progress": 100,
            "message": f"Complete! {total_processed} commits processed.",
            "commits_processed": repo.total_commits,
            "total_commits_found": repo.total_commits,
        })

        logger.info(
            f"✅ Finished analyzing {repo.full_name}: "
            f"{total_processed} new commits, {contrib_count} total contributors"
        )

        return {
            "repo_id": repo_id,
            "commits": total_processed,
            "contributors": contrib_count,
            "status": "processed",
        }

    except Exception as exc:
        logger.exception(f"❌ Failed to analyze repo {repo_id}: {exc}")
        session.rollback()

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


# ---------------------------------------------------------------------------
# Batch flush helpers
# ---------------------------------------------------------------------------

def _flush_commit_batch(session, repo_id: int, commit_dicts: list):
    """Flush a batch of commits using ON CONFLICT DO NOTHING for idempotent inserts."""
    if not commit_dicts:
        return

    # Use pg_insert with .values() for proper batch insert + ON CONFLICT handling
    stmt = pg_insert(Commit).values(commit_dicts)
    stmt = stmt.on_conflict_do_nothing(
        constraint="uq_commit_repo_hash"
    )
    session.execute(stmt)
    session.commit()


def _flush_contributors_batch(session, repo_id: int, contributor_map: dict):
    """Flush contributors as a single batch upsert statement.

    Uses a single INSERT ... ON CONFLICT DO UPDATE with multiple rows,
    instead of N individual statements.
    """
    if not contributor_map:
        return

    contrib_values = []
    for cdata in contributor_map.values():
        contrib_values.append({
            "repo_id": repo_id,
            "name": cdata["name"],
            "email": cdata["email"],
            "total_commits": cdata["total_commits"],
            "total_additions": cdata["total_additions"],
            "total_deletions": cdata["total_deletions"],
            "first_commit_at": cdata["first_commit_at"],
            "last_commit_at": cdata["last_commit_at"],
        })

    stmt = pg_insert(Contributor).values(contrib_values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_contributor_repo_email",
        set_={
            "name": stmt.excluded.name,
            "total_commits": Contributor.total_commits + stmt.excluded.total_commits,
            "total_additions": Contributor.total_additions + stmt.excluded.total_additions,
            "total_deletions": Contributor.total_deletions + stmt.excluded.total_deletions,
            "first_commit_at": func.least(Contributor.first_commit_at, stmt.excluded.first_commit_at),
            "last_commit_at": func.greatest(Contributor.last_commit_at, stmt.excluded.last_commit_at),
        }
    )
    session.execute(stmt)
    session.commit()

"""Pydantic schemas for file related endpoints."""

from datetime import datetime
from pydantic import BaseModel


class FileTreeEntry(BaseModel):
    """Entry in a Git file tree."""
    path: str
    type: str  # "blob" or "tree"
    size: int | None = None


class FileTreeResponse(BaseModel):
    """Response for repository file tree at a commit."""
    commit_hash: str
    entries: list[FileTreeEntry]


class FileHistoryEntry(BaseModel):
    """A commit in the history of a specific file."""
    commit_hash: str
    author_name: str
    author_email: str
    date: datetime
    message: str
    path: str


class FileHistoryResponse(BaseModel):
    """Response for the commit history of a specific file."""
    path: str
    history: list[FileHistoryEntry]


class FileContentResponse(BaseModel):
    """Response containing the exact content of a file at a commit."""
    path: str
    commit_hash: str
    content: str

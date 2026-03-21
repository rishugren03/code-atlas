"""add unique constraint on commits (repo_id, commit_hash)

Revision ID: a1b2c3d4e5f6
Revises: eabad67c2013
Create Date: 2026-03-21 17:36:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'eabad67c2013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First remove any duplicate commits that may exist
    op.execute("""
        DELETE FROM file_changes
        WHERE commit_id IN (
            SELECT id FROM commits
            WHERE id NOT IN (
                SELECT MIN(id) FROM commits GROUP BY repo_id, commit_hash
            )
        )
    """)
    op.execute("""
        DELETE FROM commits
        WHERE id NOT IN (
            SELECT MIN(id) FROM commits GROUP BY repo_id, commit_hash
        )
    """)
    op.create_unique_constraint('uq_commit_repo_hash', 'commits', ['repo_id', 'commit_hash'])


def downgrade() -> None:
    op.drop_constraint('uq_commit_repo_hash', 'commits', type_='unique')

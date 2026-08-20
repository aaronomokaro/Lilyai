"""add indirect rls policies to collection_documents and document_tags via parent documents table

Revision ID: 12cbf8e72324
Revises: d56d705cc9cd
Create Date: 2026-07-29 02:07:39.583872

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '12cbf8e72324'
down_revision: Union[str, None] = 'd56d705cc9cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # collection_documents - ownership derived from parent documents table.
    # DROP IF EXISTS makes this safe on production where it was added by hand.
    op.execute("ALTER TABLE collection_documents ENABLE ROW LEVEL SECURITY")
    op.execute(
        "DROP POLICY IF EXISTS collection_documents_user_isolation ON collection_documents"
    )
    op.execute(
        """
        CREATE POLICY collection_documents_user_isolation ON collection_documents
        USING (
            document_id IN (
                SELECT id FROM documents
                WHERE (user_id)::text = current_setting('app.current_user_id', true)
            )
        );
        """
    )

    # document_tags - same indirect pattern through the documents table.
    op.execute("ALTER TABLE document_tags ENABLE ROW LEVEL SECURITY")
    op.execute(
        "DROP POLICY IF EXISTS document_tags_user_isolation ON document_tags"
    )
    op.execute(
        """
        CREATE POLICY document_tags_user_isolation ON document_tags
        USING (
            document_id IN (
                SELECT id FROM documents
                WHERE (user_id)::text = current_setting('app.current_user_id', true)
            )
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS document_tags_user_isolation ON document_tags")
    op.execute("ALTER TABLE document_tags DISABLE ROW LEVEL SECURITY")
    op.execute(
        "DROP POLICY IF EXISTS collection_documents_user_isolation ON collection_documents"
    )
    op.execute("ALTER TABLE collection_documents DISABLE ROW LEVEL SECURITY")
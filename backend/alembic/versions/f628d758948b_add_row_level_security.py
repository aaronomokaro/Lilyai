"""add row level security

Revision ID: f628d758948b
Revises: 2667369539d1
Create Date: 2026-05-22 13:22:32.672260

"""
from typing import Sequence, Union

from alembic import op

revision: str = "f628d758948b"
down_revision: Union[str, None] = "2667369539d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tables with standard user_id isolation
    tables = [
        "documents",
        "chunks",
        "conversations",
        "queries",
        "outputs",
        "integration_tokens",
        "subscriptions",
        "collections",
        "tags",
        "notifications",
        "processing_jobs",
    ]

    for table in tables:
        # Enable RLS on the table
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

        # Force RLS even for the postgres user - without this the app user
        # bypasses all policies since it connects as postgres
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

        # Create standard isolation policy - users only see their own rows
        op.execute(
            f"""
            CREATE POLICY {table}_user_isolation ON {table}
            USING (
                user_id::text = current_setting('app.current_user_id', true)
            )
        """
        )

    # Subscriptions - also accessible by organisation_id for enterprise users
    # who inherit the org subscription rather than having a personal one
    op.execute(
        """
        CREATE POLICY subscriptions_org_isolation ON subscriptions
        USING (
            user_id::text = current_setting('app.current_user_id', true)
            OR organisation_id::text = current_setting('app.current_org_id', true)
        )
    """
    )

    # Chunks - also accessible by organisation_id for org members
    # who can search across documents uploaded by any member of their org
    op.execute(
        """
        CREATE POLICY chunks_org_isolation ON chunks
        USING (
            user_id::text = current_setting('app.current_user_id', true)
            OR organisation_id::text = current_setting('app.current_org_id', true)
        )
    """
    )

    # conversation_turns has no user_id - access controlled through parent conversation
    op.execute(
        "ALTER TABLE conversation_turns ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE conversation_turns FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        CREATE POLICY conversation_turns_user_isolation ON conversation_turns
        USING (
            conversation_id IN (
                SELECT id FROM conversations
                WHERE user_id::text = current_setting('app.current_user_id', true)
            )
        )
    """
    )

    # document_access_grants - special case
    # The granter needs to see grants they created (granted_by_user_id)
    # The receiver needs to see grants made to them (granted_to_user_id)
    # Standard user_id isolation would block one or the other
    op.execute(
        "ALTER TABLE document_access_grants ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE document_access_grants FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        CREATE POLICY document_access_grants_isolation ON document_access_grants
        USING (
            granted_by_user_id::text = current_setting('app.current_user_id', true)
            OR granted_to_user_id::text = current_setting('app.current_user_id', true)
        )
    """
    )


def downgrade() -> None:
    tables = [
        "documents",
        "chunks",
        "conversations",
        "queries",
        "conversation_turns",
        "outputs",
        "integration_tokens",
        "subscriptions",
        "collections",
        "tags",
        "notifications",
        "processing_jobs",
    ]

    for table in tables:
        op.execute(f"DROP POLICY IF EXISTS {table}_user_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute(
        "DROP POLICY IF EXISTS subscriptions_org_isolation ON subscriptions"
    )
    op.execute(
        "DROP POLICY IF EXISTS chunks_org_isolation ON chunks"
    )
    op.execute(
        "DROP POLICY IF EXISTS document_access_grants_isolation ON document_access_grants"
    )
    op.execute(
        "ALTER TABLE document_access_grants DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "DROP POLICY IF EXISTS conversation_turns_user_isolation ON conversation_turns"
    )
    op.execute(
        "ALTER TABLE conversation_turns DISABLE ROW LEVEL SECURITY"
    )
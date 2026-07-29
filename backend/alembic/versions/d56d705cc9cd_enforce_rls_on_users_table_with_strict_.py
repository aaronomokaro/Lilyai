"""enforce rls on users table with strict policy and security definer login and maintenance functions

Revision ID: d56d705cc9cd
Revises: ade830f47c9e
Create Date: 2026-07-29 01:08:01.837316

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd56d705cc9cd'
down_revision: Union[str, None] = 'ade830f47c9e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. SECURITY DEFINER function for login lookup - the ONLY unfiltered
    #    read of the users table, used by get_current_user during auth bootstrap.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.get_user_by_auth0_id(p_auth0_id text)
        RETURNS SETOF users
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path TO 'public'
        AS $function$
            SELECT * FROM users WHERE auth0_id = p_auth0_id;
        $function$;
        """
    )

    # 2. SECURITY DEFINER function for scheduler maintenance - the ONLY way
    #    background jobs enumerate active users. Explicit and auditable.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.get_active_users_for_maintenance()
        RETURNS SETOF users
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path TO 'public'
        AS $function$
            SELECT * FROM users WHERE is_active = true;
        $function$;
        """
    )

    # 3. Enable RLS on users and add the strict own-row-only policy.
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS users_self_isolation ON users")
    op.execute(
        """
        CREATE POLICY users_self_isolation ON users
        USING ((id)::text = current_setting('app.current_user_id', true));
        """
    )

    # 4. Grants: the restricted app role must be able to CALL the two functions.
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.get_user_by_auth0_id(text) TO lilyai_app"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.get_active_users_for_maintenance() TO lilyai_app"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS users_self_isolation ON users")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION IF EXISTS public.get_active_users_for_maintenance()")
    op.execute("DROP FUNCTION IF EXISTS public.get_user_by_auth0_id(text)")

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
    
    # 2b. SECURITY DEFINER function to provision a new user + beta subscription
    #     atomically. The only path allowed to create accounts under the
    #     strict users-table RLS policy (auto-provisioning on first login).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.provision_user(p_auth0_id text, p_email text)
        RETURNS SETOF users
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'public'
        AS $function$
        DECLARE
            v_user_id uuid;
        BEGIN
            INSERT INTO users (
                id, auth0_id, email, account_type, token_version,
                is_active, role, created_at, updated_at
            )
            VALUES (
                gen_random_uuid(), p_auth0_id, p_email, 'individual', 1,
                true, 'user', NOW(), NOW()
            )
            RETURNING id INTO v_user_id;

            INSERT INTO subscriptions (
                id, user_id, plan, status,
                queries_per_day, queries_per_month, max_documents,
                max_pages_per_doc, max_file_size_mb, storage_limit_mb,
                created_at, updated_at
            )
            VALUES (
                gen_random_uuid(), v_user_id, 'beta', 'active',
                1000, 20000, 200,
                1000, 100, 20000,
                NOW(), NOW()
            );

            RETURN QUERY SELECT * FROM users WHERE id = v_user_id;
        END;
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

    # 4. Grants: the restricted app role must be able to CALL the functions.
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.get_user_by_auth0_id(text) TO lilyai_app"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.provision_user(text, text) TO lilyai_app"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.get_active_users_for_maintenance() TO lilyai_app"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS users_self_isolation ON users")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION IF EXISTS public.get_active_users_for_maintenance()")
    op.execute("DROP FUNCTION IF EXISTS public.get_user_by_auth0_id(text)")

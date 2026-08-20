from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


@event.listens_for(SessionLocal, "after_begin")
def _apply_rls_on_transaction_start(session, transaction, connection):
    """
    Re-apply RLS context at the start of every transaction, reading the identity
    stashed on the session itself. Transaction-local (set_config ..., true) so it
    clears at transaction end - never leaks across pooled connections - and is
    re-applied after each commit within a request.
    """
    user_id = getattr(session, "_rls_user_id", None)
    if user_id is None:
        return
    org_id = getattr(session, "_rls_org_id", None)
    connection.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(user_id)},
    )
    connection.execute(
        text("SELECT set_config('app.current_org_id', :oid, true)"),
        {"oid": str(org_id) if org_id else ""},
    )


def set_rls_context(
    db, user_id: str, organisation_id: str = None, is_local: bool = True
):
    """
    Directly set RLS session variables on a db session. Used by the worker,
    which holds one connection for a whole job. is_local=False persists across
    the worker's multiple commits.
    """
    scope = "true" if is_local else "false"
    db.execute(
        text(f"SELECT set_config('app.current_user_id', :user_id, {scope})"),
        {"user_id": str(user_id)},
    )
    if organisation_id:
        db.execute(
            text(f"SELECT set_config('app.current_org_id', :org_id, {scope})"),
            {"org_id": str(organisation_id)},
        )
    else:
        db.execute(text(f"SELECT set_config('app.current_org_id', '', {scope})"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_with_user(user_id: str, organisation_id: str = None):
    """
    Request-scoped user-aware session. Stashes the RLS identity on the session;
    the after_begin listener applies it (transaction-local) to every transaction,
    so it survives commits and never leaks across pooled connections.
    """
    db = SessionLocal()
    db._rls_user_id = str(user_id)
    db._rls_org_id = str(organisation_id) if organisation_id else None
    try:
        yield db
    finally:
        db.close()

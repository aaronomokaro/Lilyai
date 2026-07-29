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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def set_rls_context(
    db, user_id: str, organisation_id: str = None, is_local: bool = True
):
    """
    Set the RLS session variables on a db session.
    is_local=True: transaction-scoped, cleared on commit (for web requests).
    is_local=False: session-scoped, persists across commits (for the worker).
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


def get_db_with_user(user_id: str, organisation_id: str = None):
    db = SessionLocal()
    try:
        # Session-scoped (is_local=False) so the RLS context survives the
        # multiple commits that happen within a single request. Without this,
        # a commit clears transaction-local context and subsequent object
        # access fails RLS ("row not present").
        set_rls_context(
            db, user_id=user_id, organisation_id=organisation_id, is_local=False
        )
        yield db
    finally:
        # Clear the context before the connection returns to the pool, so it
        # can never leak into the next request that reuses this connection.
        try:
            db.execute(text("SELECT set_config('app.current_user_id', '', false)"))
            db.execute(text("SELECT set_config('app.current_org_id', '', false)"))
            db.commit()
        except Exception:
            pass
        db.close()

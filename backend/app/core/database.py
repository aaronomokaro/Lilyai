from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def set_rls_context(db, user_id: str, organisation_id: str = None):
    """
    Set the RLS session variables on an existing db session so row-level
    security policies apply for this user.
    """
    db.execute(
        text("SELECT set_config('app.current_user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )
    if organisation_id:
        db.execute(
            text("SELECT set_config('app.current_org_id', :org_id, true)"),
            {"org_id": str(organisation_id)},
        )
    else:
        db.execute(text("SELECT set_config('app.current_org_id', '', true)"))


def get_db_with_user(user_id: str, organisation_id: str = None):
    db = SessionLocal()
    try:
        set_rls_context(db, user_id=user_id, organisation_id=organisation_id)
        yield db
    finally:
        db.close()

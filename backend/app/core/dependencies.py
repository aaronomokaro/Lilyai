from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db, get_db_with_user
from app.core.security import verify_token
from app.models.organisation import User
from app.models.subscription import Subscription


async def get_current_user(
    payload: dict = Depends(verify_token),
    db: Session = Depends(get_db),
) -> User:
    auth0_id = payload.get("sub")

    if not auth0_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = db.query(User).filter(User.auth0_id == auth0_id).first()

    if not user:
        # Auto-provision user on first login
        email = payload.get("email", "")
        user = User(
            auth0_id=auth0_id,
            email=email,
            account_type="individual",
            token_version=1,
            is_active=True,
            role="user",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Auto-provision a subscription so new users can immediately use the platform
        # TODO: switch to real Free tier defaults once beta ends and paid tiers go live
        subscription = Subscription(
            user_id=user.id,
            plan="beta",
            status="active",
            queries_per_day=1000,
            queries_per_month=20000,
            max_documents=200,
            max_pages_per_doc=1000,
            max_file_size_mb=100,
            storage_limit_mb=20000,
        )
        db.add(subscription)
        db.commit()

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    return user


def get_rls_db(
    current_user: User = Depends(get_current_user),
):
    db_gen = get_db_with_user(
        user_id=str(current_user.id),
        organisation_id=(
            str(current_user.organisation_id) if current_user.organisation_id else None
        ),
    )
    db = next(db_gen)
    try:
        yield db
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


async def get_test_user(db: Session = Depends(get_db)) -> User:
    # TEMPORARY - remove before production
    # Creates or retrieves a test user for local development
    import uuid

    from app.models.organisation import User

    test_user = db.query(User).filter(User.email == "test@lilyai.dev").first()

    if not test_user:
        test_user = User(
            id=uuid.uuid4(),
            email="test@lilyai.dev",
            auth0_id="test|local_dev",
            is_active=True,
            role="admin",
        )
        db.add(test_user)
        db.commit()

    return test_user

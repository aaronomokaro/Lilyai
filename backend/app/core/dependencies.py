from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db, get_db_with_user
from app.core.security import verify_token
from app.models.organisation import User


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

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
        organisation_id=str(current_user.organisation_id) if current_user.organisation_id else None,
    )
    db = next(db_gen)
    try:
        yield db
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass
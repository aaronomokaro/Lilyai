"""Test that login lookup works through the SECURITY DEFINER function under strict RLS."""
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.organisation import User

def lookup(auth0_id):
    db = SessionLocal()
    try:
        # Mimics get_current_user's lookup - no context set (login bootstrap)
        return (
            db.query(User)
            .from_statement(text("SELECT * FROM get_user_by_auth0_id(:auth0_id)"))
            .params(auth0_id=auth0_id)
            .first()
        )
    finally:
        db.close()

# Existing user should be found via the function, even with no RLS context
u = lookup("test|userA")
assert u is not None, "FAIL: login lookup returned nothing - login would break"
assert str(u.id) == "11111111-1111-1111-1111-111111111111", f"FAIL: wrong user {u.id}"
print("PASS: login lookup works through the function under strict RLS ->", u.auth0_id)

# Non-existent user should return None cleanly (new user -> triggers auto-provision)
n = lookup("test|doesnotexist")
assert n is None, "FAIL: expected None for unknown user"
print("PASS: unknown user returns None (auto-provision path works)")

"""
Truthful RLS test against the throwaway DB as the restricted role.
Mimics exactly what list_documents does, per user, and asserts isolation.
"""
from app.core.database import SessionLocal, set_rls_context
from app.models.document import Document

USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"


def docs_for(user_id):
    db = SessionLocal()
    try:
        set_rls_context(db, user_id=user_id)
        # NOTE: deliberately NO app-layer user_id filter here,
        # so this tests RLS ALONE, not the app filter.
        return [d.filename for d in db.query(Document).filter(Document.is_active == True).all()]
    finally:
        db.close()


a = docs_for(USER_A)
b = docs_for(USER_B)

print("User A sees:", a)
print("User B sees:", b)

assert a == ["userA_doc.pdf"], f"FAIL: user A saw {a}"
assert b == ["userB_doc.pdf"], f"FAIL: user B saw {b}"
print("PASS: RLS isolates users with no app-layer filter present")

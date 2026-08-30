from datetime import datetime, timedelta, timezone

from app.auth.hashing import hash_password
from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.models.session import Session as SessionModel
from app.models.user import User, UserRole

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "correct horse battery staple"


def _make_user(db_session, *, email=ADMIN_EMAIL, password=ADMIN_PASSWORD, role=UserRole.admin, is_active=True):
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name="Test User",
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_login_sets_session_cookie_and_logout_invalidates_it(client, db_session):
    _make_user(db_session)

    login_resp = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert login_resp.status_code == 200
    assert SESSION_COOKIE_NAME in login_resp.cookies

    logout_resp = client.post("/api/auth/logout")
    assert logout_resp.status_code == 204

    # the old cookie must no longer authenticate a protected route
    protected_resp = client.post("/api/admin/users/1/deactivate")
    assert protected_resp.status_code == 401


def test_wrong_password_unknown_email_and_deactivated_all_return_identical_401(client, db_session):
    _make_user(db_session, is_active=True)
    _make_user(db_session, email="inactive@example.com", is_active=False)

    wrong_password = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": "not the password"})
    unknown_email = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": ADMIN_PASSWORD})
    deactivated = client.post(
        "/api/auth/login", json={"email": "inactive@example.com", "password": ADMIN_PASSWORD}
    )

    for resp in (wrong_password, unknown_email, deactivated):
        assert resp.status_code == 401

    assert wrong_password.json() == unknown_email.json() == deactivated.json()


def test_expired_session_is_rejected(client, db_session):
    user = _make_user(db_session)
    session = create_session(db_session, user.id)

    # force expiry directly in the DB rather than sleeping
    db_session.query(SessionModel).filter(SessionModel.id == session.id).update(
        {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}
    )
    db_session.commit()

    client.cookies.set(SESSION_COOKIE_NAME, session.id)
    resp = client.post("/api/admin/users/1/deactivate")
    assert resp.status_code == 401


def test_interviewer_session_hitting_admin_only_route_gets_403(client, db_session):
    # No interviewer-only route exists in this ticket (that arrives with Interviewer
    # Scoring); the admin-direction case is exercised here, the interviewer-only
    # direction gets its own test once that route exists.
    admin = _make_user(db_session, email="admin2@example.com")
    interviewer = _make_user(
        db_session, email="interviewer@example.com", password="another password", role=UserRole.interviewer
    )

    interviewer_session = create_session(db_session, interviewer.id)
    client.cookies.set(SESSION_COOKIE_NAME, interviewer_session.id)
    resp = client.post(f"/api/admin/users/{admin.id}/deactivate")
    assert resp.status_code == 403


def test_reactivate_restores_login_with_original_password(client, db_session):
    user = _make_user(db_session, is_active=False)
    admin = _make_user(db_session, email="admin3@example.com", password="admin password 2")
    admin_session = create_session(db_session, admin.id)
    client.cookies.set(SESSION_COOKIE_NAME, admin_session.id)

    reactivate_resp = client.post(f"/api/admin/users/{user.id}/reactivate")
    assert reactivate_resp.status_code == 204

    client.cookies.clear()
    login_resp = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert login_resp.status_code == 200


def test_reset_password_invalidates_old_and_accepts_new(client, db_session):
    user = _make_user(db_session)
    admin = _make_user(db_session, email="admin4@example.com", password="admin password 3")
    admin_session = create_session(db_session, admin.id)
    client.cookies.set(SESSION_COOKIE_NAME, admin_session.id)

    reset_resp = client.post(f"/api/admin/users/{user.id}/reset-password", json={"new_password": "brand new password"})
    assert reset_resp.status_code == 204

    client.cookies.clear()
    old_login = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert old_login.status_code == 401

    new_login = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": "brand new password"})
    assert new_login.status_code == 200


def test_deactivate_then_login_returns_generic_401(client, db_session):
    user = _make_user(db_session)
    admin = _make_user(db_session, email="admin5@example.com", password="admin password 4")
    admin_session = create_session(db_session, admin.id)
    client.cookies.set(SESSION_COOKIE_NAME, admin_session.id)

    deactivate_resp = client.post(f"/api/admin/users/{user.id}/deactivate")
    assert deactivate_resp.status_code == 204

    client.cookies.clear()
    login_resp = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert login_resp.status_code == 401

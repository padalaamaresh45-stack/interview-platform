from app.auth.hashing import hash_password
from app.auth.session import SESSION_COOKIE_NAME, create_session
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


def _admin_client(client, db_session, *, email=ADMIN_EMAIL, password=ADMIN_PASSWORD):
    admin = _make_user(db_session, email=email, password=password)
    session = create_session(db_session, admin.id)
    client.cookies.set(SESSION_COOKIE_NAME, session.id)
    return admin


def test_create_interviewer_account(client, db_session):
    _admin_client(client, db_session)

    resp = client.post(
        "/api/admin/users",
        json={
            "email": "interviewer@example.com",
            "password": "a real password",
            "full_name": "Ivy Interviewer",
            "role": "interviewer",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "interviewer"
    assert "password" not in body
    assert "password_hash" not in body

    created = db_session.query(User).filter(User.email == "interviewer@example.com").first()
    assert created.password_hash != "a real password"


def test_create_admin_account_via_same_endpoint(client, db_session):
    _admin_client(client, db_session)

    resp = client.post(
        "/api/admin/users",
        json={
            "email": "second-admin@example.com",
            "password": "a real password",
            "full_name": "Andi Admin",
            "role": "admin",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "admin"


def test_duplicate_email_returns_clean_400(client, db_session):
    _admin_client(client, db_session)

    payload = {
        "email": "dupe@example.com",
        "password": "a real password",
        "full_name": "First",
        "role": "interviewer",
    }
    first = client.post("/api/admin/users", json=payload)
    assert first.status_code == 201

    second = client.post("/api/admin/users", json={**payload, "full_name": "Second"})
    assert second.status_code == 400


def test_list_returns_mix_of_active_and_inactive(client, db_session):
    _admin_client(client, db_session)
    _make_user(db_session, email="active@example.com", role=UserRole.interviewer, is_active=True)
    _make_user(db_session, email="inactive@example.com", role=UserRole.interviewer, is_active=False)

    resp = client.get("/api/admin/users")
    assert resp.status_code == 200
    by_email = {row["email"]: row for row in resp.json()}
    assert by_email["active@example.com"]["is_active"] is True
    assert by_email["inactive@example.com"]["is_active"] is False
    assert "role" in by_email["active@example.com"]


def test_edit_full_name_bumps_updated_at(client, db_session):
    _admin_client(client, db_session)
    target = _make_user(db_session, email="target@example.com", role=UserRole.interviewer)
    original_updated_at = target.updated_at.isoformat()

    resp = client.patch(f"/api/admin/users/{target.id}", json={"full_name": "New Name"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["full_name"] == "New Name"
    assert body["updated_at"] != original_updated_at


def test_patch_does_not_accept_email_or_role_changes(client, db_session):
    _admin_client(client, db_session)
    target = _make_user(db_session, email="fixed@example.com", role=UserRole.interviewer)

    resp = client.patch(
        f"/api/admin/users/{target.id}",
        json={"full_name": "Still Fine", "email": "changed@example.com", "role": "admin"},
    )
    assert resp.status_code == 200
    db_session.refresh(target)
    assert target.email == "fixed@example.com"
    assert target.role == UserRole.interviewer


def test_non_admin_gets_403_on_every_route_in_this_module(client, db_session):
    admin = _admin_client(client, db_session)
    interviewer = _make_user(
        db_session, email="interviewer2@example.com", password="another password", role=UserRole.interviewer
    )
    interviewer_session = create_session(db_session, interviewer.id)
    client.cookies.set(SESSION_COOKIE_NAME, interviewer_session.id)

    assert (
        client.post(
            "/api/admin/users",
            json={"email": "x@example.com", "password": "xxxxxxxx", "full_name": "X", "role": "interviewer"},
        ).status_code
        == 403
    )
    assert client.get("/api/admin/users").status_code == 403
    assert client.patch(f"/api/admin/users/{admin.id}", json={"full_name": "X"}).status_code == 403


def test_reset_password_reachable_and_list_reflects_state_afterward(client, db_session):
    _admin_client(client, db_session)
    target = _make_user(db_session, email="resetme@example.com", role=UserRole.interviewer)

    resp = client.post(f"/api/admin/users/{target.id}/reset-password", json={"new_password": "brand new password"})
    assert resp.status_code == 204

    listing = client.get("/api/admin/users")
    by_email = {row["email"]: row for row in listing.json()}
    assert by_email["resetme@example.com"]["is_active"] is True
    assert by_email["resetme@example.com"]["role"] == "interviewer"

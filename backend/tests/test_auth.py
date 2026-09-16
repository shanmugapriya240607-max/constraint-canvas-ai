from datetime import datetime, timezone
from unittest.mock import patch

import jwt
import pytest
from sqlalchemy.orm import Session

from app.models import User
from app.services.security import hash_password, verify_password

PAYLOAD = {"name": "  Shanmu  ", "email": " User@Example.COM ", "password": "StrongPassword123"}
PUBLIC_FIELDS = {"id", "name", "email", "memory_enabled", "created_at"}


@pytest.fixture
def registered(client):
    response = client.post("/api/auth/register", json=PAYLOAD)
    assert response.status_code == 201
    return response.json()


def token_headers(client):
    response = client.post("/api/auth/login", json={
        "email": "user@example.com", "password": PAYLOAD["password"],
    })
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def assert_unauthorized(response):
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert "password_hash" not in response.text


def test_registration_and_hash_storage(client, db_engine):
    response = client.post("/api/auth/register", json=PAYLOAD)
    assert response.status_code == 201
    user = response.json()
    assert set(user) == PUBLIC_FIELDS
    assert user["name"] == "Shanmu"
    assert user["email"] == "user@example.com"
    assert user["memory_enabled"] is False
    assert user["created_at"].endswith("Z")
    assert PAYLOAD["password"] not in response.text
    with Session(db_engine) as db:
        stored = db.get(User, user["id"])
        assert stored.password_hash.startswith("$argon2id$")
        assert stored.password_hash != PAYLOAD["password"]
        assert verify_password(PAYLOAD["password"], stored.password_hash)


def test_duplicate_normalized_email(client, registered):
    response = client.post("/api/auth/register", json={**PAYLOAD, "email": "USER@example.com"})
    assert response.status_code == 409
    assert response.json()["detail"] == "An account with this email already exists"


def test_duplicate_race_is_409(client, registered):
    with patch("app.api.routes.auth.find_user", side_effect=[None, object()]):
        response = client.post("/api/auth/register", json=PAYLOAD)
    assert response.status_code == 409
    assert client.get("/api/auth/me", headers=token_headers(client)).status_code == 200


@pytest.mark.parametrize("changes", [
    {"email": "not-an-email"}, {"password": "p4ss!"}, {"name": "   "},
    {"name": "x" * 101}, {"password": "x" * 1025},
    {"password": None}, {"email": None},
])
def test_registration_validation_never_echoes_credentials(client, changes):
    payload = {**PAYLOAD, **changes}
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422
    assert "input" not in response.text
    assert "password_hash" not in response.text
    if isinstance(payload["password"], str):
        assert payload["password"] not in response.text


@pytest.mark.parametrize("missing", ["name", "email", "password"])
def test_required_fields_do_not_echo_body(client, missing):
    payload = {key: value for key, value in PAYLOAD.items() if key != missing}
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422
    assert PAYLOAD["password"] not in response.text


def test_successful_login_and_me(client, registered):
    response = client.post("/api/auth/login", json=PAYLOAD)
    assert response.status_code == 200
    token = response.json()
    assert set(token) == {"access_token", "token_type", "expires_in"}
    assert token["token_type"] == "bearer"
    assert token["expires_in"] == 3600
    assert response.headers["cache-control"] == "no-store"
    claims = jwt.decode(token["access_token"], options={"verify_signature": False})
    assert set(claims) == {"sub", "iat", "exp"}
    assert claims["sub"] == str(registered["id"])
    assert claims["exp"] - claims["iat"] == 3600
    current = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token['access_token']}"})
    assert current.status_code == 200
    assert current.json() == registered
    assert set(current.json()) == PUBLIC_FIELDS
    assert PAYLOAD["password"] not in response.text + current.text


@pytest.mark.parametrize("email,password", [
    ("user@example.com", "WrongPassword"), ("unknown@example.com", "StrongPassword123"),
    ("user@example.com", "x"),
])
def test_wrong_credentials_are_generic(client, registered, email, password):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert_unauthorized(response)
    assert response.json() == {"detail": "Invalid email or password"}


@pytest.mark.parametrize("header", [None, "Bearer invalid", "Basic credentials", "Bearer", "Bearer a.b.c"])
def test_missing_and_malformed_tokens(client, header):
    headers = {} if header is None else {"Authorization": header}
    assert_unauthorized(client.get("/api/auth/me", headers=headers))


@pytest.mark.parametrize("case", [
    "expired", "future", "missing-exp", "missing-iat", "missing-sub", "wrong-key",
    "wrong-algorithm", "unsigned", "unknown-user", "nonnumeric-sub", "integer-sub",
    "negative-sub", "huge-sub", "zero-sub", "string-iat", "null-exp", "infinite-exp",
])
def test_rejects_invalid_signed_tokens(client, application, registered, case):
    now = int(datetime.now(timezone.utc).timestamp())
    claims = {"sub": str(registered["id"]), "iat": now, "exp": now + 3600}
    # A test-only signature is generated using the app's test key, never printed.
    key = application.state.token_service._secret.get_secret_value()
    algorithm = "HS256"
    if case == "expired":
        claims.update(iat=now - 7200, exp=now - 3600)
    elif case == "future":
        claims.update(iat=now + 600, exp=now + 3600)
    elif case.startswith("missing-"):
        claims.pop(case.removeprefix("missing-"))
    elif case == "wrong-key":
        key = "independent-test-key-" * 4
    elif case == "wrong-algorithm":
        algorithm = "HS384"
    elif case == "unsigned":
        key, algorithm = "", "none"
    elif case == "unknown-user":
        claims["sub"] = "99999"
    elif case == "nonnumeric-sub":
        claims["sub"] = "user-id"
    elif case == "integer-sub":
        claims["sub"] = registered["id"]
    elif case == "negative-sub":
        claims["sub"] = "-1"
    elif case == "huge-sub":
        claims["sub"] = str(2**63)
    elif case == "zero-sub":
        claims["sub"] = "0"
    elif case == "string-iat":
        claims["iat"] = str(now)
    elif case == "null-exp":
        claims["exp"] = None
    elif case == "infinite-exp":
        claims["exp"] = float("inf")
    token = jwt.encode(claims, key, algorithm=algorithm)
    assert_unauthorized(client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}))


def test_deleted_user_token_rejected(client, registered, db_engine):
    headers = token_headers(client)
    with Session(db_engine) as db:
        db.delete(db.get(User, registered["id"]))
        db.commit()
    assert_unauthorized(client.get("/api/auth/me", headers=headers))


def test_existing_mixed_case_account(client, db_engine):
    with Session(db_engine) as db:
        db.add(User(name="Existing", email="USER@Example.com", password_hash=hash_password(PAYLOAD["password"])))
        db.commit()
    assert client.post("/api/auth/login", json=PAYLOAD).status_code == 200
    assert client.post("/api/auth/register", json=PAYLOAD).status_code == 409


def test_password_whitespace_is_preserved(client):
    payload = {**PAYLOAD, "password": "  Password123  "}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    assert client.post("/api/auth/login", json=payload).status_code == 200
    assert client.post("/api/auth/login", json={**payload, "password": "Password123"}).status_code == 401


def test_password_hashes_are_salted():
    assert hash_password(PAYLOAD["password"]) != hash_password(PAYLOAD["password"])


def test_unknown_account_performs_password_verification(client):
    with patch("app.services.security.password_hasher.verify", return_value=False) as verify:
        response = client.post("/api/auth/login", json=PAYLOAD)
    assert_unauthorized(response)
    verify.assert_called_once()


def test_invalid_stored_hash_does_not_crash(client, db_engine):
    with Session(db_engine) as db:
        db.add(User(name="Old", email="user@example.com", password_hash="old-invalid-hash"))
        db.commit()
    assert_unauthorized(client.post("/api/auth/login", json=PAYLOAD))


def test_swagger_documents_bearer_and_public_fields(client):
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert schema["paths"]["/api/auth/me"]["get"]["security"] == [{"HTTPBearer": []}]
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    assert set(schema["components"]["schemas"]["UserResponse"]["properties"]) == PUBLIC_FIELDS
    for path in ("/api/auth/register", "/api/auth/login"):
        assert "application/json" in schema["paths"][path]["post"]["requestBody"]["content"]

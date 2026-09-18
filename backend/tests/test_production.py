"""Production settings, HTTPS CORS, and durable database/auth behavior."""
import secrets
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.config import Settings
from app.main import create_app


def production(tmp_path, **overrides):
    values = dict(app_env='production', jwt_secret_key=secrets.token_urlsafe(48),
                  frontend_origins=['https://frontend.example.com'],
                  database_url=f"sqlite:///{(tmp_path / 'persistent' / 'app.db').as_posix()}")
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize('origins', [[], ['http://frontend.example.com'], ['https://localhost'], ['https://127.0.0.1']])
def test_production_rejects_nonpublic_cors(tmp_path, origins):
    with pytest.raises(ValidationError):
        production(tmp_path, frontend_origins=origins)


@pytest.mark.parametrize('url', ['sqlite://', 'sqlite:///:memory:', 'sqlite:///relative.db'])
def test_production_rejects_ephemeral_or_relative_sqlite(tmp_path, url):
    with pytest.raises(ValidationError):
        production(tmp_path, database_url=url)


def test_production_requires_explicit_database(monkeypatch, tmp_path):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    with pytest.raises(ValidationError, match='DATABASE_URL must be explicitly'):
        Settings(_env_file=None, app_env='production', jwt_secret_key=secrets.token_urlsafe(48),
                 frontend_origins=['https://frontend.example.com'])


def test_production_database_and_tokens_survive_restart(tmp_path):
    config = production(tmp_path)
    with TestClient(create_app(config)) as client:
        assert client.get('/api/health').json()['database'] == 'connected'
        allowed = client.options('/api/plans', headers={'Origin': 'https://frontend.example.com',
            'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'authorization,content-type'})
        assert allowed.status_code == 200
        assert allowed.headers['access-control-allow-origin'] == 'https://frontend.example.com'
        denied = client.options('/api/plans', headers={'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST'})
        assert denied.status_code == 400
        account = {'name': 'Production check', 'email': 'deployment@example.com', 'password': secrets.token_urlsafe(24)}
        assert client.post('/api/auth/register', json=account).status_code == 201
        login = client.post('/api/auth/login', json={key: account[key] for key in ('email', 'password')})
        assert login.status_code == 200
        token = login.json()['access_token']
    with TestClient(create_app(config)) as restarted:
        response = restarted.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
        assert response.status_code == 200
        assert response.json()['email'] == account['email']

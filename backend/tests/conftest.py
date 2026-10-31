"""Test setup: real PostgreSQL + pgvector database (TEST_DATABASE_URL), hash embeddings,
extractive answers (no LLM needed) and synchronous background jobs."""
import json
import os
import tempfile

os.environ.update(
    {
        "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://bui:bui@localhost:5432/bui_test"),
        "EMBEDDING_PROVIDER": "hash",
        "LLM_PROVIDER": "extractive",
        "RUN_JOBS_INLINE": "true",
        "REDIS_URL": "",
        "RESEARCH_SCHEDULER_ENABLED": "false",
        "UPLOAD_DIR": tempfile.mkdtemp(prefix="bui-test-uploads-"),
        "INITIAL_ADMIN_EMAIL": "root@test.local",
        "INITIAL_ADMIN_PASSWORD": "RootPassw0rd!",
        "SEARCH_PROVIDER": "none",
        "LOGIN_RATE_LIMIT_PER_MINUTE": "1000",
        "CHAT_RATE_LIMIT_PER_MINUTE": "1000",
        "SECRET_KEY": "test-secret-key-for-bui-tests-only-0123456789",
    }
)

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core import cache as cache_module  # noqa: E402
from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import Role, User  # noqa: E402
from app.research.fetcher import set_fetcher_override  # noqa: E402
from app.research.search import set_search_provider_override  # noqa: E402

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session", autouse=True)
def _migrate():
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "migrations"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _clean_db():
    with engine.begin() as conn:
        tables = [r[0] for r in conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'"))]
        conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    cache_module._cache = None
    set_search_provider_override(None)
    set_fetcher_override(None)
    yield


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


def make_user(email: str, role: str, password: str = "Passw0rdTest!") -> None:
    s = SessionLocal()
    rid = s.query(Role).filter_by(name=role).one().id
    s.add(User(email=email, full_name=email.split("@")[0].title(), password_hash=hash_password(password), role_id=rid))
    s.commit()
    s.close()


def login(client: TestClient, email: str, password: str = "Passw0rdTest!") -> dict:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def super_h(client):
    return login(client, "root@test.local", "RootPassw0rd!")


@pytest.fixture
def admin_h(client):
    make_user("admin@test.local", "admin")
    return login(client, "admin@test.local")


@pytest.fixture
def member_h(client):
    make_user("member@test.local", "team_member")
    return login(client, "member@test.local")


def sse_events(response) -> list[dict]:
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def ask(client, headers, message, **kw) -> dict:
    r = client.post("/api/chat/stream", json={"message": message, **kw}, headers=headers)
    assert r.status_code == 200, r.text
    events = sse_events(r)
    done = [e for e in events if e["type"] == "done"]
    assert done, events
    return {"events": events, **done[0], "conversation_id": events[0]["conversation_id"]}


SAMPLE_PRODUCT = {
    "name": "HydroMax 900",
    "brand": "Testco",
    "model_number": "HM-900",
    "description": "HydroMax 900 is a 1.5 HP pressure booster pump for commercial buildings.",
    "specifications": {"Motor Power": "1.5 HP", "Maximum Head": "60 m", "Voltage": "230 V AC"},
    "features": ["Stainless steel impeller", "Dry-run protection"],
    "accessories": ["Pressure switch PS-2"],
    "compatibility": ["Testco tank T-100"],
    "warranty": "HydroMax 900 carries a 30 month warranty against manufacturing defects.",
    "installation": "Mount HydroMax 900 on a concrete base and connect a 16 A dedicated circuit.",
    "troubleshooting": "If HydroMax 900 trips on startup, check the dry-run sensor wiring.",
    "status": "verified",
}


@pytest.fixture
def product(client, admin_h):
    r = client.post("/api/products", json=SAMPLE_PRODUCT, headers=admin_h)
    assert r.status_code == 201, r.text
    return r.json()

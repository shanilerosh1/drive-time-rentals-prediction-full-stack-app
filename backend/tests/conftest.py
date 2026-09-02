"""Test fixtures: an isolated database and storage directory per test."""
import io
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

# Point the settings at throwaway locations before anything imports them.
_TMP = Path(tempfile.mkdtemp(prefix="cdi-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["STORAGE_DIR"] = str(_TMP / "storage")
os.environ["PREDICTOR_BACKEND"] = "mock"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["SEED_DEMO_DATA"] = "false"
os.environ["FIRST_ADMIN_EMAIL"] = "admin@example.com"
os.environ["FIRST_ADMIN_PASSWORD"] = "AdminPass123!"

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database() -> Iterator[None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def vehicle(client: TestClient, admin_headers: dict[str, str]) -> dict:
    response = client.post(
        "/api/v1/vehicles",
        json={"registration": "CBA-1234", "make": "Toyota", "model": "Aqua", "year": 2019},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def make_image(colour: tuple[int, int, int] = (120, 130, 140), size=(320, 240)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture
def image_bytes():
    return make_image


from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.base  # Registers all SQLAlchemy models
from app.db.session import Base, get_db
from app.main import app
from app.api.deps import get_current_user


bearer_scheme = HTTPBearer()


@pytest.fixture
def client():
    # A fresh, isolated in-memory SQLite database for each test.
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
    )

    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_user(
        credentials: HTTPAuthorizationCredentials = __import__(
            "fastapi"
        ).Depends(bearer_scheme),
    ):
        # These are test-only tokens, not real application JWTs.
        test_users = {
            "customer-test-token": SimpleNamespace(
                id=100,
                name="Test Customer",
                email="customer@example.com",
                phone="9000000000",
                role="customer",
                is_active=True,
            ),
            "admin-test-token": SimpleNamespace(
                id=200,
                name="Test Admin",
                email="admin@example.com",
                phone=None,
                role="admin",
                is_active=True,
            ),
        }

        user = test_users.get(credentials.credentials)

        if user is None:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid test token",
            )

        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = (
        override_get_current_user
    )

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


@pytest.fixture
def customer_headers():
    return {"Authorization": "Bearer customer-test-token"}


@pytest.fixture
def admin_headers():
    return {"Authorization": "Bearer admin-test-token"}

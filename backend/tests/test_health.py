
from app.main import health


def test_health_payload():
    assert health() == {"status": "healthy"}

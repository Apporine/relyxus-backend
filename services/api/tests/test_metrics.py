from fastapi.testclient import TestClient

from api_test_support import make_settings
from relyxus_api.app import create_app


def test_metrics_returns_prometheus_text() -> None:
    client = TestClient(create_app(make_settings()))
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "relyxus_up 1" in response.text
    assert "relyxus_api_info" in response.text

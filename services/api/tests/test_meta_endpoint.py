from fastapi.testclient import TestClient

from api_test_support import make_settings
from relyxus_api.app import API_CONTRACT_VERSION, create_app


def test_meta_returns_contract_version() -> None:
    client = TestClient(create_app(make_settings()))
    response = client.get("/api/v1/meta")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["contract_version"] == API_CONTRACT_VERSION
    assert data["service"] == "relyxus-api"

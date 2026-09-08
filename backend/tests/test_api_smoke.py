import pytest
from fastapi.testclient import TestClient
from backend.api.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_root(client):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Welcome" in response.json()["message"]

def test_api_v1_health(client):
    """Test the /api/v1/health endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_metrics_snapshot(client):
    """Test the /api/v1/metrics/snapshot endpoint."""
    response = client.get("/api/v1/metrics/snapshot")
    assert response.status_code == 200
    data = response.json()
    assert "queries_total" in data
    assert "avg_grounding_score" in data

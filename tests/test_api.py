from fastapi.testclient import TestClient

from ai_research_stack.api import create_app


def test_health_endpoint_reports_ok():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_root_returns_operator_console():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "AI Research Stack" in response.text
    assert "Daily Budget" in response.text


def test_opportunities_endpoint_returns_list_shape():
    client = TestClient(create_app())

    response = client.get("/api/opportunities")

    assert response.status_code == 200
    assert response.json() == {"opportunities": []}

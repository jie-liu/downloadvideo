import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from unittest.mock import patch
from server import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_ping(client):
    resp = client.get("/api/ping")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}

def test_info_missing_url(client):
    resp = client.post("/api/info", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()

def test_info_calls_get_info(client):
    fake_result = {"title": "Test", "formats": []}
    with patch("routes.get_info", return_value=fake_result) as mock_fn:
        resp = client.post("/api/info", json={"url": "https://example.com"})
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Test"
    mock_fn.assert_called_once_with("https://example.com")

def test_info_get_info_error(client):
    with patch("routes.get_info", side_effect=Exception("Unsupported URL")):
        resp = client.post("/api/info", json={"url": "https://example.com"})
    assert resp.status_code == 500
    assert "error" in resp.get_json()

def test_download_missing_params(client):
    resp = client.post("/api/download", json={"url": "https://example.com"})
    assert resp.status_code == 400

def test_download_starts_task(client):
    with patch("routes.download", return_value="abc123") as mock_dl:
        resp = client.post("/api/download", json={
            "url": "https://example.com",
            "format_id": "137",
            "output_dir": "~/Downloads",
        })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["task_id"] == "abc123"
    assert data["status"] == "started"

def test_status_unknown_task(client):
    with patch("routes.get_task_status", return_value={"status": "not_found"}):
        resp = client.get("/api/status?task_id=xyz")
    assert resp.status_code == 404

def test_status_known_task(client):
    fake_status = {"status": "downloading", "progress": 42.0, "filename": "video.mp4", "error": None}
    with patch("routes.get_task_status", return_value=fake_status):
        resp = client.get("/api/status?task_id=abc123")
    assert resp.status_code == 200
    assert resp.get_json()["progress"] == 42.0

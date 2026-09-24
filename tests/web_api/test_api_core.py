"""
Tests for Core API System and Settings Endpoints.
"""

def test_api_health(api_test_env):
    """Verify system health endpoint returns 200 and expected status."""
    client = api_test_env["client"]
    res = client.get("/api/system/health")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["data"]["status"] == "healthy"
    assert data["data"]["version"] == "6.0.0"


def test_api_stats(api_test_env):
    """Verify system stats returns accurate library metrics."""
    client = api_test_env["client"]
    res = client.get("/api/system/stats")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total_songs"] >= 2
    assert data["total_movies"] >= 1
    assert data["total_artists"] >= 1


def test_api_sources(api_test_env):
    """Verify source status reporting."""
    client = api_test_env["client"]
    res = client.get("/api/system/sources")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "sources" in data["data"]


def test_api_settings_crud(api_test_env):
    """Verify settings fetch and update."""
    client = api_test_env["client"]
    # 1. Get settings
    res = client.get("/api/settings")
    assert res.status_code == 200
    data = res.json()["data"]
    assert "download" in data

    # 2. Update settings
    res_update = client.put("/api/settings", json={"max_workers": 5, "preferred_quality": 320})
    assert res_update.status_code == 200
    assert res_update.json()["success"] is True

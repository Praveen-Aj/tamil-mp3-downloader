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

    # 2. Update settings via PUT and POST with nested config (BUG-010)
    res_update = client.put("/api/settings", json={"max_workers": 5, "preferred_quality": 320})
    assert res_update.status_code == 200
    assert res_update.json()["success"] is True

    res_post_update = client.post("/api/settings", json={
        "download": {
            "download_dir": "downloads",
            "max_workers": 4,
            "preferred_quality": 320
        }
    })
    assert res_post_update.status_code == 200
    assert res_post_update.json()["success"] is True


def test_validate_path_nonexistent_does_not_create(api_test_env, tmp_path):
    """Verify validate-path rejects nonexistent directory and does NOT create it on disk (BUG-013)."""
    client = api_test_env["client"]
    phantom_dir = tmp_path / "phantom_never_created_dir_12345"
    assert not phantom_dir.exists()

    res = client.post("/api/settings/validate-path", json={"path": str(phantom_dir)})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["is_valid"] is False
    # Crucial assertion: Directory must NOT have been created on filesystem!
    assert not phantom_dir.exists()


def test_root_spa_serving(api_test_env):
    """Verify root / serves the built web single-page application."""
    client = api_test_env["client"]
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "Tamil MP3" in res.text


def test_spa_history_fallback_subroutes(api_test_env):
    """Regression test for DEFECT-02: verify direct refresh on sub-routes serves SPA index.html."""
    client = api_test_env["client"]
    subroutes = [
        "/songs",
        "/movies",
        "/artists",
        "/playlists",
        "/downloads",
        "/settings",
        "/import",
    ]
    for route in subroutes:
        res = client.get(route)
        assert res.status_code == 200, f"Route {route} failed with {res.status_code}"
        assert "text/html" in res.headers.get("content-type", "")
        assert "Tamil MP3" in res.text

    # Unmatched API routes must still return 404 JSON, NOT index.html!
    api_404 = client.get("/api/unknown_nonexistent_endpoint")
    assert api_404.status_code == 404
    assert api_404.headers.get("content-type", "").startswith("application/json")

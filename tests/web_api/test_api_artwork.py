"""
Tests for Artwork API Endpoints.
"""

def test_artwork_categories(api_test_env):
    """Verify artwork endpoint serves valid image bytes and headers for each category."""
    client = api_test_env["client"]
    m1_id = api_test_env["m1_id"]
    a1_id = api_test_env["a1_id"]
    chart_id = api_test_env["chart_id"]
    s1_id = api_test_env["s1_id"]

    for cat, ent_id in [("movie", m1_id), ("artist", a1_id), ("chart", chart_id), ("song", s1_id)]:
        res = client.get(f"/api/artwork/{cat}/{ent_id}?width=128&height=128")
        assert res.status_code == 200
        assert res.headers.get("content-type") == "image/jpeg"
        assert len(res.content) > 100
        assert "x-artwork-state" in res.headers
        assert "x-artwork-source" in res.headers
        assert "x-artwork-confidence" in res.headers


def test_artwork_invalid_category_returns_400(api_test_env):
    """Verify invalid category returns 400."""
    client = api_test_env["client"]
    res = client.get("/api/artwork/invalid_category/1")
    assert res.status_code == 400


def test_artwork_status_endpoint(api_test_env):
    """Verify artwork status endpoint returns entity resolution metadata."""
    client = api_test_env["client"]
    m1_id = api_test_env["m1_id"]

    res = client.get(f"/api/artwork/movie/{m1_id}/status")
    assert res.status_code == 200
    data = res.json()
    assert data["category"] == "movie"
    assert str(data["entity_id"]) == str(m1_id)
    assert data["state"] in ["found", "pending", "not_found", "failed"]


def test_artwork_stats_endpoint(api_test_env):
    """Verify system artwork cache statistics."""
    client = api_test_env["client"]
    res = client.get("/api/artwork/system/stats")
    assert res.status_code == 200
    stats = res.json()
    assert "memory_cache_hits" in stats
    assert "disk_cache_dir" in stats

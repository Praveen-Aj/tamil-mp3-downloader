"""
Tests for Artwork API Endpoints.
"""

def test_artwork_categories(api_test_env):
    """Verify artwork endpoint serves valid image bytes for each category."""
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


def test_artwork_invalid_category_returns_400(api_test_env):
    """Verify invalid category returns 400."""
    client = api_test_env["client"]
    res = client.get("/api/artwork/invalid_category/1")
    assert res.status_code == 400

"""
Tests for Global Search API Endpoint.
"""

def test_global_search(api_test_env):
    """Verify unified global search returns cross-entity results."""
    client = api_test_env["client"]

    # Search for "Leo"
    res = client.get("/api/search/global?q=Leo")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["movies"]) >= 1
    assert any("Leo" in m["name"] for m in data["movies"])

    # Search for "Anirudh"
    res_a = client.get("/api/search/global?q=Anirudh")
    assert res_a.status_code == 200
    data_a = res_a.json()["data"]
    assert len(data_a["artists"]) >= 1

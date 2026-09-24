"""
Tests for Artists API Endpoints.
"""

def test_list_artists(api_test_env):
    """Verify artist listing and role filtering."""
    client = api_test_env["client"]
    res = client.get("/api/artists")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] >= 1
    assert any("Anirudh" in it["name"] for it in data["items"])


def test_get_artist_details(api_test_env):
    """Verify artist details endpoint."""
    client = api_test_env["client"]
    a1_id = api_test_env["a1_id"]
    res = client.get(f"/api/artists/{a1_id}")
    assert res.status_code == 200
    data = res.json()["data"]
    assert "Anirudh" in data["artist"]["name"]
    assert len(data["songs"]) >= 1


def test_artist_download_planning(api_test_env):
    """Verify artist download planning."""
    client = api_test_env["client"]
    a1_id = api_test_env["a1_id"]
    res = client.post(f"/api/artists/{a1_id}/plan?mode=missing")
    assert res.status_code == 200
    assert "to_download" in res.json()["data"]

"""
Tests for Song Endpoints.
"""

def test_list_songs(api_test_env):
    """Verify paginated song listing and search filter."""
    client = api_test_env["client"]
    res = client.get("/api/songs")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] >= 2
    assert len(data["items"]) >= 2

    # Query filter
    res_q = client.get("/api/songs?query=Badass")
    assert res_q.status_code == 200
    data_q = res_q.json()["data"]
    assert data_q["total"] >= 1
    assert any("Badass" in it["title"] for it in data_q["items"])


def test_get_song_detail(api_test_env):
    """Verify song detail endpoint."""
    client = api_test_env["client"]
    s1_id = api_test_env["s1_id"]
    res = client.get(f"/api/songs/{s1_id}")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["song"]["title"] == "Badass"
    assert len(data["sources"]) >= 1


def test_song_rating_and_favorite(api_test_env):
    """Verify rating and favorite toggle."""
    client = api_test_env["client"]
    s1_id = api_test_env["s1_id"]

    # Rate song
    res_rate = client.post(f"/api/songs/{s1_id}/rating", json={"rating": 5})
    assert res_rate.status_code == 200
    assert res_rate.json()["data"]["rating"] == 5

    # Toggle favorite
    res_fav = client.post(f"/api/songs/{s1_id}/favorite", json={"is_favorite": True})
    assert res_fav.status_code == 200
    assert res_fav.json()["data"]["is_favorite"] is True

    # Check in favorites list - ensure "id" field is present on each item (BUG-009)
    res_favs = client.get("/api/songs/favorites")
    assert res_favs.status_code == 200
    favs_data = res_favs.json()["data"]
    assert favs_data["total"] >= 1
    assert len(favs_data["items"]) >= 1
    first_item = favs_data["items"][0]
    assert "id" in first_item
    assert first_item["id"] == s1_id


def test_download_missing_songs(api_test_env):
    """Verify download-missing endpoint returns integer queued_count (BUG-003)."""
    client = api_test_env["client"]
    res = client.post("/api/songs/download-missing", json={"preferred_quality": 320})
    assert res.status_code == 200
    data = res.json()["data"]
    assert "queued_count" in data
    assert isinstance(data["queued_count"], int)
    assert data["queued_count"] >= 0


def test_song_deletion(api_test_env):
    """Verify song deletion endpoint."""
    client = api_test_env["client"]
    s2_id = api_test_env["s2_id"]
    res = client.delete(f"/api/songs/{s2_id}?remove_from_library=true&delete_physical_file=false")
    assert res.status_code == 200
    assert res.json()["success"] is True

    # Ensure removed
    res_check = client.get(f"/api/songs/{s2_id}")
    assert res_check.status_code == 404

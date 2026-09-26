"""
Tests for Playlists API Endpoints.
"""

def test_playlist_crud_lifecycle(api_test_env):
    """Verify full playlist lifecycle: create, list, details, add item, move, delete."""
    client = api_test_env["client"]
    s2_id = api_test_env["s2_id"]

    # 1. Create Playlist
    res_create = client.post("/api/playlists", json={"name": "Workout Vibe", "description": "Upbeat tracks"})
    assert res_create.status_code == 200
    p_id = res_create.json()["data"]["id"]

    # 2. Get Details
    res_detail = client.get(f"/api/playlists/{p_id}")
    assert res_detail.status_code == 200
    detail_data = res_detail.json()["data"]
    assert detail_data["name"] == "Workout Vibe"
    assert "playlist" in detail_data
    assert "songs" in detail_data

    # 3. Add Song (via /add-song endpoint alias used by web client)
    res_add = client.post(f"/api/playlists/{p_id}/add-song", json={"song_id": s2_id})
    assert res_add.status_code == 200

    # 3b. Test playlist download endpoint returns integer queued_count
    res_dl = client.post(f"/api/playlists/{p_id}/download", json={"preferred_quality": 320})
    assert res_dl.status_code == 200
    assert isinstance(res_dl.json()["data"]["queued_count"], int)

    # 4. Remove Song (via /remove-song endpoint alias used by web client)
    res_rem = client.post(f"/api/playlists/{p_id}/remove-song", json={"song_id": s2_id})
    assert res_rem.status_code == 200

    # 5. Delete Playlist
    res_del = client.delete(f"/api/playlists/{p_id}")
    assert res_del.status_code == 200

    # 6. Verify Deleted
    res_check = client.get(f"/api/playlists/{p_id}")
    assert res_check.status_code == 404

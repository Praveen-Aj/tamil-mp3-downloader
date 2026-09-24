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
    assert res_detail.json()["data"]["name"] == "Workout Vibe"

    # 3. Add Song
    res_add = client.post(f"/api/playlists/{p_id}/items", json={"song_id": s2_id})
    assert res_add.status_code == 200

    # 4. Remove Song
    res_rem = client.delete(f"/api/playlists/{p_id}/items/{s2_id}")
    assert res_rem.status_code == 200

    # 5. Delete Playlist
    res_del = client.delete(f"/api/playlists/{p_id}")
    assert res_del.status_code == 200

    # 6. Verify Deleted
    res_check = client.get(f"/api/playlists/{p_id}")
    assert res_check.status_code == 404

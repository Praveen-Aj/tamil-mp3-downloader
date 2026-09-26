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


def test_directors_and_labels_filtered_from_artists_view(api_test_env):
    """Regression test for DEFECT-05: directors and record labels are filtered out of artists listing."""
    client = api_test_env["client"]
    service = api_test_env["service"]
    db = service.db
    from library.models import Artist

    # Add a director and a record label with 0 songs
    db.add_artist(Artist(name="Nelson Dilipkumar", role="director"))
    db.add_artist(Artist(name="Sony Music South", role="record_label"))

    # Fetch artists list
    res = client.get("/api/artists?page_size=100")
    assert res.status_code == 200
    names = [it["name"] for it in res.json()["data"]["items"]]
    assert "Nelson Dilipkumar" not in names
    assert "Sony Music South" not in names

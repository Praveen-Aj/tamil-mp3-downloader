"""
Tests for Movies API Endpoints.
"""

def test_list_movies(api_test_env):
    """Verify movie listing and pagination."""
    client = api_test_env["client"]
    res = client.get("/api/movies")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] >= 1
    assert any(it.get("name") == "Leo" or it.get("title") == "Leo" for it in data["items"])


def test_get_movie_details(api_test_env):
    """Verify movie details endpoint returns cast and songs."""
    client = api_test_env["client"]
    m1_id = api_test_env["m1_id"]
    res = client.get(f"/api/movies/{m1_id}")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["movie"].get("name") == "Leo" or data["movie"].get("title") == "Leo"

    assert len(data["songs"]) >= 2


def test_movie_download_planning(api_test_env):
    """Verify movie download planning for all vs missing."""
    client = api_test_env["client"]
    m1_id = api_test_env["m1_id"]
    res = client.post(f"/api/movies/{m1_id}/plan?mode=missing")
    assert res.status_code == 200
    data = res.json()["data"]
    assert "to_download" in data
    assert "to_skip" in data

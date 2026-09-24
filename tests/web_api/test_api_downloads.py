"""
Tests for Downloads API Endpoints.
"""

def test_downloads_listing_and_planning(api_test_env):
    """Verify download queue listing and preview planning."""
    client = api_test_env["client"]
    s2_id = api_test_env["s2_id"]

    # 1. Preview download plan for song 2
    res_plan = client.post("/api/downloads/plan", json={"song_ids": [s2_id]})
    assert res_plan.status_code == 200
    plan_data = res_plan.json()["data"]
    assert plan_data["total_requested"] == 1

    # 2. List downloads
    res_list = client.get("/api/downloads")
    assert res_list.status_code == 200
    assert isinstance(res_list.json()["data"], list)

    # 3. Pause & Resume
    res_pause = client.post("/api/downloads/pause")
    assert res_pause.status_code == 200

    res_resume = client.post("/api/downloads/resume")
    assert res_resume.status_code == 200

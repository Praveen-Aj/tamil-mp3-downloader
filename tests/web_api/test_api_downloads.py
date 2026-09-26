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

    # 3. Queue download via /queue endpoint (BUG-004)
    res_queue = client.post("/api/downloads/queue", json={"song_ids": [s2_id], "preferred_quality": 320})
    assert res_queue.status_code == 200
    queue_data = res_queue.json()["data"]
    assert isinstance(queue_data["queued_count"], int)
    assert queue_data["queued_count"] >= 0

    # 4. List active and history downloads
    res_active = client.get("/api/downloads/active")
    assert res_active.status_code == 200
    assert isinstance(res_active.json()["data"]["active"], list)

    res_history = client.get("/api/downloads/history")
    assert res_history.status_code == 200
    assert isinstance(res_history.json()["data"]["history"], list)

    # 5. Pause & Resume
    res_pause = client.post("/api/downloads/pause")
    assert res_pause.status_code == 200

    res_resume = client.post("/api/downloads/resume")
    assert res_resume.status_code == 200


def test_downloads_serialization_with_progress_event(api_test_env):
    """Regression test for DEFECT-01: active download serialization with DownloadProgressEvent."""
    client = api_test_env["client"]
    service = api_test_env["service"]
    s2_id = api_test_env["s2_id"]

    from library.service import DownloadProgressEvent
    from library.models import Download, DownloadState

    # 1. Create a download record
    dl_id = service.db.add_download(Download(
        song_id=s2_id,
        song_source_id=1,
        state=DownloadState.QUEUED,
    ))

    # 2. Inject an active DownloadProgressEvent with percent (0.55) and speed_bps (1048576.0)
    ev = DownloadProgressEvent(
        download_id=dl_id,
        song_id=s2_id,
        title="Test Track",
        status="DOWNLOADING",
        bytes_downloaded=500000,
        total_bytes=1000000,
        speed_bps=1048576.0,
        percent=0.55,
        eta_seconds=12,
    )
    with service._lock:
        service._active_progress[dl_id] = ev

    try:
        # Call GET /api/downloads - must NOT raise AttributeError or return HTTP 500
        res = client.get("/api/downloads")
        assert res.status_code == 200
        data = res.json()["data"]
        matching = [item for item in data if item["id"] == dl_id]
        assert len(matching) == 1
        item = matching[0]
        assert item["progress"] == 55.0
        assert item["speed"] == 1024.0
        assert item["eta"] == 12
        assert item["status"] == "downloading"
    finally:
        with service._lock:
            service._active_progress.pop(dl_id, None)


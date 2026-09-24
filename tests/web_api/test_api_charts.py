"""
Tests for Charts API Endpoints.
"""

def test_list_charts(api_test_env):
    """Verify chart listing."""
    client = api_test_env["client"]
    res = client.get("/api/charts")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) >= 1
    assert any(c["id"] == "tamil_top_20" or "Tamil Top 20" in c.get("name", "") for c in data)


def test_get_chart_details(api_test_env):
    """Verify chart details and entries."""
    client = api_test_env["client"]
    chart_id = api_test_env["chart_id"]
    res = client.get(f"/api/charts/{chart_id}")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["chart"]["id"] == "tamil_top_20" or "Tamil Top 20" in data["chart"].get("name", "")

    assert len(data["entries"]) >= 2


def test_chart_download_planning(api_test_env):
    """Verify chart download planning."""
    client = api_test_env["client"]
    chart_id = api_test_env["chart_id"]
    res = client.post(f"/api/charts/{chart_id}/plan?mode=missing")
    assert res.status_code == 200
    assert "to_download" in res.json()["data"]

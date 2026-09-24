"""
Tests for Audio Streaming and HTTP 206 Partial Content.
"""

def test_stream_full_content(api_test_env):
    """Verify full audio stream returns 200 and accept-ranges header."""
    client = api_test_env["client"]
    s1_id = api_test_env["s1_id"]

    res = client.get(f"/api/songs/{s1_id}/stream")
    assert res.status_code == 200
    assert res.headers.get("accept-ranges") == "bytes"
    assert "audio/" in res.headers.get("content-type")
    assert len(res.content) > 0


def test_stream_partial_content_range(api_test_env):
    """Verify HTTP 206 Partial Content range requests."""
    client = api_test_env["client"]
    s1_id = api_test_env["s1_id"]

    # Request first 100 bytes: bytes=0-99
    res = client.get(f"/api/songs/{s1_id}/stream", headers={"Range": "bytes=0-99"})
    assert res.status_code == 206
    assert res.headers.get("accept-ranges") == "bytes"
    assert "bytes 0-99/" in res.headers.get("content-range")
    assert res.headers.get("content-length") == "100"
    assert len(res.content) == 100


def test_stream_invalid_range_returns_416(api_test_env):
    """Verify out-of-range request returns 416 Range Not Satisfiable."""
    client = api_test_env["client"]
    s1_id = api_test_env["s1_id"]

    res = client.get(f"/api/songs/{s1_id}/stream", headers={"Range": "bytes=9999999-99999999"})
    assert res.status_code == 416


def test_stream_non_downloaded_returns_404(api_test_env):
    """Verify song without downloaded physical file returns 404."""
    client = api_test_env["client"]
    s2_id = api_test_env["s2_id"]

    res = client.get(f"/api/songs/{s2_id}/stream")
    assert res.status_code == 404

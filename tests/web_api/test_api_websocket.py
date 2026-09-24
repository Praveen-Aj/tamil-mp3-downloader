"""
Tests for WebSocket Live Event Endpoint.
"""

def test_websocket_connection_and_ping_pong(api_test_env):
    """Verify WebSocket connection and ping-pong message reception."""
    client = api_test_env["client"]
    with client.websocket_connect("/ws/events") as websocket:
        websocket.send_text("ping")
        response = websocket.receive_text()
        assert "pong" in response

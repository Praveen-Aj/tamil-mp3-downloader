"""
Silent Server Entry Point for Tamil MP3 Downloader.
Ensures stdout/stderr are redirected under pythonw.exe so uvicorn runs smoothly without crashing.
"""

import os
import sys

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "desktop_server.log")

    if sys.stdout is None or not hasattr(sys.stdout, "write"):
        sys.stdout = open(log_path, "a", encoding="utf-8", buffering=1)
    if sys.stderr is None or not hasattr(sys.stderr, "write"):
        sys.stderr = open(log_path, "a", encoding="utf-8", buffering=1)

    try:
        import uvicorn
        uvicorn.run("api.app:app", host="127.0.0.1", port=8765, log_level="info")
    except Exception as e:
        import traceback
        with open(os.path.join(base_dir, "run_server_crash.txt"), "w") as f:
            f.write(traceback.format_exc())

if __name__ == "__main__":
    main()

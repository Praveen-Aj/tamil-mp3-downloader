#!/usr/bin/env python3
"""Compatibility entrypoint.

Legacy CLI flow was removed to avoid conflicts with the current GUI-first app.
Running this file now starts the same GUI as gui.py.
"""

from gui import main as gui_main


def main() -> None:
    gui_main()


if __name__ == "__main__":
    main()

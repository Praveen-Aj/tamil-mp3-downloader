#!/usr/bin/env python3
"""Main Application Entry Point.

Starts the Library-centric CustomTkinter application.
"""

def main() -> None:
    from ui.app import TamilMP3App
    app = TamilMP3App()
    app.mainloop()

if __name__ == "__main__":
    main()

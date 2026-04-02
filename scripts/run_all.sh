#!/usr/bin/env bash
# Run tests and lint quickly
python -m pip install -r requirements.txt
pytest -q
python -m py_compile main.py scrapers/isaimini.py scrapers/masstamilan.py downloaders/http_downloader.py

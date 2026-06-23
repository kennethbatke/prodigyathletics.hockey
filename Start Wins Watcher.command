#!/bin/bash
cd "$(dirname "$0")"
echo "Prodigy Results Watcher running..."
echo "Drop any screenshot into your Wins folder and it will appear on the site automatically."
echo "Press Ctrl+C to stop."
echo ""
python3 scripts/wins_watcher.py

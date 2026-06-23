#!/usr/bin/env python3
"""
Prodigy Results Watcher
Watches the Wins folders and auto-updates results.html when new files are dropped.
Install: pip3 install watchdog
"""
import os
import re
import json
import time
import shutil
import subprocess
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [wins_watcher] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("wins_watcher")

WINS_DIR     = Path("/Users/kenny/Documents/Prodigy Resources/Wins")
PARENT_WINS  = WINS_DIR / "Parent Wins"
PLAYER_WINS  = WINS_DIR / "Player Wins"

REPO_DIR          = Path("/Users/kenny/Documents/Claude/prodigyathletics-site")
REPO_PARENT_IMGS  = REPO_DIR / "images/wins/parents"
REPO_PLAYER_IMGS  = REPO_DIR / "images/wins/players"
MANIFEST_PATH     = REPO_DIR / "images/wins/manifest.json"
RESULTS_HTML      = REPO_DIR / "results/index.html"

IMAGE_EXTENSIONS  = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# Single mixed grid markers
WINS_START = "<!-- WINS_START -->"
WINS_END   = "<!-- WINS_END -->"


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text())
    return {"entries": []}


def save_manifest(manifest: dict):
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))


def display_name_from_filename(stem: str) -> str:
    return re.sub(r"\s+Win\s+\d+$", "", stem, flags=re.IGNORECASE).strip()


def win_card_html(entry: dict) -> str:
    return (
        f'      <div class="win-card" data-category="{entry["category"]}">\n'
        f'        <img src="{entry["web_path"]}" alt="Client win" loading="lazy">\n'
        f'      </div>'
    )


def rebuild_results_html(manifest: dict):
    html = RESULTS_HTML.read_text()

    all_cards = "\n\n".join(win_card_html(e) for e in manifest["entries"])

    s = html.find(WINS_START)
    e = html.find(WINS_END)
    if s == -1 or e == -1:
        logger.warning("WINS_START/END markers not found in results/index.html")
        return
    html = html[:s + len(WINS_START)] + "\n\n" + all_cards + "\n\n" + html[e:]
    RESULTS_HTML.write_text(html)
    logger.info("results/index.html rebuilt")


def git_push(label: str):
    try:
        subprocess.run(["git", "add", "-A"], cwd=REPO_DIR, check=True, capture_output=True)
        result = subprocess.run(
            ["git", "commit", "-m", f"Add win: {label}"],
            cwd=REPO_DIR, capture_output=True, text=True
        )
        if "nothing to commit" in result.stdout:
            logger.info("Nothing new to commit")
            return
        subprocess.run(["git", "push"], cwd=REPO_DIR, check=True, capture_output=True)
        logger.info(f"Pushed: {label}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Git error: {e}")


def process_new_file(src: Path, category: str):
    if src.suffix.lower() not in IMAGE_EXTENSIONS:
        return
    if src.name.startswith("."):
        return

    dest_dir = REPO_PARENT_IMGS if category == "parent" else REPO_PLAYER_IMGS
    dest = dest_dir / src.name

    shutil.copy2(src, dest)
    logger.info(f"Copied {src.name} → repo ({category})")

    web_path = f"/images/wins/{'parents' if category == 'parent' else 'players'}/{src.name}"
    name = display_name_from_filename(src.stem)

    manifest = load_manifest()
    manifest["entries"] = [e for e in manifest["entries"] if e["filename"] != src.name]
    manifest["entries"].insert(0, {
        "filename": src.name,
        "name": name,
        "category": category,
        "web_path": web_path,
        "added_at": time.time(),
    })
    save_manifest(manifest)
    rebuild_results_html(manifest)
    git_push(src.name)


class WinsHandler(FileSystemEventHandler):
    def __init__(self, category: str):
        self.category = category
        self._pending: dict[str, float] = {}

    def on_created(self, event):
        if not event.is_directory:
            self._pending[event.src_path] = time.time()

    def on_moved(self, event):
        if not event.is_directory:
            self._pending[event.dest_path] = time.time()

    def flush_pending(self):
        now = time.time()
        ready = [p for p, t in list(self._pending.items()) if now - t > 2.0]
        for p in ready:
            del self._pending[p]
            process_new_file(Path(p), self.category)


def main():
    logger.info("Prodigy Results Watcher started")
    logger.info(f"  Parent Wins: {PARENT_WINS}")
    logger.info(f"  Player Wins: {PLAYER_WINS}")
    logger.info(f"  Repo:        {REPO_DIR}")

    parent_h = WinsHandler("parent")
    player_h = WinsHandler("player")

    observer = Observer()
    observer.schedule(parent_h, str(PARENT_WINS), recursive=False)
    observer.schedule(player_h, str(PLAYER_WINS), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
            parent_h.flush_pending()
            player_h.flush_pending()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Static site generator: data/ + templates/ -> public/"""

import io
import math
import json
import random
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from PIL import Image

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
TEMPLATES_DIR = ROOT / "templates"
PUBLIC_DIR = ROOT / "public"
THUMB_CACHE = ROOT / ".thumbnails"
PAGE_SIZE = 20


def youtube_video_id(url: str) -> str | None:
    m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def git_date_added(path: Path) -> str:
    """ISO date of first git commit for this file, empty string if untracked."""
    result = subprocess.run(
        ["git", "log", "--follow", "--format=%aI", "--", str(path.relative_to(ROOT))],
        capture_output=True, text=True, cwd=ROOT,
    )
    lines = result.stdout.strip().splitlines()
    return lines[-1] if lines else ""


def fetch_thumbnail(video_id: str) -> Path | None:
    THUMB_CACHE.mkdir(exist_ok=True)
    dest = THUMB_CACHE / f"{video_id}.webp"
    if dest.exists():
        return dest
    for quality in ("maxresdefault", "hqdefault"):
        url = f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
        try:
            data = urllib.request.urlopen(url).read()
            img = Image.open(io.BytesIO(data))
            w, h = img.size
            img = img.resize((400, int(h * 400 / w)), Image.LANCZOS)
            img.save(dest, "webp", quality=75)
            print(f"  thumbnail: {video_id}")
            return dest
        except urllib.error.HTTPError:
            continue
    return None


def load_lectures() -> list[dict]:
    lectures = []
    for path in sorted(DATA_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        data["slug"] = path.stem
        urls = data.get("urls", [])
        data["video_id"] = youtube_video_id(urls[0]) if urls else None
        data["date_added"] = git_date_added(path)
        lectures.append(data)
    return lectures


def page_url(mode: str, page: int) -> str:
    """Root-relative URL for a given mode + page number."""
    if page == 1:
        return f"lectures/{mode}/"
    return f"lectures/{mode}/{page}.html"


def build_paginated(tpl, lectures: list[dict], mode: str, mode_dir: Path, root: str):
    total_pages = max(1, math.ceil(len(lectures) / PAGE_SIZE))
    mode_dir.mkdir()
    for page in range(1, total_pages + 1):
        slice_ = lectures[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
        ctx = {
            "root": root,
            "lectures": slice_,
            "page": page,
            "total_pages": total_pages,
            "mode": mode,
            "prev_url": None if page == 1 else page_url(mode, page - 1),
            "next_url": None if page == total_pages else page_url(mode, page + 1),
            "mode_urls": {
                "random": "lectures/random/",
                "alpha":  "lectures/alpha/",
                "recent": "lectures/recent/",
            },
        }
        filename = "index.html" if page == 1 else f"{page}.html"
        (mode_dir / filename).write_text(tpl.render(**ctx))
    return total_pages


def build():
    if PUBLIC_DIR.exists():
        shutil.rmtree(PUBLIC_DIR)
    PUBLIC_DIR.mkdir()

    shutil.copy(TEMPLATES_DIR / "styles.css", PUBLIC_DIR / "styles.css")

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    lectures = load_lectures()

    # Thumbnails
    thumbs_dir = PUBLIC_DIR / "thumbnails"
    thumbs_dir.mkdir()
    placeholder = ROOT / "misc" / "placeholder.webp"
    shutil.copy(placeholder, thumbs_dir / "placeholder.webp")
    for lecture in lectures:
        vid = lecture["video_id"]
        cached = fetch_thumbnail(vid) if vid else None
        if cached:
            shutil.copy(cached, thumbs_dir / cached.name)
            lecture["thumbnail"] = f"thumbnails/{cached.name}"
        else:
            lecture["thumbnail"] = "thumbnails/placeholder.webp"

    # Three orderings
    random_order = random.sample(lectures, len(lectures))
    alpha_order   = sorted(lectures, key=lambda l: l["title"].lower())
    recent_order  = sorted(lectures, key=lambda l: l["date_added"], reverse=True)

    # Landing page
    tpl = env.get_template("index.html.jinja2")
    (PUBLIC_DIR / "index.html").write_text(tpl.render(root=""))

    # Search page
    search_dir = PUBLIC_DIR / "search"
    search_dir.mkdir()
    tpl = env.get_template("search.html.jinja2")
    (search_dir / "index.html").write_text(tpl.render(root="../"))

    # Paginated lists
    lectures_dir = PUBLIC_DIR / "lectures"
    lectures_dir.mkdir()
    list_tpl = env.get_template("lectures_list.html.jinja2")
    for mode, ordered in [("random", random_order), ("alpha", alpha_order), ("recent", recent_order)]:
        pages = build_paginated(list_tpl, ordered, mode, lectures_dir / mode, root="../../")
        print(f"  {mode}: {pages} page(s)")

    # Per-lecture pages
    view_tpl = env.get_template("lectures_view.html.jinja2")
    for lecture in lectures:
        (lectures_dir / f"{lecture['slug']}.html").write_text(view_tpl.render(lecture=lecture, root="../"))

    print(f"Built {len(lectures)} lectures -> {PUBLIC_DIR}")

    result = subprocess.run(["npx", "pagefind", "--site", str(PUBLIC_DIR)], capture_output=True, text=True)
    if result.returncode == 0:
        print("Pagefind index built.")
    else:
        print(f"Pagefind failed (is npx available?):\n{result.stderr}")


if __name__ == "__main__":
    build()

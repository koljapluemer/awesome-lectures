#!/usr/bin/env python3
"""Static site generator: data/ + templates/ -> public/"""

import colorsys
import hashlib
import io
import math
import json
import os
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


def _hue_from_str(s: str) -> str:
    """Deterministic HSV colour (fixed S=0.72, V=0.85) from a string key."""
    h = int(hashlib.md5(s.encode()).hexdigest(), 16) % 360 / 360
    r, g, b = colorsys.hsv_to_rgb(h, 0.72, 0.85)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def _mix_white(color_hex: str, t: float) -> str:
    """Interpolate between white (t=0) and color_hex (t=1)."""
    r = int(color_hex[1:3], 16)
    g = int(color_hex[3:5], 16)
    b = int(color_hex[5:7], 16)
    return f"#{int(255 + (r - 255) * t):02x}{int(255 + (g - 255) * t):02x}{int(255 + (b - 255) * t):02x}"


def _sorted_learnings(learnings: list) -> list:
    """Flatten the learnings list-of-dicts and sort by Bayesian rating (desc).

    The stored rating is already the Bayesian mean (prior baked in), so no
    further adjustment is needed — higher rating = higher confidence-adjusted score.
    """
    items = []
    for block in learnings:
        for key, val in block.items():
            items.append({"key": key, **val})
    items.sort(key=lambda x: x["rating"], reverse=True)
    return items
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


def check_oembed(video_id: str) -> bool:
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        urllib.request.urlopen(url)
        return True
    except urllib.error.HTTPError:
        return False


def load_lectures() -> list[dict]:
    lectures = []
    for path in sorted(DATA_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        urls = data.get("urls", [])
        video_id = youtube_video_id(urls[0]) if urls else None

        # Check embeddability once; write result back to JSON as cache
        if video_id and "embed" not in data:
            data["embed"] = check_oembed(video_id)
            print(f"  embed check {path.stem}: {data['embed']}")
            path.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n")

        # Normalise tags/topics: {name: count} → [name] filtered to count > 0
        for field in ("topics", "tags"):
            raw = data.get(field)
            if isinstance(raw, dict):
                data[field] = [k for k, v in raw.items() if v > 0]
            elif raw is None:
                data[field] = []

        data["slug"] = path.stem
        data["video_id"] = video_id
        data["date_added"] = git_date_added(path)
        lectures.append(data)
    return lectures


def page_url(mode: str, page: int) -> str:
    """Root-relative URL for a given mode + page number."""
    if page == 1:
        return f"lectures/{mode}/"
    return f"lectures/{mode}/{page}.html"


def build_paginated(tpl, lectures: list[dict], mode: str, mode_dir: Path, root: str, **extra):
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
            **extra,
        }
        filename = "index.html" if page == 1 else f"{page}.html"
        (mode_dir / filename).write_text(tpl.render(**ctx))
    return total_pages


def build():
    if PUBLIC_DIR.exists():
        shutil.rmtree(PUBLIC_DIR)
    PUBLIC_DIR.mkdir()

    shutil.copy(TEMPLATES_DIR / "styles.css", PUBLIC_DIR / "styles.css")
    shutil.copy(TEMPLATES_DIR / "lectures_view.js", PUBLIC_DIR / "lectures_view.js")
    shutil.copy(ROOT / "misc" / "favicon.ico", PUBLIC_DIR / "favicon.ico")
    shutil.copy(ROOT / "misc" / "logo.png", PUBLIC_DIR / "logo.png")

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    env.filters["hue_from_str"] = _hue_from_str
    env.filters["mix_white"] = _mix_white
    env.filters["sorted_learnings"] = _sorted_learnings
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

    staticforms_key = os.environ.get("STATICFORMS_KEY", "YOUR_KEY_HERE")
    site_url = os.environ.get("SITE_URL", "http://localhost:8000/")
    if not site_url.endswith("/"):
        site_url += "/"
    # API_BASE controls frontend API calls:
    #   unset      → None  → API calls disabled (local preview without backend)
    #   ""         → ""    → relative /api/... calls (production via Netlify proxy)
    #   "http://localhost:5000" → that URL (local dev with backend running)
    api_base_env = os.environ.get("API_BASE")
    api_base = api_base_env.rstrip("/") if api_base_env is not None else None

    common = {"api_base": api_base}

    # Landing page
    tpl = env.get_template("index.html.jinja2")
    (PUBLIC_DIR / "index.html").write_text(tpl.render(root="", **common))

    # Search page
    search_dir = PUBLIC_DIR / "search"
    search_dir.mkdir()
    tpl = env.get_template("search.html.jinja2")
    (search_dir / "index.html").write_text(tpl.render(root="../", **common))

    # About page
    about_dir = PUBLIC_DIR / "about"
    about_dir.mkdir()
    tpl = env.get_template("about.html.jinja2")
    (about_dir / "index.html").write_text(tpl.render(root="../", **common))

    # Submit page + thanks
    submit_dir = PUBLIC_DIR / "submit"
    submit_dir.mkdir()
    tpl = env.get_template("submit.html.jinja2")
    (submit_dir / "index.html").write_text(tpl.render(root="../", staticforms_key=staticforms_key, site_url=site_url, **common))
    thanks_dir = submit_dir / "thanks"
    thanks_dir.mkdir()
    tpl = env.get_template("submit_thanks.html.jinja2")
    (thanks_dir / "index.html").write_text(tpl.render(root="../../", **common))

    # Paginated lists
    lectures_dir = PUBLIC_DIR / "lectures"
    lectures_dir.mkdir()
    list_tpl = env.get_template("lectures_list.html.jinja2")
    for mode, ordered in [("random", random_order), ("alpha", alpha_order), ("recent", recent_order)]:
        pages = build_paginated(list_tpl, ordered, mode, lectures_dir / mode, root="../../", **common)
        print(f"  {mode}: {pages} page(s)")

    # Per-lecture pages
    view_tpl = env.get_template("lectures_view.html.jinja2")
    for lecture in lectures:
        (lectures_dir / f"{lecture['slug']}.html").write_text(view_tpl.render(lecture=lecture, root="../", **common))

    print(f"Built {len(lectures)} lectures -> {PUBLIC_DIR}")

    result = subprocess.run(["npx", "--yes", "pagefind", "--site", str(PUBLIC_DIR)])
    if result.returncode != 0:
        print("Pagefind failed (is npx available?)")


if __name__ == "__main__":
    build()

#!/usr/bin/env python3
"""Static site generator: data/ + templates/ -> public/"""

import io
import json
import re
import shutil
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


def youtube_video_id(url: str) -> str | None:
    m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


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
        lectures.append(data)
    return lectures


def lecture_index_entry(lecture: dict) -> dict:
    """Minimal record for lectures.json — only what the filter UI needs."""
    learning_keys = [
        key
        for item in lecture.get("learnings") or []
        for key in item.keys()
    ]
    return {
        "slug": lecture["slug"],
        "title": lecture["title"],
        "speakers": lecture.get("speakers") or [],
        "topics": (lecture.get("topics") or []) + (lecture.get("tags") or []),
        "learnings": learning_keys,
        "thumbnail": lecture.get("thumbnail"),
    }


def build():
    if PUBLIC_DIR.exists():
        shutil.rmtree(PUBLIC_DIR)
    PUBLIC_DIR.mkdir()

    shutil.copy(TEMPLATES_DIR / "styles.css", PUBLIC_DIR / "styles.css")

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    lectures = load_lectures()

    # Fetch thumbnails and copy to public/; store root-relative path
    thumbs_dir = PUBLIC_DIR / "thumbnails"
    thumbs_dir.mkdir()
    for lecture in lectures:
        vid = lecture["video_id"]
        if vid:
            cached = fetch_thumbnail(vid)
            if cached:
                shutil.copy(cached, thumbs_dir / cached.name)
                lecture["thumbnail"] = f"thumbnails/{cached.name}"
            else:
                lecture["thumbnail"] = None
        else:
            lecture["thumbnail"] = None

    # lectures.json — consumed by the filter UI
    index = [lecture_index_entry(l) for l in lectures]
    (PUBLIC_DIR / "lectures.json").write_text(json.dumps(index, ensure_ascii=False))

    # Landing page
    tpl = env.get_template("index.html.jinja2")
    (PUBLIC_DIR / "index.html").write_text(tpl.render())

    # Lectures list (now a static shell; data comes from lectures.json)
    lectures_dir = PUBLIC_DIR / "lectures"
    lectures_dir.mkdir()
    tpl = env.get_template("lectures_list.html.jinja2")
    (lectures_dir / "index.html").write_text(tpl.render())

    # Per-lecture pages (still fully rendered for pagefind indexing)
    tpl = env.get_template("lectures_view.html.jinja2")
    for lecture in lectures:
        # Fix thumbnail path to be relative from lectures/
        if lecture.get("thumbnail"):
            lecture["thumbnail"] = f"../{lecture['thumbnail']}"
        (lectures_dir / f"{lecture['slug']}.html").write_text(tpl.render(lecture=lecture))

    print(f"Built {len(lectures)} lectures -> {PUBLIC_DIR}")


if __name__ == "__main__":
    build()

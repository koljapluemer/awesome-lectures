#!/usr/bin/env python3
"""Static site generator: data/ + templates/ -> public/"""

import json
import re
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
TEMPLATES_DIR = ROOT / "templates"
PUBLIC_DIR = ROOT / "public"


def youtube_video_id(url: str) -> str | None:
    m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def load_lectures() -> list[dict]:
    lectures = []
    for path in sorted(DATA_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        data["slug"] = path.stem
        urls = data.get("urls", [])
        data["video_id"] = youtube_video_id(urls[0]) if urls else None
        lectures.append(data)
    return lectures


def build():
    PUBLIC_DIR.mkdir(exist_ok=True)

    # Copy stylesheet
    shutil.copy(TEMPLATES_DIR / "styles.css", PUBLIC_DIR / "styles.css")

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    lectures = load_lectures()

    # Index page
    tpl = env.get_template("lectures_list.html.jinja2")
    (PUBLIC_DIR / "index.html").write_text(tpl.render(lectures=lectures))

    # Per-lecture pages
    tpl = env.get_template("lectures_view.html.jinja2")
    for lecture in lectures:
        out_dir = PUBLIC_DIR / lecture["slug"]
        out_dir.mkdir(exist_ok=True)
        (out_dir / "index.html").write_text(tpl.render(lecture=lecture))

    print(f"Built {len(lectures)} lectures -> {PUBLIC_DIR}")


if __name__ == "__main__":
    build()

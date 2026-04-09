import json

from flask import Blueprint, g, jsonify, request
from db import get_db
from limiter import limiter

bp = Blueprint("suggestions", __name__, url_prefix="/api/suggestions")


@bp.post("/lectures")
@limiter.limit("100 per day")
def suggest_lecture():
    if not g.fingerprint:
        return jsonify({"error": "missing fingerprint"}), 400
    data = request.get_json(silent=True) or {}
    if data.get("hp"):
        return jsonify({"status": "ok"}), 201
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url required"}), 400

    extra_fields = {k: v for k, v in data.items() if k not in ("url", "title")}
    db = get_db()
    db.execute(
        "INSERT INTO lecture_suggestions (fingerprint_id, url, title, note, data) VALUES (?, ?, ?, ?, ?)",
        (g.fingerprint, url, data.get("title"), data.get("extra"), json.dumps(extra_fields) if extra_fields else None),
    )
    db.commit()
    return jsonify({"status": "ok"}), 201


@bp.post("/learnings/<slug>")
@limiter.limit("200 per hour")
def suggest_learning(slug):
    """Suggest a new learning outcome."""
    if not g.fingerprint:
        return jsonify({"error": "missing fingerprint"}), 400
    data = request.get_json(silent=True) or {}
    if data.get("hp"):
        return jsonify({"status": "ok"}), 201
    learning = (data.get("learning") or "").strip()
    if not learning:
        return jsonify({"error": "learning required"}), 400

    db = get_db()
    db.execute(
        "INSERT INTO learning_suggestions (fingerprint_id, slug, learning) VALUES (?, ?, ?)",
        (g.fingerprint, slug, learning),
    )
    db.commit()
    return jsonify({"status": "ok"}), 201


@bp.post("/topics/<slug>")
@limiter.limit("200 per hour")
def suggest_topic(slug):
    """Single tag addition."""
    if not g.fingerprint:
        return jsonify({"error": "missing fingerprint"}), 400
    data = request.get_json(silent=True) or {}
    if data.get("hp"):
        return jsonify({"status": "ok"}), 201
    topic = (data.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "topic required"}), 400

    db = get_db()
    db.execute(
        "INSERT INTO topic_suggestions (fingerprint_id, slug, topic, action) VALUES (?, ?, ?, 'add')",
        (g.fingerprint, slug, topic),
    )
    db.commit()
    return jsonify({"status": "ok"}), 201


@bp.post("/tags/<slug>")
@limiter.limit("200 per hour")
def suggest_tags(slug):
    """Batch tag additions and/or removals."""
    if not g.fingerprint:
        return jsonify({"error": "missing fingerprint"}), 400
    data = request.get_json(silent=True) or {}
    if data.get("hp"):
        return jsonify({"status": "ok"}), 201
    add    = [t.strip() for t in data.get("add",    []) if str(t).strip()]
    remove = [t.strip() for t in data.get("remove", []) if str(t).strip()]
    if not add and not remove:
        return jsonify({"error": "nothing to do"}), 400

    db = get_db()
    db.executemany(
        "INSERT INTO topic_suggestions (fingerprint_id, slug, topic, action) VALUES (?, ?, ?, ?)",
        [(g.fingerprint, slug, t, action) for action, tags in (("add", add), ("remove", remove)) for t in tags],
    )
    db.commit()
    return jsonify({"status": "ok"}), 201

from flask import Blueprint, g, jsonify, request
from db import get_db

bp = Blueprint("suggestions", __name__, url_prefix="/api/suggestions")


@bp.post("/lectures")
def suggest_lecture():
    if not g.fingerprint:
        return jsonify({"error": "missing fingerprint"}), 400
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url required"}), 400

    db = get_db()
    db.execute(
        "INSERT INTO lecture_suggestions (fingerprint_id, url, title, note) VALUES (?, ?, ?, ?)",
        (g.fingerprint, url, data.get("title"), data.get("note")),
    )
    db.commit()
    return jsonify({"status": "ok"}), 201


@bp.post("/topics/<slug>")
def suggest_topic(slug):
    if not g.fingerprint:
        return jsonify({"error": "missing fingerprint"}), 400
    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "topic required"}), 400

    db = get_db()
    db.execute(
        "INSERT INTO topic_suggestions (fingerprint_id, slug, topic) VALUES (?, ?, ?)",
        (g.fingerprint, slug, topic),
    )
    db.commit()
    return jsonify({"status": "ok"}), 201

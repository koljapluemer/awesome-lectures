from flask import Blueprint, g, jsonify, request
from db import get_db

bp = Blueprint("ratings", __name__, url_prefix="/api/ratings")


@bp.post("/<slug>")
def vote(slug):
    if not g.fingerprint:
        return jsonify({"error": "missing fingerprint"}), 400
    data = request.get_json(silent=True) or {}
    field = (data.get("field") or "").strip()
    if not field:
        return jsonify({"error": "field required"}), 400
    try:
        value = float(data.get("value"))
        if not (0 <= value <= 10):
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "value must be a number between 0 and 10"}), 400

    db = get_db()
    db.execute(
        "INSERT INTO rating_votes (fingerprint_id, slug, field, value) VALUES (?, ?, ?, ?)",
        (g.fingerprint, slug, field, value),
    )
    db.commit()
    return jsonify({"status": "ok"}), 201

import sqlite3
from datetime import date
from flask import Blueprint, g, jsonify
from db import get_db

bp = Blueprint("interactions", __name__, url_prefix="/api/interactions")


@bp.get("/<slug>")
def get_counts(slug):
    db = get_db()
    row = db.execute(
        "SELECT COALESCE(SUM(likes), 0) AS likes FROM interaction_counts WHERE slug = ?",
        (slug,),
    ).fetchone()
    return jsonify({"slug": slug, "likes": row["likes"]})


@bp.post("/<slug>/like")
def like(slug):
    if not g.fingerprint:
        return jsonify({"error": "missing fingerprint"}), 400
    db = get_db()
    today = date.today().isoformat()
    fp = g.fingerprint

    def _like_count():
        row = db.execute(
            "SELECT COALESCE(SUM(likes), 0) AS total FROM interaction_counts WHERE slug = ?",
            (slug,),
        ).fetchone()
        return jsonify({"slug": slug, "like": row["total"]})

    try:
        db.execute(
            "INSERT INTO votes (fingerprint_id, slug, action, date) VALUES (?, ?, 'like', ?)",
            (fp, slug, today),
        )
    except sqlite3.IntegrityError:
        return _like_count()

    db.execute(
        """INSERT INTO interaction_counts (slug, date, likes) VALUES (?, ?, 1)
           ON CONFLICT(slug, date) DO UPDATE SET likes = likes + 1""",
        (slug, today),
    )
    db.commit()
    return _like_count()

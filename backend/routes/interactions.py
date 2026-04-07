import sqlite3
from datetime import date
from flask import Blueprint, g, jsonify
from db import get_db

bp = Blueprint("interactions", __name__, url_prefix="/api/interactions")


@bp.get("/<slug>")
def get_counts(slug):
    db = get_db()
    row = db.execute(
        """SELECT COALESCE(SUM(likes), 0) AS likes,
                  COALESCE(SUM(seen),  0) AS seen
           FROM interaction_counts WHERE slug = ?""",
        (slug,),
    ).fetchone()
    return jsonify({"slug": slug, "likes": row["likes"], "seen": row["seen"]})


@bp.post("/<slug>/like")
def like(slug):
    return _interact(slug, "like")


@bp.post("/<slug>/seen")
def mark_seen(slug):
    return _interact(slug, "seen")


def _interact(slug: str, action: str):
    if not g.fingerprint:
        return jsonify({"error": "missing fingerprint"}), 400
    db = get_db()
    today = date.today().isoformat()
    fp = g.fingerprint

    try:
        db.execute(
            "INSERT INTO votes (fingerprint_id, slug, action, date) VALUES (?, ?, ?, ?)",
            (fp, slug, action, today),
        )
    except sqlite3.IntegrityError:
        # Already voted today — idempotent, return current count without error
        return _counts_response(db, slug, action)

    col = "likes" if action == "like" else "seen"
    db.execute(
        f"""INSERT INTO interaction_counts (slug, date, {col}) VALUES (?, ?, 1)
            ON CONFLICT(slug, date) DO UPDATE SET {col} = {col} + 1""",
        (slug, today),
    )
    db.commit()
    return _counts_response(db, slug, action)


def _counts_response(db, slug: str, action: str):
    col = "likes" if action == "like" else "seen"
    row = db.execute(
        f"SELECT COALESCE(SUM({col}), 0) AS total FROM interaction_counts WHERE slug = ?",
        (slug,),
    ).fetchone()
    return jsonify({"slug": slug, action: row["total"]})

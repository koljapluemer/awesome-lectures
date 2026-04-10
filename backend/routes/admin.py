import json
import secrets
from functools import wraps

import requests as http
from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

import github_api
from db import get_db

bp = Blueprint("admin", __name__, url_prefix="/admin")

KNOWN_SCALE_FIELDS = {
    "audioQuality",
    "videoQuality",
    "beginnerExpertSpectrum",
    "worthListeningToWithoutVideo",
}

FIELD_LABELS = {
    "audioQuality": "Audio Quality",
    "videoQuality": "Video Quality",
    "beginnerExpertSpectrum": "Beginner → Expert Spectrum",
    "worthListeningToWithoutVideo": "Worth Without Video",
}


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def require_moderator(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        username = session.get("github_username")
        if not username:
            return redirect(url_for("admin.login"))
        if username not in current_app.config["ALLOWED_MODERATORS"]:
            return render_template("admin_unauthorized.html", username=username), 403
        return f(*args, **kwargs)
    return decorated


def _gh_token() -> str:
    return session["github_token"]

def _gh_repo() -> str:
    return current_app.config["GITHUB_REPO"]

def _gh_branch() -> str:
    return current_app.config["GITHUB_BRANCH"]


# ---------------------------------------------------------------------------
# OAuth routes
# ---------------------------------------------------------------------------

@bp.get("/login")
def login():
    if session.get("github_username") and session["github_username"] in current_app.config["ALLOWED_MODERATORS"]:
        return redirect(url_for("admin.index"))
    state = secrets.token_urlsafe(16)
    session.permanent = True
    session["oauth_state"] = state
    client_id = current_app.config["GITHUB_CLIENT_ID"]
    return redirect(
        f"https://github.com/login/oauth/authorize"
        f"?client_id={client_id}&scope=public_repo&state={state}"
    )


@bp.get("/callback")
def callback():
    state = request.args.get("state", "")
    if state != session.pop("oauth_state", None):
        return "Invalid OAuth state", 400

    code = request.args.get("code", "")
    if not code:
        return "Missing code", 400

    try:
        token = github_api.exchange_code(
            current_app.config["GITHUB_CLIENT_ID"],
            current_app.config["GITHUB_CLIENT_SECRET"],
            code,
        )
        user = github_api.get_user(token)
    except (ValueError, http.HTTPError) as e:
        return f"GitHub OAuth error: {e}", 502

    username = user["login"]
    if username not in current_app.config["ALLOWED_MODERATORS"]:
        return render_template("admin_unauthorized.html", username=username), 403

    session["github_username"] = username
    session["github_token"] = token
    return redirect(url_for("admin.index"))


@bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------

def _is_edit(row) -> bool:
    data = json.loads(row["data"] or "{}")
    return "slug" in data


@bp.get("/")
@require_moderator
def index():
    db = get_db()

    all_lecture = db.execute(
        "SELECT * FROM lecture_suggestions ORDER BY created_at DESC"
    ).fetchall()
    edit_suggestions = [r for r in all_lecture if _is_edit(r)]
    new_suggestions  = [r for r in all_lecture if not _is_edit(r)]

    learning_suggestions = db.execute(
        "SELECT * FROM learning_suggestions ORDER BY created_at DESC"
    ).fetchall()

    topic_suggestions = db.execute(
        "SELECT * FROM topic_suggestions ORDER BY created_at DESC"
    ).fetchall()

    rating_groups = db.execute(
        """SELECT slug, field,
                  COUNT(*)            AS vote_count,
                  AVG(value)          AS mean_value,
                  MIN(value)          AS min_value,
                  MAX(value)          AS max_value,
                  GROUP_CONCAT(value) AS values_csv
           FROM rating_votes
           GROUP BY slug, field
           ORDER BY slug, field"""
    ).fetchall()

    # Pre-parse data JSON for edit suggestions so template can iterate it.
    # Also fetch the current lecture content so the moderator can see the live
    # title and URL when validating the proposed changes.
    token  = _gh_token()
    repo   = _gh_repo()
    branch = _gh_branch()

    edit_parsed = []
    for row in edit_suggestions:
        data = json.loads(row["data"] or "{}")
        slug = data.get("slug", "")
        current_title = None
        current_url   = None
        try:
            live, _ = github_api.get_file(repo, f"data/{slug}.json", branch, token)
            current_title = live.get("title", "")
            urls = live.get("urls", [])
            current_url = urls[0] if urls else None
        except Exception:
            pass
        edit_parsed.append({
            "id":            row["id"],
            "slug":          slug,
            "url":           row["url"],
            "title":         row["title"],
            "note":          row["note"],
            "data":          data,
            "created_at":    row["created_at"],
            "current_title": current_title,
            "current_url":   current_url,
        })

    new_parsed = []
    for row in new_suggestions:
        data = json.loads(row["data"] or "{}")
        new_parsed.append({
            "id":         row["id"],
            "url":        row["url"],
            "title":      row["title"],
            "note":       row["note"],
            "data":       data,
            "created_at": row["created_at"],
        })

    return render_template(
        "admin.html",
        edit_suggestions=edit_parsed,
        new_suggestions=new_parsed,
        learning_suggestions=[dict(r) for r in learning_suggestions],
        topic_suggestions=[dict(r) for r in topic_suggestions],
        rating_groups=[dict(r) for r in rating_groups],
        field_labels=FIELD_LABELS,
        username=session["github_username"],
    )


# ---------------------------------------------------------------------------
# GitHub write helpers
# ---------------------------------------------------------------------------

def _flatten_learnings(content: dict) -> dict:
    """Convert learnings list-of-single-key-dicts → flat {text: rating_obj}."""
    flat = {}
    for item in content.get("learnings", []):
        flat.update(item)
    return flat


def _rebuild_learnings(flat: dict) -> list:
    return [{k: v} for k, v in flat.items()]


def _smart_merge_collection(existing: dict, proposed_keys: list) -> dict:
    """
    Merge a topics/tags dict.
    - Keys in proposed but absent in existing → add with count 1
    - Keys in proposed and already existing → keep existing count
    - Keys in existing but absent from proposed → set to 0 (SSG hides ≤0)
    """
    merged = dict(existing)
    proposed_set = set(proposed_keys)
    for key in proposed_set:
        if key not in merged:
            merged[key] = 1
    for key in list(merged):
        if key not in proposed_set:
            merged[key] = 0
    return merged


def _github_error_response(exc: http.HTTPError):
    status = exc.response.status_code if exc.response is not None else 502
    try:
        msg = exc.response.json().get("message", str(exc))
    except Exception:
        msg = str(exc)
    if status == 409:
        return jsonify({"error": "File modified concurrently — reload and retry"}), 409
    if status == 404:
        return jsonify({"error": f"File not found on GitHub: {msg}"}), 404
    return jsonify({"error": f"GitHub error: {msg}"}), 502


# ---------------------------------------------------------------------------
# API: lecture suggestions
# ---------------------------------------------------------------------------

@bp.post("/api/lecture-suggestions/<int:id>/approve")
@require_moderator
def approve_lecture(id):
    db = get_db()
    row = db.execute("SELECT * FROM lecture_suggestions WHERE id = ?", (id,)).fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404

    data = json.loads(row["data"] or "{}")
    token  = _gh_token()
    repo   = _gh_repo()
    branch = _gh_branch()

    if "slug" in data:
        # Edit suggestion — apply diff to existing file
        slug = data["slug"]
        try:
            content, sha = github_api.get_file(repo, f"data/{slug}.json", branch, token)
        except http.HTTPError as e:
            return _github_error_response(e)

        if row["title"] is not None:
            content["title"] = row["title"]
        if row["note"] is not None:
            content["extra"] = row["note"]

        for key in ("urls", "speakers", "year", "startsAt", "embed"):
            if key in data:
                content[key] = data[key]

        for collection in ("topics", "tags"):
            if collection in data:
                existing = content.get(collection, {})
                content[collection] = _smart_merge_collection(existing, data[collection])

        if "learnings" in data:
            flat = _flatten_learnings(content)
            proposed = data["learnings"]  # list of text strings
            merged = {}
            for text in proposed:
                merged[text] = flat.get(text, {"rating": 5, "weight": 0})
            content["learnings"] = _rebuild_learnings(merged)

        for key in KNOWN_SCALE_FIELDS:
            if key in data:
                content[key] = data[key]

        commit_msg = f"moderation: edit {slug}"
    else:
        # New lecture suggestion
        slug = (request.get_json(silent=True) or {}).get("slug", "").strip()
        if not slug:
            return jsonify({"error": "slug required for new lecture"}), 400

        content = {"title": row["title"] or "", "urls": data.get("urls", [row["url"]])}
        if row["note"]:
            content["extra"] = row["note"]
        for key in ("speakers", "year", "startsAt", "embed", "topics", "tags"):
            if key in data:
                content[key] = data[key]
        if "learnings" in data:
            content["learnings"] = [
                {text: {"rating": 5, "weight": 0}} for text in data["learnings"]
            ]
        for key in KNOWN_SCALE_FIELDS:
            if key in data:
                content[key] = data[key]
        sha = None
        commit_msg = f"moderation: add {slug}"

    try:
        github_api.put_file(repo, f"data/{slug}.json", branch, token, content, commit_msg, sha=sha)
    except http.HTTPError as e:
        return _github_error_response(e)

    db.execute("DELETE FROM lecture_suggestions WHERE id = ?", (id,))
    db.commit()
    return jsonify({"status": "ok"})


@bp.post("/api/lecture-suggestions/<int:id>/discard")
@require_moderator
def discard_lecture(id):
    db = get_db()
    db.execute("DELETE FROM lecture_suggestions WHERE id = ?", (id,))
    db.commit()
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# API: learning suggestions
# ---------------------------------------------------------------------------

@bp.post("/api/learning-suggestions/<int:id>/approve")
@require_moderator
def approve_learning(id):
    db = get_db()
    row = db.execute("SELECT * FROM learning_suggestions WHERE id = ?", (id,)).fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404

    token  = _gh_token()
    repo   = _gh_repo()
    branch = _gh_branch()

    try:
        content, sha = github_api.get_file(repo, f"data/{row['slug']}.json", branch, token)
    except http.HTTPError as e:
        return _github_error_response(e)

    flat = _flatten_learnings(content)
    if row["learning"] not in flat:
        flat[row["learning"]] = {"rating": 5, "weight": 0}
    content["learnings"] = _rebuild_learnings(flat)

    try:
        github_api.put_file(
            repo, f"data/{row['slug']}.json", branch, token, content,
            f"moderation: add learning to {row['slug']}", sha=sha,
        )
    except http.HTTPError as e:
        return _github_error_response(e)

    db.execute("DELETE FROM learning_suggestions WHERE id = ?", (id,))
    db.commit()
    return jsonify({"status": "ok"})


@bp.post("/api/learning-suggestions/<int:id>/discard")
@require_moderator
def discard_learning(id):
    db = get_db()
    db.execute("DELETE FROM learning_suggestions WHERE id = ?", (id,))
    db.commit()
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# API: topic suggestions
# ---------------------------------------------------------------------------

@bp.post("/api/topic-suggestions/<int:id>/approve")
@require_moderator
def approve_topic(id):
    db = get_db()
    row = db.execute("SELECT * FROM topic_suggestions WHERE id = ?", (id,)).fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404

    token  = _gh_token()
    repo   = _gh_repo()
    branch = _gh_branch()

    try:
        content, sha = github_api.get_file(repo, f"data/{row['slug']}.json", branch, token)
    except http.HTTPError as e:
        return _github_error_response(e)

    topics = content.get("topics", {})
    if row["action"] == "add":
        topics[row["topic"]] = max(1, topics.get(row["topic"], 0) + 1)
    else:
        topics[row["topic"]] = topics.get(row["topic"], 0) - 1
    content["topics"] = topics

    try:
        github_api.put_file(
            repo, f"data/{row['slug']}.json", branch, token, content,
            f"moderation: {row['action']} topic '{row['topic']}' on {row['slug']}", sha=sha,
        )
    except http.HTTPError as e:
        return _github_error_response(e)

    db.execute("DELETE FROM topic_suggestions WHERE id = ?", (id,))
    db.commit()
    return jsonify({"status": "ok"})


@bp.post("/api/topic-suggestions/<int:id>/discard")
@require_moderator
def discard_topic(id):
    db = get_db()
    db.execute("DELETE FROM topic_suggestions WHERE id = ?", (id,))
    db.commit()
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# API: rating votes
# ---------------------------------------------------------------------------

@bp.post("/api/rating-votes/approve")
@require_moderator
def approve_ratings():
    body = request.get_json(silent=True) or {}
    slug  = body.get("slug", "").strip()
    field = body.get("field", "").strip()
    if not slug or not field:
        return jsonify({"error": "slug and field required"}), 400

    db = get_db()
    rows = db.execute(
        "SELECT value FROM rating_votes WHERE slug = ? AND field = ?", (slug, field)
    ).fetchall()
    if not rows:
        return jsonify({"error": "no votes found"}), 404

    values = [r["value"] for r in rows]
    count  = len(values)
    total  = sum(values)

    token  = _gh_token()
    repo   = _gh_repo()
    branch = _gh_branch()

    try:
        content, sha = github_api.get_file(repo, f"data/{slug}.json", branch, token)
    except http.HTTPError as e:
        return _github_error_response(e)

    is_learning = field not in KNOWN_SCALE_FIELDS

    if is_learning:
        flat = _flatten_learnings(content)
        obj  = flat.get(field, {"rating": 5, "weight": 0})
    else:
        obj = content.get(field, {"rating": 5, "weight": 0})

    old_weight = obj.get("weight", 0)
    old_rating = obj.get("rating", 5)
    new_weight = old_weight + count
    new_rating = (old_rating * old_weight + total) / new_weight

    obj["rating"] = round(new_rating, 4)
    obj["weight"] = new_weight

    if is_learning:
        flat[field] = obj
        content["learnings"] = _rebuild_learnings(flat)
    else:
        content[field] = obj

    try:
        github_api.put_file(
            repo, f"data/{slug}.json", branch, token, content,
            f"moderation: apply {count} rating(s) for '{field}' on {slug}", sha=sha,
        )
    except http.HTTPError as e:
        return _github_error_response(e)

    db.execute("DELETE FROM rating_votes WHERE slug = ? AND field = ?", (slug, field))
    db.commit()
    return jsonify({"status": "ok"})


@bp.post("/api/rating-votes/discard")
@require_moderator
def discard_ratings():
    body = request.get_json(silent=True) or {}
    slug  = body.get("slug", "").strip()
    field = body.get("field", "").strip()
    if not slug or not field:
        return jsonify({"error": "slug and field required"}), 400

    db = get_db()
    db.execute("DELETE FROM rating_votes WHERE slug = ? AND field = ?", (slug, field))
    db.commit()
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# API: batch
# ---------------------------------------------------------------------------

@bp.post("/api/batch")
@require_moderator
def batch():
    """
    Process multiple moderation decisions in one request, writing a single commit.

    Expects JSON: { "decisions": [ { "type", "action", ... }, ... ] }
    action: "accept" | "deny" | "ignore"
    type "lecture": also needs "id"; new lectures also need "slug"
    type "learning": needs "id"
    type "topic":    needs "id"
    type "rating":   needs "slug" and "field"
    """
    body = request.get_json(silent=True) or {}
    decisions = body.get("decisions", [])
    if not decisions:
        return jsonify({"error": "no decisions provided"}), 400

    token  = _gh_token()
    repo   = _gh_repo()
    branch = _gh_branch()
    db_conn = get_db()

    # --- Pre-fetch DB rows for all non-ignored decisions --------------------
    lecture_rows  = {}
    learning_rows = {}
    topic_rows    = {}

    for d in decisions:
        if d.get("action", "ignore") == "ignore":
            continue
        dtype = d.get("type")
        rid   = d.get("id")

        if dtype == "lecture" and rid and rid not in lecture_rows:
            row = db_conn.execute(
                "SELECT * FROM lecture_suggestions WHERE id = ?", (rid,)
            ).fetchone()
            if not row:
                return jsonify({"error": f"lecture suggestion {rid} not found"}), 404
            lecture_rows[rid] = row

        elif dtype == "learning" and rid and rid not in learning_rows:
            row = db_conn.execute(
                "SELECT * FROM learning_suggestions WHERE id = ?", (rid,)
            ).fetchone()
            if not row:
                return jsonify({"error": f"learning suggestion {rid} not found"}), 404
            learning_rows[rid] = row

        elif dtype == "topic" and rid and rid not in topic_rows:
            row = db_conn.execute(
                "SELECT * FROM topic_suggestions WHERE id = ?", (rid,)
            ).fetchone()
            if not row:
                return jsonify({"error": f"topic suggestion {rid} not found"}), 404
            topic_rows[rid] = row

    # --- Determine which slugs need fetching (accepted items only) ----------
    slugs_needed      = set()
    new_lecture_slugs = {}  # id -> provided slug

    for d in decisions:
        if d.get("action") != "accept":
            continue
        dtype = d.get("type")

        if dtype == "lecture":
            rid  = d["id"]
            data = json.loads(lecture_rows[rid]["data"] or "{}")
            if "slug" in data:
                slugs_needed.add(data["slug"])
            else:
                slug = d.get("slug", "").strip()
                if not slug:
                    return jsonify({"error": f"slug required for new lecture (id={rid})"}), 400
                new_lecture_slugs[rid] = slug

        elif dtype == "learning":
            slugs_needed.add(learning_rows[d["id"]]["slug"])

        elif dtype == "topic":
            slugs_needed.add(topic_rows[d["id"]]["slug"])

        elif dtype == "rating":
            slug  = d.get("slug", "").strip()
            field = d.get("field", "").strip()
            if not slug or not field:
                return jsonify({"error": "rating decision requires slug and field"}), 400
            slugs_needed.add(slug)

    # --- Fetch files from GitHub once per slug ------------------------------
    file_cache = {}
    for slug in slugs_needed:
        try:
            content, _sha = github_api.get_file(repo, f"data/{slug}.json", branch, token)
            file_cache[slug] = content
        except http.HTTPError as e:
            return _github_error_response(e)

    # --- Apply accepted changes to in-memory content -----------------------
    commit_parts = []
    db_deletes   = []

    for d in decisions:
        action = d.get("action", "ignore")
        dtype  = d.get("type")

        if action == "ignore":
            continue

        if action == "deny":
            if dtype == "lecture":
                db_deletes.append(
                    ("DELETE FROM lecture_suggestions WHERE id = ?", (d["id"],))
                )
            elif dtype == "learning":
                db_deletes.append(
                    ("DELETE FROM learning_suggestions WHERE id = ?", (d["id"],))
                )
            elif dtype == "topic":
                db_deletes.append(
                    ("DELETE FROM topic_suggestions WHERE id = ?", (d["id"],))
                )
            elif dtype == "rating":
                db_deletes.append(
                    ("DELETE FROM rating_votes WHERE slug = ? AND field = ?",
                     (d["slug"], d["field"]))
                )
            continue

        # action == "accept"
        if dtype == "lecture":
            rid  = d["id"]
            row  = lecture_rows[rid]
            data = json.loads(row["data"] or "{}")

            if "slug" in data:
                slug    = data["slug"]
                content = file_cache[slug]
                if row["title"] is not None:
                    content["title"] = row["title"]
                if row["note"] is not None:
                    content["extra"] = row["note"]
                for key in ("urls", "speakers", "year", "startsAt", "embed"):
                    if key in data:
                        content[key] = data[key]
                for collection in ("topics", "tags"):
                    if collection in data:
                        content[collection] = _smart_merge_collection(
                            content.get(collection, {}), data[collection]
                        )
                if "learnings" in data:
                    flat   = _flatten_learnings(content)
                    merged = {t: flat.get(t, {"rating": 5, "weight": 0})
                              for t in data["learnings"]}
                    content["learnings"] = _rebuild_learnings(merged)
                for key in KNOWN_SCALE_FIELDS:
                    if key in data:
                        content[key] = data[key]
                commit_parts.append(f"edit {slug}")
            else:
                slug    = new_lecture_slugs[rid]
                content = {"title": row["title"] or "", "urls": data.get("urls", [row["url"]])}
                if row["note"]:
                    content["extra"] = row["note"]
                for key in ("speakers", "year", "startsAt", "embed", "topics", "tags"):
                    if key in data:
                        content[key] = data[key]
                if "learnings" in data:
                    content["learnings"] = [
                        {t: {"rating": 5, "weight": 0}} for t in data["learnings"]
                    ]
                for key in KNOWN_SCALE_FIELDS:
                    if key in data:
                        content[key] = data[key]
                file_cache[slug] = content
                commit_parts.append(f"add {slug}")

            db_deletes.append(
                ("DELETE FROM lecture_suggestions WHERE id = ?", (rid,))
            )

        elif dtype == "learning":
            rid     = d["id"]
            row     = learning_rows[rid]
            slug    = row["slug"]
            content = file_cache[slug]
            flat    = _flatten_learnings(content)
            if row["learning"] not in flat:
                flat[row["learning"]] = {"rating": 5, "weight": 0}
            content["learnings"] = _rebuild_learnings(flat)
            commit_parts.append(f"add learning to {slug}")
            db_deletes.append(
                ("DELETE FROM learning_suggestions WHERE id = ?", (rid,))
            )

        elif dtype == "topic":
            rid     = d["id"]
            row     = topic_rows[rid]
            slug    = row["slug"]
            content = file_cache[slug]
            topics  = content.get("topics", {})
            if row["action"] == "add":
                topics[row["topic"]] = max(1, topics.get(row["topic"], 0) + 1)
            else:
                topics[row["topic"]] = topics.get(row["topic"], 0) - 1
            content["topics"] = topics
            commit_parts.append(f"{row['action']} topic '{row['topic']}' on {slug}")
            db_deletes.append(
                ("DELETE FROM topic_suggestions WHERE id = ?", (rid,))
            )

        elif dtype == "rating":
            slug    = d["slug"]
            field   = d["field"]
            votes   = db_conn.execute(
                "SELECT value FROM rating_votes WHERE slug = ? AND field = ?", (slug, field)
            ).fetchall()
            if not votes:
                return jsonify({"error": f"no votes found for {slug}/{field}"}), 404
            values     = [r["value"] for r in votes]
            count      = len(values)
            total      = sum(values)
            content    = file_cache[slug]
            is_learning = field not in KNOWN_SCALE_FIELDS
            if is_learning:
                flat = _flatten_learnings(content)
                obj  = flat.get(field, {"rating": 5, "weight": 0})
            else:
                obj = content.get(field, {"rating": 5, "weight": 0})
            old_weight = obj.get("weight", 0)
            old_rating = obj.get("rating", 5)
            new_weight = old_weight + count
            new_rating = (old_rating * old_weight + total) / new_weight
            obj["rating"] = round(new_rating, 4)
            obj["weight"] = new_weight
            if is_learning:
                flat[field] = obj
                content["learnings"] = _rebuild_learnings(flat)
            else:
                content[field] = obj
            commit_parts.append(f"apply {count} rating(s) for '{field}' on {slug}")
            db_deletes.append(
                ("DELETE FROM rating_votes WHERE slug = ? AND field = ?", (slug, field))
            )

    # --- Commit all file changes in one go ----------------------------------
    if file_cache:
        commit_msg = "moderation: " + "; ".join(commit_parts)
        try:
            github_api.put_files(
                repo, branch, token,
                {f"data/{slug}.json": content for slug, content in file_cache.items()},
                commit_msg,
            )
        except http.HTTPError as e:
            return _github_error_response(e)

    # --- Clean up database --------------------------------------------------
    for sql, params in db_deletes:
        db_conn.execute(sql, params)
    db_conn.commit()

    accepted_count = sum(1 for d in decisions if d.get("action") == "accept")
    denied_count   = sum(1 for d in decisions if d.get("action") == "deny")
    return jsonify({"status": "ok", "accepted": accepted_count, "denied": denied_count})

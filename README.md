# awesome-lectures

Community-curated collection of lectures worth watching.

## Architecture

Two independent components that can be developed and deployed separately:

```
data/           one JSON file per lecture (source of truth)
schema.json     JSON Schema (Draft 7) for lecture data files
src/            SSG — builds data/ + templates/ → public/
  ssg.py
  validate.py
  pyproject.toml
backend/        Flask API for runtime interactions
  app.py
  config.py
  db.py
  routes/
    interactions.py   likes + seen counts
    ratings.py        numerical field voting
    suggestions.py    lecture/tag/learning submissions
  schema.sql
  pyproject.toml
templates/      Jinja2 templates, CSS, JS
public/         build output (gitignored)
.thumbnails/    cached YouTube thumbnails (committed)
misc/           favicon, logo, placeholder thumbnail
doc/            design notes and reference
```

### SSG (`src/`)

Python script (`ssg.py`) that reads `data/*.json`, renders Jinja2 templates, and writes `public/`. Run with `uv run ssg.py` from the `src/` directory.

What it produces:

- `public/index.html` — landing page with 3 randomly selected featured lectures (must have ≥ 2 learning outcomes)
- `public/lectures/<slug>.html` — per-lecture detail page
- `public/lectures/{random,alpha,recent}/` — paginated list views (20 per page), three orderings
- `public/search/` — Pagefind-powered search page
- `public/submit/` — lecture submission form (via staticforms.xyz)
- `public/suggest-edit/<slug>/` — per-lecture edit suggestion form
- `public/about/`
- `public/thumbnails/` — YouTube thumbnails (400 px wide, WebP) or placeholder

On first build, `ssg.py` checks YouTube's oEmbed API to determine embeddability for each lecture that lacks an `embed` field, and writes the result back to the JSON file. Thumbnails are fetched from YouTube, converted to WebP, and cached in `.thumbnails/`.

Build-time env vars:

| Variable | Purpose |
|---|---|
| `STATICFORMS_KEY` | staticforms.xyz API key for the submit form |
| `SITE_URL` | Deployed URL (used in submit form payload) |
| `API_BASE` | Controls frontend API calls. Unset → API disabled. `""` → relative `/api/...` calls (production). A URL → that origin (local dev). |

After rendering HTML, the build runs `npx pagefind --site public` to generate the search index.

### Backend (`backend/`)

Flask app (`app.py`) providing a JSON API for runtime interactions that aren't baked into the static build. Uses SQLite (`lectures.db`). Fingerprinting via a UUID cookie sent as `X-AL-Fingerprint` header; one fingerprint per anonymous user.

**API endpoints:**

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/interactions/<slug>` | Total like and seen counts |
| `POST` | `/api/interactions/<slug>/like` | Record a like (deduplicated per fingerprint per day) |
| `POST` | `/api/interactions/<slug>/seen` | Record a view (deduplicated per fingerprint per day) |
| `POST` | `/api/ratings/<slug>` | Submit a numerical rating for a field (0–10) |
| `POST` | `/api/suggestions/lectures` | Suggest a new lecture |
| `POST` | `/api/suggestions/learnings/<slug>` | Suggest a learning outcome for an existing lecture |
| `POST` | `/api/suggestions/topics/<slug>` | Suggest adding a topic tag |
| `POST` | `/api/suggestions/tags/<slug>` | Suggest tag additions/removals (batch) |
| `GET` | `/health` | Health check |

Backend env vars:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE` | `backend/lectures.db` | SQLite file path |
| `SECRET_KEY` | `dev-secret-change-in-prod` | Flask secret key |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS allowed origins |

### Data (`data/`)

One JSON file per lecture, named `<slug>.json`. Validated against `schema.json` (JSON Schema Draft 7) by `src/validate.py`.

Required fields: `title`, `urls` (string or array of strings).

Optional fields (see `schema.json` for full spec):

| Field | Type | Description |
|---|---|---|
| `speakers` | string[] | Presenter names |
| `embed` | bool | YouTube embed allowed (auto-set by SSG) |
| `extra` | string | Free-text description |
| `year` | int | Year recorded |
| `startsAt` | int | Seconds offset where relevant content begins |
| `topics` | `{name: vote_count}` | Coarse topic tags; entries with count ≤ 0 are hidden |
| `tags` | `{name: vote_count}` | Descriptive tags (e.g. "conference", "seminar") |
| `learnings` | array | Learning outcomes — list of `{"outcome": scaleRating}` dicts |
| `liked` | binaryRating | Aggregate like signal |
| `audioQuality` | scaleRating | Audio quality (0–10) |
| `videoQuality` | scaleRating | Video quality (0–10) |
| `beginnerExpertSpectrum` | scaleRating | Audience level: 0 = beginner, 10 = expert |
| `worthListeningToWithoutVideo` | scaleRating | Audio-only value (0–10) |

**Rating types** (see `doc/ref/ratings.md` for algorithm details):

- `binaryRating`: `{rating, weight}` — Bayesian mean likes/day; weight = cumulative days active
- `scaleRating`: `{rating, spread, weight}` — Bayesian mean (0–10), std deviation, cumulative vote count

Both use `prior_weight = 10` so sparse items start near neutral (0.3 likes/day or 5.0/10) and converge toward the true population value as votes accumulate. The SSG adds one additional phantom vote of 5 to all scale ratings at display time.

## Running locally

### Build the site

```sh
cd src
uv run ssg.py
```

Then serve `public/` with any static file server, e.g. `python3 -m http.server -d public 8000`.

### Run the backend

```sh
cd backend
uv run flask --app app run
```

Runs on `http://localhost:5000` by default. Set `API_BASE=http://localhost:5000` before building the SSG to wire frontend calls to the local backend.

### Validate data files

```sh
cd src
uv run validate.py
```

## Adding a lecture

Create `data/<slug>.json` with at minimum:

```json
{
    "title": "The Title",
    "urls": ["https://..."],
    "speakers": ["Name"],
    "topics": {"topic": 1},
    "tags": {"conference": 1}
}
```

The `embed` field is auto-populated on first build. The slug (filename without `.json`) becomes the URL path component.

## Deployment

Deployed on Netlify (config in `netlify.toml`). The build command installs `uv` and runs the SSG. Set `STATICFORMS_KEY`, `SITE_URL`, and `API_BASE` (set to `""` for the proxy rewrite) in the Netlify environment variables UI.

The backend runs separately on a VPS. Netlify proxies `/api/*` requests to it via the redirect rule in `netlify.toml` (update the target URL there).

## Meta sources

- <https://www.edukatico.org/en/report/free-online-lectures-list-of-all-subjects-and-universities>
- <https://www.openculture.com/freeonlinecourses>
- <https://library.wabash.edu/av/open>
- <https://www.youtube.com/watch?v=F-OxHWWg59o&list=PLoROMvodv4rMyupDF2O00r19JsmolyXdD>
- <https://video.tu-clausthal.de/uebersicht/lehre/vorlesungsaufzeichnungen.html>
- <https://old.reddit.com/r/lectures/>, especially <https://old.reddit.com/r/lectures/comments/9ykg99/announcement_new_submission_rule_going_forward/>

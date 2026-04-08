# awesome-lectures

Community-curated collection of lectures worth watching. Built as a static site.

## Structure

```
data/           one JSON file per lecture
misc/           favicon, logo, placeholder thumbnail
src/            SSG (Python/uv)
  ssg.py        build script
  pyproject.toml
templates/      Jinja2 templates + styles.css
public/         build output (gitignored)
.thumbnails/    cached YouTube thumbnails (committed)
```

## Adding a lecture

Create `data/<slug>.json`:

```json
{
    "title": "The Title",
    "urls": ["https://..."],
    "speakers": ["Name"],
    "topics": ["topic"],
    "tags": ["conference"]
}
```

Optional fields: `learnings` (list of `{"topic": score}` dicts), `liked` (`[score, count]`), `beginnerExpertSpectrum` (`[score, count]`), `worthListeningToWithoutVideo` (int/10).

The `embed` field (bool) is auto-set on first build via YouTube's oEmbed API and written back to the JSON. Remove it to re-check.

## Build

```sh
cd src && uv run ssg.py
```

Requires `npx` (pagefind). Set env vars before building for production:

```sh
export STATICFORMS_KEY=...   # from staticforms.xyz
export SITE_URL=https://...  # deployed URL, trailing slash
```

## Deploy

Netlify. Config in `netlify.toml`. Set `STATICFORMS_KEY` and `SITE_URL` in the Netlify UI under Site configuration → Environment variables.

## Meta sources

- <https://www.edukatico.org/en/report/free-online-lectures-list-of-all-subjects-and-universities>
- <https://www.openculture.com/freeonlinecourses>
- <https://library.wabash.edu/av/open>
- <https://www.youtube.com/watch?v=F-OxHWWg59o&list=PLoROMvodv4rMyupDF2O00r19JsmolyXdD>
- <https://video.tu-clausthal.de/uebersicht/lehre/vorlesungsaufzeichnungen.html>

- <https://old.reddit.com/r/lectures/>, especially <https://old.reddit.com/r/lectures/comments/9ykg99/announcement_new_submission_rule_going_forward/>
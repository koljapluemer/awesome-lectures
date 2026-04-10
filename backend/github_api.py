import base64
import json

import requests

GITHUB_API = "https://api.github.com"
GITHUB_AUTH = "https://github.com"


def exchange_code(client_id: str, client_secret: str, code: str) -> str:
    """Exchange OAuth code for an access token. Raises ValueError on GitHub error."""
    resp = requests.post(
        f"{GITHUB_AUTH}/login/oauth/access_token",
        json={"client_id": client_id, "client_secret": client_secret, "code": code},
        headers={"Accept": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise ValueError(data.get("error_description", data["error"]))
    return data["access_token"]


def get_user(token: str) -> dict:
    """Return the authenticated GitHub user object."""
    resp = requests.get(
        f"{GITHUB_API}/user",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_file(repo: str, path: str, branch: str, token: str) -> tuple[dict, str]:
    """
    Fetch a JSON file from the repo. Returns (parsed_dict, sha).
    Raises requests.HTTPError on failure (caller handles 404 for new-file case).
    """
    resp = requests.get(
        f"{GITHUB_API}/repos/{repo}/contents/{path}",
        params={"ref": branch},
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    # GitHub base64 includes newlines — strip before decoding
    raw = base64.b64decode(data["content"].replace("\n", ""))
    return json.loads(raw), data["sha"]


def put_file(
    repo: str,
    path: str,
    branch: str,
    token: str,
    content: dict,
    message: str,
    sha: str | None = None,
) -> None:
    """
    Create or update a JSON file in the repo.
    sha=None creates a new file; passing sha updates an existing one.
    Raises requests.HTTPError on failure.
    """
    encoded = base64.b64encode(
        json.dumps(content, indent=4, ensure_ascii=False).encode()
    ).decode()

    body: dict = {
        "message": message,
        "content": encoded,
        "branch": branch,
    }
    if sha is not None:
        body["sha"] = sha

    resp = requests.put(
        f"{GITHUB_API}/repos/{repo}/contents/{path}",
        json=body,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        timeout=15,
    )
    resp.raise_for_status()


def put_files(
    repo: str,
    branch: str,
    token: str,
    files: dict,
    message: str,
) -> None:
    """
    Commit multiple JSON files in a single git commit using the Git Data API.
    files: {path: content_dict}
    Raises requests.HTTPError on failure.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    r = requests.get(
        f"{GITHUB_API}/repos/{repo}/git/ref/heads/{branch}",
        headers=headers, timeout=10,
    )
    r.raise_for_status()
    head_sha = r.json()["object"]["sha"]

    r = requests.get(
        f"{GITHUB_API}/repos/{repo}/git/commits/{head_sha}",
        headers=headers, timeout=10,
    )
    r.raise_for_status()
    base_tree_sha = r.json()["tree"]["sha"]

    tree_entries = [
        {
            "path": path,
            "mode": "100644",
            "type": "blob",
            "content": json.dumps(content, indent=4, ensure_ascii=False),
        }
        for path, content in files.items()
    ]

    r = requests.post(
        f"{GITHUB_API}/repos/{repo}/git/trees",
        json={"base_tree": base_tree_sha, "tree": tree_entries},
        headers=headers, timeout=30,
    )
    r.raise_for_status()
    new_tree_sha = r.json()["sha"]

    r = requests.post(
        f"{GITHUB_API}/repos/{repo}/git/commits",
        json={"message": message, "tree": new_tree_sha, "parents": [head_sha]},
        headers=headers, timeout=10,
    )
    r.raise_for_status()
    new_commit_sha = r.json()["sha"]

    r = requests.patch(
        f"{GITHUB_API}/repos/{repo}/git/refs/heads/{branch}",
        json={"sha": new_commit_sha},
        headers=headers, timeout=10,
    )
    r.raise_for_status()

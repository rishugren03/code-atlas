"""GitHub URL parsing utilities."""

import re
from urllib.parse import urlparse


def parse_github_url(url: str) -> tuple[str, str]:
    """Extract owner and repo name from a GitHub URL.

    Supports:
      - https://github.com/owner/repo
      - https://github.com/owner/repo.git
      - https://github.com/owner/repo/
      - git@github.com:owner/repo.git
      - http://github.com/owner/repo

    Returns:
        tuple[str, str]: (owner, repo_name)

    Raises:
        ValueError: If the URL is not a valid GitHub repository URL.
    """
    url = url.strip()

    # Handle SSH URLs: git@github.com:owner/repo.git
    ssh_match = re.match(r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)

    # Handle HTTPS URLs
    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise ValueError(f"Invalid URL: {url}") from exc

    if parsed.hostname not in ("github.com", "www.github.com"):
        raise ValueError(
            f"Not a GitHub URL: {url}. Only github.com repositories are supported."
        )

    # Extract path segments: /owner/repo[.git][/...]
    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]

    parts = path.split("/")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ValueError(
            f"Invalid GitHub repo URL: {url}. Expected format: https://github.com/owner/repo"
        )

    owner = parts[0]
    repo_name = parts[1]

    return owner, repo_name

"""Get a code base from GitHub, falling back to a prebuilt local copy when GitHub cannot be used.

The repository is downloaded as a zip snapshot through the GitHub API, so git is not required and
private repositories work with a token. Each repo@ref is cached under .work/repos: when a fresh
download fails, the last downloaded copy is used before falling back to the local folder.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .java_runner import WORK_DIR

REPO_CACHE = WORK_DIR / "repos"
API_URL = "https://api.github.com"
TIMEOUT = 60
COMPLETE_MARKER = ".difflens-download"

# https://github.com/owner/repo(.git)(/tree/<ref>(/<path>)) or git@github.com:owner/repo(.git)
_GITHUB_URL = re.compile(
    r"^(?:https?://(?:www\.)?github\.com/|git@github\.com:)(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?"
    r"(?:/tree/(?P<ref>[^/]+)(?:/(?P<path>.+?))?)?/?$")

GITHUB = "github"
CACHED = "cached"
LOCAL = "local"
FALLBACK = "fallback"


class SourceError(Exception):
    """GitHub could not provide the code; the message says why, in plain words."""


def _remove_tree(path: Path) -> None:
    """Delete a folder, clearing the read-only flag that Windows sets on some extracted files."""
    def make_writable_and_retry(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    if path.exists():
        shutil.rmtree(path, onexc=make_writable_and_retry)


@dataclass
class SourceResult:
    label: str
    root: Path
    origin: str  # github | cached | local | fallback
    detail: str  # what was used, or why GitHub could not be used


@dataclass
class GitHubRepo:
    owner: str
    repo: str
    ref: str  # branch, tag or commit; "" = the repository's default branch
    subdir: str  # folder inside the repository holding the project; "" = repository root

    @property
    def name(self) -> str:
        return (f"{self.owner}/{self.repo}" + (f"@{self.ref}" if self.ref else "")
                + (f"/{self.subdir}" if self.subdir else ""))


def parse_github_url(url: str, ref: str = "", subdir: str = "") -> GitHubRepo:
    """Read owner/repo (and an optional /tree/<ref>/<path>) from a GitHub URL; explicit ref/subdir win."""
    match = _GITHUB_URL.match(url.strip())
    if not match:
        raise SourceError(f"'{url.strip()}' is not a GitHub repository URL (expected https://github.com/owner/repo)")
    return GitHubRepo(
        owner=match["owner"],
        repo=match["repo"],
        ref=ref.strip() or match["ref"] or "",
        subdir=(subdir.strip().strip("/\\") or match["path"] or "").replace("\\", "/"),
    )


def _download(repo: GitHubRepo, token: str, dest: Path) -> None:
    url = f"{API_URL}/repos/{repo.owner}/{repo.repo}/zipball"
    if repo.ref:
        url += "/" + urllib.parse.quote(repo.ref, safe="")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "DiffLens"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=TIMEOUT) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise SourceError("repository, branch or tag not found (a private repository needs an access token)") from e
        if e.code in (401, 403):
            raise SourceError(f"GitHub refused access (HTTP {e.code}): check the access token, or the API rate "
                              "limit was reached") from e
        raise SourceError(f"GitHub answered HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SourceError(f"could not reach GitHub ({getattr(e, 'reason', e)})") from e

    tmp = dest.with_name(dest.name + ".part")
    _remove_tree(tmp)
    tmp.mkdir(parents=True)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            base = tmp.resolve()
            for member in archive.infolist():  # refuse entries that would land outside the folder
                if not (tmp / member.filename).resolve().is_relative_to(base):
                    raise SourceError(f"unsafe path in the downloaded archive: {member.filename}")
            archive.extractall(tmp)
    except zipfile.BadZipFile as e:
        raise SourceError("GitHub did not return a valid zip archive") from e
    (tmp / COMPLETE_MARKER).write_text(f"{repo.name}\n{datetime.now():%Y-%m-%d %H:%M}\n", encoding="utf-8")
    # Swap by renaming, never by deleting first: on Windows a virus scanner or indexer can briefly lock
    # freshly extracted files, and the old copy must survive a failed swap.
    old = dest.with_name(dest.name + ".old")
    _remove_tree(old)
    try:
        if dest.exists():
            _rename_with_retry(dest, old)
    except OSError as e:
        raise SourceError(f"could not replace the cached copy in {dest} ({e.strerror or e})") from e
    try:
        _rename_with_retry(tmp, dest)
    except OSError as e:
        if old.exists():
            old.rename(dest)
        raise SourceError(f"could not replace the cached copy in {dest} ({e.strerror or e})") from e
    shutil.rmtree(old, ignore_errors=True)


def _rename_with_retry(src: Path, dst: Path, attempts: int = 10) -> None:
    for attempt in range(attempts):
        try:
            src.rename(dst)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.5)


def _project_root(repo: GitHubRepo, dest: Path) -> Path:
    tops = [p for p in dest.iterdir() if p.is_dir()]  # the zipball wraps everything in owner-repo-<sha>/
    root = tops[0] if len(tops) == 1 else dest
    target = root / repo.subdir if repo.subdir else root
    if not target.is_dir():
        raise SourceError(f"folder '{repo.subdir}' does not exist in {repo.owner}/{repo.repo}")
    return target


def fetch_github(url: str, ref: str = "", subdir: str = "", token: str = "",
                 refresh: bool = False) -> tuple[Path, str, bool]:
    """Return (project folder, description, used_cache). Raises SourceError if neither works."""
    repo = parse_github_url(url, ref, subdir)
    key = hashlib.sha1(f"{repo.owner}/{repo.repo}@{repo.ref}".lower().encode()).hexdigest()[:10]
    dest = REPO_CACHE / f"{repo.owner}-{repo.repo}-{key}"
    cached = (dest / COMPLETE_MARKER).exists()
    if refresh or not cached:
        try:
            _download(repo, token, dest)
            return _project_root(repo, dest), repo.name, False
        except SourceError as e:
            if not (dest / COMPLETE_MARKER).exists():
                raise
            stamp = (dest / COMPLETE_MARKER).read_text(encoding="utf-8").splitlines()[-1]
            return _project_root(repo, dest), f"{repo.name} (cached copy from {stamp}; download failed: {e})", True
    stamp = (dest / COMPLETE_MARKER).read_text(encoding="utf-8").splitlines()[-1]
    return _project_root(repo, dest), f"{repo.name} (cached copy from {stamp})", True


def resolve_source(label: str, url: str, ref: str, subdir: str, token: str, refresh: bool,
                   local_root: Path) -> SourceResult:
    """GitHub when a URL is given and reachable, else the prebuilt local folder. Never raises."""
    if not url.strip():
        return SourceResult(label, local_root, LOCAL, str(local_root))
    try:
        root, description, used_cache = fetch_github(url, ref, subdir, token, refresh)
        return SourceResult(label, root, CACHED if used_cache else GITHUB, description)
    except Exception as e:  # any failure, expected or not, means: use the prebuilt code
        reason = str(e) if isinstance(e, SourceError) else f"unexpected error ({type(e).__name__}: {e})"
        return SourceResult(label, local_root, FALLBACK, f"{reason}. Using the prebuilt code in {local_root}.")

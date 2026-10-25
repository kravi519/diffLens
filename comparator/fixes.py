"""Check the source fixes that the AI explanation proposes.

A proposed fix is an exact text replacement in one source file. It is only accepted when the old text
occurs exactly once, so a stale or ambiguous proposal is refused instead of guessed at. Test files are
never proposed for change: a fix must make the code behave as the tests expect, not change the tests.
Nothing is written to the code bases.
"""

from __future__ import annotations

from pathlib import Path

TEST_FOLDERS = {"test", "tests"}


def check_fix(root: Path, path: str, old_text: str, new_text: str) -> str | None:
    """Return why the fix cannot be applied, or None when it can."""
    if not old_text:
        return "old_text is empty."
    if old_text == new_text:
        return "new_text is the same as old_text."
    root = root.resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        return "path is outside the project root."
    if not target.is_file():
        return f"{path} does not exist."
    if TEST_FOLDERS & set(target.relative_to(root).parts):
        return "fixes must change source code, not tests."
    text = _read(target)
    count = text.count(_match_newlines(old_text, text))
    if count != 1:
        return f"old_text must occur exactly once in {path}, found {count} times."
    return None


def _read(path: Path) -> str:
    # Keep the file's own line endings: reading with universal newlines would rewrite CRLF files as LF.
    return path.read_bytes().decode("utf-8")


def _match_newlines(text: str, file_text: str) -> str:
    """The model copies code with LF line endings; match the file's CRLF endings when it uses them."""
    if "\r\n" in file_text:
        return text.replace("\r\n", "\n").replace("\n", "\r\n")
    return text

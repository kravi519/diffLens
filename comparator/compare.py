"""Line up the results of the two runs input case by input case and classify every difference.

Tests that record their output ("RESULT|<case>|<output>") are matched on the input case, so the
legacy and new-gen suites can be written separately as long as they read the same inputs. Tests
that record nothing fall back to matching on their test id.
"""

from __future__ import annotations

from dataclasses import dataclass

from .java_runner import RunResult, TestCase

PASS = {"passed"}
BROKEN = {"failed", "error"}

# Category keys, in the order they are shown.
REGRESSION = "regression"  # passed in legacy, fails in new gen
FIXED = "fixed"  # failed in legacy, passes in new gen
CHANGED = "changed"  # any other status change (e.g. failed -> error, passed -> skipped)
OUTPUT_DIFF = "output_diff"  # same status, but the code returned different output for the same input
ONLY_LEGACY = "only_legacy"
ONLY_NEWGEN = "only_newgen"
SAME = "same"

CATEGORY_LABELS = {
    REGRESSION: "🔴 Regression",
    FIXED: "🟢 Fixed",
    CHANGED: "🟡 Changed",
    OUTPUT_DIFF: "🟠 Output differs",
    ONLY_LEGACY: "➖ Only in legacy",
    ONLY_NEWGEN: "➕ Only in new gen",
    SAME: "⚪ Same",
}


@dataclass
class Comparison:
    test_id: str
    suite: str
    name: str
    display_name: str
    category: str
    legacy: TestCase | None
    newgen: TestCase | None

    @property
    def legacy_status(self) -> str:
        return self.legacy.status if self.legacy else "missing"

    @property
    def newgen_status(self) -> str:
        return self.newgen.status if self.newgen else "missing"

    @property
    def legacy_output(self) -> str | None:
        return self.legacy.output if self.legacy else None

    @property
    def newgen_output(self) -> str | None:
        return self.newgen.output if self.newgen else None

    @property
    def time_delta(self) -> float | None:
        if self.legacy and self.newgen:
            return self.newgen.time - self.legacy.time
        return None


def _categorize(legacy: TestCase | None, newgen: TestCase | None) -> str:
    if newgen is None:
        return ONLY_LEGACY
    if legacy is None:
        return ONLY_NEWGEN
    if legacy.status == newgen.status:
        if legacy.output is not None and newgen.output is not None and legacy.output != newgen.output:
            return OUTPUT_DIFF
        return SAME
    if legacy.status in PASS and newgen.status in BROKEN:
        return REGRESSION
    if legacy.status in BROKEN and newgen.status in PASS:
        return FIXED
    return CHANGED


def compare(legacy: RunResult, newgen: RunResult) -> list[Comparison]:
    left = {t.key: t for t in legacy.tests}
    right = {t.key: t for t in newgen.tests}
    rows = []
    for test_id in sorted(left.keys() | right.keys()):
        lt, nt = left.get(test_id), right.get(test_id)
        ref = lt or nt
        rows.append(Comparison(
            test_id=test_id,
            suite=ref.suite,
            name=ref.name,
            display_name=ref.display_name,
            category=_categorize(lt, nt),
            legacy=lt,
            newgen=nt,
        ))
    order = list(CATEGORY_LABELS)
    rows.sort(key=lambda r: (order.index(r.category), r.test_id))
    return rows


@dataclass
class Cause:
    """One output token that appears on only one side, and every differing case it explains."""
    token: str
    side: str  # "new gen" (token only in the new-gen output) or "legacy"
    cases: list[Comparison]


def difference_causes(rows: list[Comparison]) -> list[Cause]:
    """Group differing cases by the output tokens only one side produced, most cases first.

    Bulk runs can produce hundreds of differences that share a few causes. Comparing the two outputs
    word by word (for pacs.008: rule codes such as R49 or INSTRID) turns them into a short list, e.g.
    "INSTRID only in new gen: 194 cases". A case is listed under every token it differs by.
    """
    groups: dict[tuple[str, str], list[Comparison]] = {}
    for r in rows:
        if r.category == SAME or r.legacy_output is None or r.newgen_output is None:
            continue
        legacy, newgen = set(r.legacy_output.split()), set(r.newgen_output.split())
        for side, tokens in (("new gen", newgen - legacy), ("legacy", legacy - newgen)):
            for token in tokens:
                groups.setdefault((token, side), []).append(r)
    causes = [Cause(token, side, cases) for (token, side), cases in groups.items()]
    causes.sort(key=lambda c: (-len(c.cases), c.side, c.token))
    return causes


def category_counts(rows: list[Comparison]) -> dict[str, int]:
    counts = {k: 0 for k in CATEGORY_LABELS}
    for r in rows:
        counts[r.category] += 1
    return counts

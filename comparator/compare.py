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


def category_counts(rows: list[Comparison]) -> dict[str, int]:
    counts = {k: 0 for k in CATEGORY_LABELS}
    for r in rows:
        counts[r.category] += 1
    return counts

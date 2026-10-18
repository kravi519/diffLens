"""Keep every comparison run on disk so earlier runs can be reviewed, reopened and downloaded.

Each run is a folder under .work/history/<run id>/ with two files:
  * summary.json  - the headline numbers, read when listing runs (small and fast);
  * run.json.gz   - both RunResults in full (every test, output, message, stack trace and build log),
                    read only when one run is opened or downloaded.

Only the newest MAX_RUNS runs are kept. The folder lives on the app server's disk: on Streamlit Community
Cloud it is cleared whenever the app restarts or redeploys.
"""

from __future__ import annotations

import gzip
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from .compare import Comparison, category_counts, compare
from .java_runner import WORK_DIR, RunResult, TestCase

HISTORY_DIR = WORK_DIR / "history"
MAX_RUNS = 50
SIDES = ("legacy", "newgen")


@dataclass
class RunRecord:
    """One stored run: when it ran, where each side's code came from, and both results."""
    run_id: str
    started: datetime
    sources: dict[str, dict[str, str]]  # side -> {"origin": ..., "detail": ...}
    results: dict[str, RunResult]

    @property
    def rows(self) -> list[Comparison]:
        return compare(self.results["legacy"], self.results["newgen"])


def _summary(record: RunRecord, rows: list[Comparison]) -> dict:
    counts = category_counts(rows)
    return {
        "run_id": record.run_id,
        "started": record.started.isoformat(timespec="seconds"),
        "duration": max(r.duration for r in record.results.values()),
        "cases": len(rows),
        "categories": counts,
        "sources": record.sources,
        "sides": {side: {"ok": r.ok, "stage": r.stage, "error": r.error, "duration": r.duration, **r.counts()}
                  for side, r in record.results.items()},
    }


def save_run(results: dict[str, RunResult], sources: dict, rows: list[Comparison] | None = None,
             started: datetime | None = None) -> str:
    """Store a finished run and return its id. `sources` maps side -> SourceResult (or a dict)."""
    started = started or datetime.now()
    run_id = started.strftime("%Y%m%d-%H%M%S-%f")
    record = RunRecord(
        run_id=run_id,
        started=started,
        sources={side: s if isinstance(s, dict) else
                 {"origin": s.origin, "detail": s.detail, "root": str(s.root)} for side, s in sources.items()},
        results=results,
    )
    rows = rows if rows is not None else record.rows
    folder = HISTORY_DIR / run_id
    tmp = folder.with_name(run_id + ".part")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    full = {"run_id": run_id, "started": record.started.isoformat(), "sources": record.sources,
            "results": {side: asdict(r) for side, r in results.items()}}
    with gzip.open(tmp / "run.json.gz", "wt", encoding="utf-8") as f:
        json.dump(full, f)
    (tmp / "summary.json").write_text(json.dumps(_summary(record, rows)), encoding="utf-8")
    tmp.rename(folder)  # a run appears in the list only once both files are complete
    _prune()
    return run_id


def _prune() -> None:
    runs = sorted(p for p in HISTORY_DIR.iterdir() if p.is_dir() and not p.name.endswith(".part"))
    for old in runs[:-MAX_RUNS]:
        shutil.rmtree(old, ignore_errors=True)


def list_runs() -> list[dict]:
    """Summaries of the stored runs, newest first."""
    if not HISTORY_DIR.exists():
        return []
    summaries = []
    for folder in sorted(HISTORY_DIR.iterdir(), reverse=True):
        summary = folder / "summary.json"
        if folder.is_dir() and summary.exists():
            try:
                summaries.append(json.loads(summary.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue  # skip a damaged entry rather than hide the whole history
    return summaries


def load_run(run_id: str) -> RunRecord:
    """The full stored run, with RunResult and TestCase objects rebuilt."""
    with gzip.open(HISTORY_DIR / run_id / "run.json.gz", "rt", encoding="utf-8") as f:
        data = json.load(f)
    results = {}
    for side, r in data["results"].items():
        tests = [TestCase(**t) for t in r.pop("tests")]
        results[side] = RunResult(tests=tests, **r)
    return RunRecord(run_id=data["run_id"], started=datetime.fromisoformat(data["started"]),
                     sources=data["sources"], results=results)


def delete_run(run_id: str) -> None:
    shutil.rmtree(HISTORY_DIR / run_id, ignore_errors=True)

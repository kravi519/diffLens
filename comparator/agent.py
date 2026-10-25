"""Claude agent that runs the shared test suite against both code bases and explains the differences.

The agent drives the work through tools: it runs each suite, pulls the comparison, reads the
source of both code bases to find the root cause of every behavioural difference, and finishes
with a markdown migration report.
"""

from __future__ import annotations

import json
from typing import Callable

import anthropic
from anthropic import beta_tool

from .compare import CATEGORY_LABELS, SAME, Comparison, category_counts, compare
from .java_runner import ProjectConfig, RunResult, run_suite

MODEL = "claude-haiku-5-5"
MAX_FILE_CHARS = 60_000
SOURCE_SUFFIXES = {".java", ".kt", ".xml", ".properties", ".yml", ".yaml", ".gradle", ".kts"}

SYSTEM_PROMPT = """\
You are a Java migration test analyst. A team is migrating a legacy Java code base to a new-generation \
Java code base. The same test cases are run against both, and your job is to explain where and why \
their behaviour differs.

Work through it like this:
1. Run the test suite on both code bases with run_test_suite ("legacy" and "newgen").
2. Call compare_results to see every test whose outcome differs.
3. For each regression, fix or other change, use get_test_details and read the relevant source in \
both code bases until you can name the root cause. Point at the exact method and the code change \
responsible. Do not guess when you can read the code.
4. If a code base failed to build, explain the compile errors instead.

Finish with a markdown report with these sections:
## Verdict - one or two sentences: is the new gen code safe to ship as-is?
## Regressions - per test: what broke, root cause (file + method), and a suggested fix.
## Fixed in new gen - per test: what the new code does differently.
## Other differences - status changes, missing tests, notable timing differences.
## Recommendations - a short prioritized list.
Keep it concise and specific; quote short code snippets where they make the cause obvious."""


class ComparisonAgent:
    def __init__(self, legacy: ProjectConfig, newgen: ProjectConfig, client: anthropic.Anthropic | None = None,
                 results: dict[str, RunResult] | None = None):
        """results: runs that already exist (e.g. from the UI); run_test_suite reuses them instead of rebuilding."""
        self.configs = {"legacy": legacy, "newgen": newgen}
        self.results: dict[str, RunResult] = dict(results or {})
        self.client = client or anthropic.Anthropic()

    # ---- helpers used by the tools -------------------------------------------------------

    def _config(self, codebase: str) -> ProjectConfig:
        if codebase not in self.configs:
            raise ValueError('codebase must be "legacy" or "newgen"')
        return self.configs[codebase]

    def comparison(self) -> list[Comparison]:
        return compare(self.results["legacy"], self.results["newgen"])

    def _tools(self) -> list:
        agent = self

        @beta_tool
        def run_test_suite(codebase: str) -> str:
            """Build the code base and run the shared JUnit test suite against it. Takes a while.

            Args:
                codebase: Which code base to test: "legacy" or "newgen".
            """
            config = agent._config(codebase)
            result = agent.results.get(codebase) or run_suite(config)
            agent.results[codebase] = result
            summary = {
                "codebase": codebase,
                "ran": result.ok,
                "stage": result.stage,
                "error": result.error,
                "counts": result.counts(),
                "duration_seconds": round(result.duration, 2),
            }
            if not result.ok:
                summary["build_log_tail"] = result.log[-6000:]
            return json.dumps(summary, indent=2)

        @beta_tool
        def compare_results() -> str:
            """Compare the latest legacy and newgen runs test by test. Returns only tests whose outcome differs,
            plus category counts. Both suites must have been run first."""
            missing = [c for c in ("legacy", "newgen") if c not in agent.results]
            if missing:
                return f"Run the test suite first for: {', '.join(missing)}"
            rows = agent.comparison()
            diffs = [
                {
                    "test_id": r.test_id,
                    "display_name": r.display_name,
                    "category": r.category,
                    "legacy_status": r.legacy_status,
                    "newgen_status": r.newgen_status,
                    "legacy_message": r.legacy.message if r.legacy else None,
                    "newgen_message": r.newgen.message if r.newgen else None,
                }
                for r in rows
                if r.category != SAME
            ]
            return json.dumps({"category_counts": category_counts(rows), "differences": diffs}, indent=2)

        @beta_tool
        def get_test_details(test_id: str) -> str:
            """Get the full failure message, stack trace and output of one test in both code bases.

            Args:
                test_id: Test id as returned by compare_results, e.g. "com.example.FooTest#bar()".
            """
            out = {}
            for codebase, result in agent.results.items():
                match = next((t for t in result.tests if t.key == test_id), None)
                out[codebase] = None if match is None else {
                    "status": match.status,
                    "time_seconds": match.time,
                    "message": match.message,
                    "stack_trace": match.details[:8000],
                    "stdout": match.stdout[:4000],
                }
            return json.dumps(out, indent=2)

        @beta_tool
        def list_source_files(codebase: str) -> str:
            """List source and build files of a code base, relative to its project root.

            Args:
                codebase: "legacy" or "newgen".
            """
            root = agent._config(codebase).root.resolve()
            files = [
                p.relative_to(root).as_posix()
                for p in sorted(root.rglob("*"))
                if p.is_file() and p.suffix in SOURCE_SUFFIXES
                and not any(part in {"target", "build", ".git", ".gradle"} for part in p.relative_to(root).parts)
            ]
            return "\n".join(files[:2000]) or "(no source files found)"

        @beta_tool
        def read_source_file(codebase: str, path: str) -> str:
            """Read one file of a code base.

            Args:
                codebase: "legacy" or "newgen".
                path: File path relative to the project root, as listed by list_source_files.
            """
            root = agent._config(codebase).root.resolve()
            target = (root / path).resolve()
            if not target.is_relative_to(root):
                return "Error: path is outside the project root."
            if not target.is_file():
                return f"Error: {path} does not exist."
            text = target.read_text(encoding="utf-8", errors="replace")
            if len(text) > MAX_FILE_CHARS:
                text = text[:MAX_FILE_CHARS] + f"\n... [truncated, file is {len(text)} chars]"
            numbered = "\n".join(f"{i:5d}  {line}" for i, line in enumerate(text.splitlines(), 1))
            return numbered

        return [run_test_suite, compare_results, get_test_details, list_source_files, read_source_file]

    # ---- main loop -----------------------------------------------------------------------

    def run(self, on_event: Callable[[str, str], None] | None = None) -> str:
        """Run the agent to completion and return its markdown report.

        on_event(kind, text) is called as the agent works; kind is "tool" or "text".
        """
        emit = on_event or (lambda kind, text: None)
        legacy, newgen = self.configs["legacy"], self.configs["newgen"]
        task = (
            "Compare the legacy and new-gen code bases using the shared test suite.\n"
            f"Legacy project root: {legacy.root} (build: {legacy.build_tool})\n"
            f"New-gen project root: {newgen.root} (build: {newgen.build_tool})\n"
            f"Category meanings: {json.dumps(CATEGORY_LABELS)}"
        )

        runner = self.client.beta.messages.tool_runner(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            tools=self._tools(),
            messages=[{"role": "user", "content": task}],
        )

        final = None
        for message in runner:
            final = message
            for block in message.content:
                if block.type == "tool_use":
                    args = ", ".join(f"{k}={v!r}" for k, v in (block.input or {}).items())
                    emit("tool", f"{block.name}({args})")
                elif block.type == "text" and block.text.strip() and message.stop_reason == "tool_use":
                    emit("text", block.text)

        if final is None:
            return "The agent returned no response."
        if final.stop_reason == "refusal":
            return "The model declined to complete this analysis."
        report = "".join(b.text for b in final.content if b.type == "text").strip()
        if final.stop_reason == "max_tokens":
            report += "\n\n_(Report truncated: the response hit max_tokens.)_"
        return report or "The agent finished without writing a report."

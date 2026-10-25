"""Run history page: every saved comparison run, with its numbers, report downloads and an option to reopen it."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from comparator.compare import FIXED, OUTPUT_DIFF, REGRESSION, SAME
from comparator.history import MAX_RUNS, delete_run, list_runs, load_run
from comparator.report import excel_report, html_report, report_name
from comparator.source import SourceResult

SIDE_NAMES = {"legacy": "Legacy", "newgen": "New gen"}


@st.cache_data(show_spinner=False, max_entries=10)
def excel_for(run_id: str) -> bytes:
    record = load_run(run_id)
    return excel_report(record.started, record.sources, record.results, record.rows)


@st.cache_data(show_spinner=False, max_entries=10)
def html_for(run_id: str) -> str:
    record = load_run(run_id)
    return html_report(record.started, record.sources, record.results, record.rows)


def pass_rate(side: dict) -> float | None:
    return side["passed"] / side["total"] * 100 if side.get("total") else None


def source_text(source: dict) -> str:
    origin = {"github": "GitHub", "cached": "GitHub (cached)", "local": "Local", "fallback": "Fallback"}
    return origin.get(source.get("origin", ""), source.get("origin", ""))


def status_text(run: dict) -> str:
    stopped = [f"{SIDE_NAMES[s]} stopped at {d['stage']}" for s, d in run["sides"].items() if not d["ok"]]
    return "; ".join(stopped) or "Completed"


def open_in_comparison(run_id: str) -> None:
    """Load a stored run into the session so the Comparison page shows it like a fresh run."""
    record = load_run(run_id)
    st.session_state.results = record.results
    st.session_state.comparison = record.rows
    st.session_state.run_started = record.started
    st.session_state.run_id = record.run_id
    st.session_state.opened_run = record.run_id
    st.session_state.ai_report = None
    st.session_state.ai_fixes = []
    st.session_state.run_seconds = None  # the time of the run was not kept with the history record
    st.session_state.sources = {
        side: SourceResult(side, Path(s.get("root", "")), s.get("origin", ""), s.get("detail", ""))
        for side, s in record.sources.items()}


# ---------------------------------------------------------------- page

st.title(":material/history: Run history")
st.caption(f"Every comparison run is saved here automatically (the newest {MAX_RUNS} are kept). Select a run to "
           "see its numbers, download its full test report, or reopen it on the Comparison page.")

runs = list_runs()
if not runs:
    st.info("No runs yet. Click **Compare** in the left panel of the Comparison page; each run is saved here.",
            icon=":material/history_toggle_off:")
    st.page_link("app_pages/comparison.py", label="Go to Comparison", icon=":material/compare_arrows:")
    st.stop()

table = pd.DataFrame([{
    "Run": datetime.fromisoformat(r["started"]),
    "Status": status_text(r),
    "Cases": r["cases"],
    "Differ": r["cases"] - r["categories"][SAME],
    "Regressions": r["categories"][REGRESSION],
    "Fixed": r["categories"][FIXED],
    "Output differs": r["categories"][OUTPUT_DIFF],
    "Legacy pass rate": pass_rate(r["sides"]["legacy"]),
    "New gen pass rate": pass_rate(r["sides"]["newgen"]),
    "Legacy code": source_text(r["sources"].get("legacy", {})),
    "New gen code": source_text(r["sources"].get("newgen", {})),
    "Run time (s)": r["duration"],
} for r in runs])

event = st.dataframe(
    table, hide_index=True, width="stretch", key="history_table", on_select="rerun", selection_mode="single-row",
    height=min(38 + 35 * len(table), 420), alt="Saved comparison runs, newest first",
    column_config={
        "Run": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm:ss"),
        "Legacy pass rate": st.column_config.NumberColumn(format="%.1f%%"),
        "New gen pass rate": st.column_config.NumberColumn(format="%.1f%%"),
        "Run time (s)": st.column_config.NumberColumn(format="%.1f"),
    })
selected_rows = event.selection.rows
index = selected_rows[0] if selected_rows else 0
if not selected_rows:
    st.caption(":material/touch_app: Showing the latest run. Click a row's checkbox to see another one.")

run = runs[index]
previous = runs[index + 1] if index + 1 < len(runs) else None  # the run just before it, for the change
started = datetime.fromisoformat(run["started"])

st.subheader(f"Run of {started:%Y-%m-%d %H:%M:%S}")
for side, detail in run["sides"].items():
    if not detail["ok"]:
        st.error(f"Stopped at stage `{detail['stage']}`: {detail['error']}", title=f"{SIDE_NAMES[side]} did not run",
                 icon=":material/error:")


def change(key: str) -> int | None:
    if previous is None:
        return None
    if key == "differ":
        return (run["cases"] - run["categories"][SAME]) - (previous["cases"] - previous["categories"][SAME])
    return run["categories"][key] - previous["categories"][key]


tile = {"border": True, "height": "stretch"}
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Input cases", run["cases"], **tile)
k2.metric("Differ", run["cases"] - run["categories"][SAME], change("differ"), delta_color="inverse", **tile)
k3.metric("Regressions", run["categories"][REGRESSION], change(REGRESSION), delta_color="inverse", **tile)
k4.metric("Fixed", run["categories"][FIXED], change(FIXED), **tile)
lp, np_ = pass_rate(run["sides"]["legacy"]), pass_rate(run["sides"]["newgen"])
k5.metric("Pass rate (legacy → new gen)", f"{lp or 0:.1f}% → {np_ or 0:.1f}%", **tile)
st.caption("Changes are against the run before this one." if previous else "This is the oldest saved run.")

with st.container(border=True):
    for side in ("legacy", "newgen"):
        source = run["sources"].get(side, {})
        st.markdown(f"**{SIDE_NAMES[side]} code:** {source_text(source)} · `{source.get('detail', '')}`")

with st.container(horizontal=True, gap="small", vertical_alignment="center"):
    run_id = run["run_id"]
    st.download_button("Excel report", lambda: excel_for(run_id), report_name(started, "xlsx"),
                       icon=":material/table_view:", type="primary", on_click="ignore",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       help="Every case with both outputs, root causes, failures with stack traces, build logs")
    st.download_button("HTML report", lambda: html_for(run_id), report_name(started, "html"),
                       icon=":material/description:", on_click="ignore", mime="text/html",
                       help="The same report as one web page: open, print or email it")
    if st.button("Open in Comparison", icon=":material/open_in_new:"):
        open_in_comparison(run_id)
        st.switch_page("app_pages/comparison.py")
    if st.button("Delete run", icon=":material/delete:", type="tertiary"):
        delete_run(run_id)
        st.toast(f"Deleted the run of {started:%Y-%m-%d %H:%M:%S}", icon=":material/delete:")
        st.rerun()

st.caption(":material/info: Runs are saved on the app server. On Streamlit Community Cloud the history is cleared "
           "when the app restarts or redeploys, so download reports you want to keep.")

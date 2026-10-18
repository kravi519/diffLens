"""Input files page: pick any shared input file in the left panel and read it in a readable layout.

The case file (pacs008.csv) shows every input case with the last run's results; a message (XML) shows
its fields with plain names, the cases that send it, and how it differs from the valid baseline.
"""

from __future__ import annotations

import difflib
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from comparator.compare import CATEGORY_LABELS, compare
from comparator.input_files import column_label, read_csv, show_value, xml_fields

ROOT = Path(__file__).resolve().parent.parent  # project root (this page lives in app_pages/)
INPUTS_DIR = ROOT / "sample" / "inputs"  # the same directory the Comparison page uses
MESSAGES_DIR = INPUTS_DIR / "pacs008"  # the "files" column of a case file is relative to this folder
BULK_DIR = MESSAGES_DIR / "bulk"
BASELINE_XML = INPUTS_DIR / "pacs008" / "p8_01_valid.xml"
NULL_NOTE = "∅ null is an empty field, `\"\"` an empty string."


@st.cache_data(show_spinner=False, max_entries=200)
def load_text(path: str, modified: float) -> str:
    return Path(path).read_text(encoding="utf-8")


@st.cache_data(show_spinner=False, max_entries=20)
def load_csv(path: str, modified: float) -> tuple[list[str], list[list[str | None]]]:
    return read_csv(Path(path))


def last_run_by_case() -> dict:
    """Comparison row per input case from the last run on the Comparison page, if any."""
    results = st.session_state.get("results")
    if not results or len(results) < 2:
        return {}
    rows = st.session_state.get("comparison") or compare(results["legacy"], results["newgen"])
    return {row.test_id: row for row in rows}


def cases_table(header: list[str], rows: list[list[str | None]], runs: dict) -> pd.DataFrame:
    """Cases as a table: case, result, what it tests, the inputs, expected, then both actual outputs."""
    table = pd.DataFrame([[show_value(v) for v in row] for row in rows], columns=[column_label(h) for h in header])
    inputs_cols = [c for c in table.columns if c not in ("Case", "Edge case", "Expected")]
    order = ["Case"] + (["Edge case"] if "Edge case" in table else []) + inputs_cols + ["Expected"]
    if runs:
        matched = [runs.get(row[0]) for row in rows]
        table["Result"] = [CATEGORY_LABELS[m.category] if m else "— not run" for m in matched]
        table["Legacy output"] = [m.legacy_output if m else None for m in matched]
        table["New gen output"] = [m.newgen_output if m else None for m in matched]
        order = ["Case", "Result"] + order[1:] + ["Legacy output", "New gen output"]
    if "expected" in header:  # bulk cases have no expected result: they are only compared between the sides
        col = header.index("expected")
        table["Expected"] = [show_value(r[col]) if r[col] is not None else "— compared only" for r in rows]
    return table[order]


def show_cases(table: pd.DataFrame, alt: str) -> None:
    st.dataframe(table, hide_index=True, width="stretch", alt=alt, height=min(38 + 35 * len(table), 560),
                 column_config={"Edge case": st.column_config.TextColumn(width="medium")})


# ---------------------------------------------------------------- left panel: file picker

files = sorted(INPUTS_DIR.rglob("*.csv")) + sorted(INPUTS_DIR.rglob("*.xml"))
if not files:
    st.warning(f"No input files found in `{INPUTS_DIR}`.", icon=":material/folder_off:")
    st.stop()

# Message (relative to pacs008/) -> the cases that send it, from every case file (exact and bulk).
case_header: list[str] = []
used_by: dict[str, list[list[str | None]]] = {}
for csv_file in (f for f in files if f.suffix == ".csv"):
    header, rows = load_csv(str(csv_file), csv_file.stat().st_mtime)
    if "files" not in header:
        continue
    case_header = case_header or header
    for row in rows:
        for name in (row[header.index("files")] or "").split(";"):
            used_by.setdefault(name.strip(), []).append(row)
desc_col = case_header.index("description") if "description" in case_header else None
runs = last_run_by_case()


def message_key(path: Path) -> str:
    return path.relative_to(MESSAGES_DIR).as_posix() if path.is_relative_to(MESSAGES_DIR) else path.name


def file_label(rel: str) -> str:
    """'pacs008/p8_13_invalid_uetr.xml' -> 'p8_13_invalid_uetr.xml · UETR is not a UUID'."""
    path = INPUTS_DIR / rel
    rows = used_by.get(message_key(path)) if path.suffix == ".xml" else None
    if rows and desc_col is not None and len(rows) == 1 and rows[0][desc_col]:
        return f"{path.name} · {rows[0][desc_col]}"
    return path.name


KINDS = {
    "Test cases": lambda f: f.suffix == ".csv",
    "Messages": lambda f: f.suffix == ".xml" and not f.is_relative_to(BULK_DIR),
    "Bulk": lambda f: f.suffix == ".xml" and f.is_relative_to(BULK_DIR),
}
st.sidebar.header(":material/folder_open: Input files")
kind = st.sidebar.segmented_control(
    "File type", list(KINDS), default="Test cases", key="input_file_kind", width="stretch",
    help="Bulk: generated messages that vary many fields at once (tools/generate_bulk_inputs.py).")
shown = [f for f in files if KINDS.get(kind or "Test cases")(f)] or files
rel_paths = [f.relative_to(INPUTS_DIR).as_posix() for f in shown]
selected = st.sidebar.selectbox(
    "Open file", rel_paths, format_func=file_label, key="input_file",
    help="Type to search by file name or edge case.")
st.sidebar.caption(f"{len(rel_paths)} of {len(files)} files in `sample/inputs`")

# ---------------------------------------------------------------- selected file

path = INPUTS_DIR / selected
stat = path.stat()
text = load_text(str(path), stat.st_mtime)

st.title(f":material/description: {path.name}")
st.caption(f"`sample/inputs/{selected}` · {stat.st_size:,} bytes · "
           f"modified {datetime.fromtimestamp(stat.st_mtime):%Y-%m-%d %H:%M}")

if path.suffix == ".csv":
    header, rows = load_csv(str(path), stat.st_mtime)
    view = st.segmented_control("View", ["Readable", "Raw file"], default="Readable", key="csv_view",
                                label_visibility="collapsed")
    if view == "Raw file":
        st.code(text or "(empty file)", language="csv", line_numbers=True)
    elif not header:
        st.info("This file is empty.", icon=":material/draft:")
    else:
        bulk = "expected" in header and all(r[header.index("expected")] is None for r in rows)
        st.caption("Generated bulk cases: none has an expected result, so each one only checks that legacy and "
                   "new gen return the same output. Regenerate with `python tools/generate_bulk_inputs.py`."
                   if bulk else "Every row is fed to both the legacy and the new-gen test suite, so a difference "
                   "in their results is a difference in behaviour.")
        table = cases_table(header, rows, runs)
        differs = ~table["Result"].isin([CATEGORY_LABELS["same"], "— not run"]) if runs else None
        messages = {name.strip() for r in rows if "files" in header
                    for name in (r[header.index("files")] or "").split(";")}
        k1, k2, k3 = st.columns(3)
        k1.metric("Input cases", len(rows), border=True)
        k2.metric("pacs.008 messages", len(messages), border=True)
        k3.metric("Last run", f"{differs.sum()} differ" if runs else "Not run yet", border=True)
        if runs and st.toggle("Only show cases whose result differs between legacy and new gen"):
            table = table[differs]
        if not runs:
            st.caption(":material/info: Run the tests on the Comparison page to see each case's result here.")
        if table.empty:
            st.success("Every case behaves the same on both sides.", icon=":material/check_circle:")
        else:
            show_cases(table, f"Input cases in {path.name}")
        st.caption(f"{NULL_NOTE} Open a message under **Messages** or **Bulk** in the left panel to read it.")
else:
    cases = used_by.get(message_key(path), [])
    if cases:
        with st.container(border=True):
            st.markdown(f":material/dataset: **Used by {len(cases)} test case{'s' if len(cases) > 1 else ''}**")
            show_cases(cases_table(case_header, cases, runs), f"Test cases that send {path.name}")

    view = st.segmented_control("View", ["Readable", "Changes vs valid baseline", "Raw file"], default="Readable",
                                key="xml_view", label_visibility="collapsed")
    if view == "Changes vs valid baseline":
        if path == BASELINE_XML:
            st.caption("This is the valid baseline message every other message is derived from.")
        else:
            baseline = load_text(str(BASELINE_XML), BASELINE_XML.stat().st_mtime) if BASELINE_XML.exists() else ""
            diff = difflib.unified_diff(baseline.splitlines(), text.splitlines(), BASELINE_XML.name, path.name,
                                        lineterm="", n=1)
            st.code("\n".join(diff) or "(identical to the baseline)", language="diff")
    elif view == "Raw file":
        st.code(text or "(empty file)", language="xml", line_numbers=True)
    else:
        try:
            fields = xml_fields(text)
        except ET.ParseError as e:
            st.warning(f"This message is not well-formed XML ({e}), which is what its test case checks. "
                       "The raw file is shown instead.", title="Cannot show a readable view",
                       icon=":material/warning:")
            st.code(text or "(empty file)", language="xml", line_numbers=True)
        else:
            for section in dict.fromkeys(section for section, _, _ in fields):
                st.markdown(f"##### {section}")
                st.table(pd.DataFrame([(f, v or "—") for s, f, v in fields if s == section],
                                      columns=["Field", "Value"]).set_index("Field"),
                         alt=f"{section} fields of {path.name}")

"""Input cases page: every input row fed to both code bases, and the pacs.008 messages behind them."""

from __future__ import annotations

import difflib
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from comparator.compare import CATEGORY_LABELS, compare

ROOT = Path(__file__).resolve().parent.parent  # project root (this page lives in app_pages/)
DEFAULT_INPUTS = ROOT / "sample" / "inputs"
PACS_DIR = "pacs008"
BASELINE_XML = "p8_01_valid.xml"

# File name -> (title, method under test, what the inputs mean). Unknown CSV files are still listed.
SUITES = {
    "pacs008.csv": ("pacs.008", "Pacs008Controller.submit(xml)",
                    "Each case posts one or more ISO 20022 messages from `pacs008/` (separated by `;`) to a "
                    "fresh in-memory database and records the last HTTP-style response."),
}
COLUMN_LABELS = {"case": "Case", "expected": "Expected", "description": "Edge case", "files": "Messages"}


def split_csv_line(line: str) -> list[str | None]:
    """Split one line like JUnit's @CsvFileSource: unquoted empty -> null, quoted "" -> empty string."""
    fields: list[str | None] = []
    buf: list[str] = []
    quoted = in_quotes = False
    i = 0
    while i < len(line):
        ch = line[i]
        if in_quotes:
            if ch == '"' and i + 1 < len(line) and line[i + 1] == '"':
                buf.append('"')
                i += 1
            elif ch == '"':
                in_quotes = False
            else:
                buf.append(ch)
        elif ch == '"':
            in_quotes = quoted = True
        elif ch == ",":
            fields.append(_field(buf, quoted))
            buf, quoted = [], False
        else:
            buf.append(ch)
        i += 1
    fields.append(_field(buf, quoted))
    return fields


def _field(buf: list[str], quoted: bool) -> str | None:
    text = "".join(buf)
    if quoted:
        return text
    text = text.strip()
    return text or None


def column_label(name: str) -> str:
    """CSV header to a sentence-case column title, e.g. firstName -> First name."""
    if name in COLUMN_LABELS:
        return COLUMN_LABELS[name]
    words = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).lower()
    return words[:1].upper() + words[1:]


def show_value(value: str | None) -> str:
    """Make null, empty and padded values visible in the table."""
    if value is None:
        return "∅ null"
    if value == "" or value != value.strip():
        return f'"{value}"'
    return value


@st.cache_data(show_spinner=False)
def read_suite(path: str, modified: float) -> tuple[list[str], list[list[str | None]]]:
    lines = [line for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [split_csv_line(line) for line in lines]
    return rows[0], rows[1:]


def last_run_by_case() -> dict:
    """Comparison row per input case from the last run on the Comparison page, if any."""
    results = st.session_state.get("results")
    if not results or len(results) < 2:
        return {}
    return {row.test_id: row for row in compare(results["legacy"], results["newgen"])}


# ---------------------------------------------------------------- page

st.title(":material/dataset: Input cases")
st.caption("Every row below is fed to both the legacy and the new-gen test suite. Both sides read the same "
           "files, so a difference in their results is a difference in behaviour.")

inputs_dir = Path(st.sidebar.text_input(
    "Shared input data dir", st.session_state.get("inputs_dir", str(DEFAULT_INPUTS)),
    help="The same directory the Comparison page uses."))
st.session_state.inputs_dir = str(inputs_dir)

csv_files = sorted(inputs_dir.glob("*.csv"), key=lambda p: (list(SUITES).index(p.name) if p.name in SUITES
                                                             else len(SUITES), p.name))
if not csv_files:
    st.warning(f"No CSV input files found in `{inputs_dir}`.", icon=":material/folder_off:")
    st.stop()

suites = {p.name: read_suite(str(p), p.stat().st_mtime) for p in csv_files}
runs = last_run_by_case()
total_cases = sum(len(rows) for _, rows in suites.values())
xml_count = len(list((inputs_dir / PACS_DIR).glob("*.xml")))

k1, k2, k3, k4 = st.columns(4)
k1.metric("Test suites", len(suites), border=True, height="stretch")
k2.metric("Input cases", total_cases, border=True, height="stretch")
k3.metric("pacs.008 messages", xml_count, border=True, height="stretch")
if runs:
    differ = sum(1 for r in runs.values() if r.category != "same")
    k4.metric("Last run", f"{differ} differ", border=True, height="stretch")
else:
    k4.metric("Last run", "Not run yet", border=True, height="stretch")

if runs:
    only_diffs = st.toggle("Only show cases whose result differs between legacy and new gen")
else:
    only_diffs = False
    st.caption(":material/info: Run the tests on the Comparison page to see each case's result here.")

tabs = st.tabs([f"{SUITES.get(name, (Path(name).stem,))[0]} · {len(rows)}" for name, (_, rows) in suites.items()])
for tab, (name, (header, rows)) in zip(tabs, suites.items()):
    with tab:
        title, method, about = SUITES.get(name, (Path(name).stem, "", ""))
        if method:
            st.markdown(f"`{method}`")
        if about:
            st.caption(about)

        table = pd.DataFrame([[show_value(v) for v in row] for row in rows],
                             columns=[column_label(h) for h in header])
        # Order: case, result, what it tests, the inputs, then expected vs actual.
        inputs_cols = [c for c in table.columns if c not in ("Case", "Edge case", "Expected")]
        order = ["Case"] + (["Edge case"] if "Edge case" in table else []) + inputs_cols + ["Expected"]
        if runs:
            matched = [runs.get(row[0]) for row in rows]
            table["Result"] = [CATEGORY_LABELS[m.category] if m else "— not run" for m in matched]
            table["Legacy output"] = [m.legacy_output if m else None for m in matched]
            table["New gen output"] = [m.newgen_output if m else None for m in matched]
            order = ["Case", "Result"] + order[1:] + ["Legacy output", "New gen output"]
            if only_diffs:
                table = table[[bool(m) and m.category != "same" for m in matched]]
        if table.empty:
            st.success("Every case in this suite behaves the same on both sides.", icon=":material/check_circle:")
        else:
            st.dataframe(table[order], hide_index=True, width="stretch", alt=f"{title} input cases",
                         height=min(36 + 35 * len(table), 560),
                         column_config={"Edge case": st.column_config.TextColumn(width="medium")})
        st.caption(f"`{inputs_dir / name}` · ∅ null is an empty field, `\"\"` an empty string.")

        if name != "pacs008.csv":
            continue

        st.markdown("##### Messages behind each case")
        by_id = {row[0]: row for row in rows}
        files_col = header.index("files")
        desc_col = header.index("description") if "description" in header else None
        case_id = st.selectbox(
            "Case", list(by_id),
            format_func=lambda c: f"{c} — {by_id[c][desc_col]}" if desc_col is not None else c)
        baseline = (inputs_dir / PACS_DIR / BASELINE_XML)
        baseline_text = baseline.read_text(encoding="utf-8") if baseline.exists() else ""

        for file_name in (by_id[case_id][files_col] or "").split(";"):
            file_name = file_name.strip()
            path = inputs_dir / PACS_DIR / file_name
            with st.container(border=True):
                st.markdown(f":material/description: **{file_name}**")
                if not path.exists():
                    st.error(f"`{path}` does not exist.", icon=":material/error:")
                    continue
                text = path.read_text(encoding="utf-8")
                view = st.segmented_control("View", ["Message", "Changes vs valid baseline"],
                                            default="Message", key=f"view-{case_id}-{file_name}",
                                            label_visibility="collapsed")
                if view == "Changes vs valid baseline":
                    if file_name == BASELINE_XML:
                        st.caption("This is the valid baseline message every other case is derived from.")
                    else:
                        diff = difflib.unified_diff(baseline_text.splitlines(), text.splitlines(),
                                                    BASELINE_XML, file_name, lineterm="", n=1)
                        st.code("\n".join(diff) or "(identical to the baseline)", language="diff")
                else:
                    st.code(text or "(empty file)", language="xml", line_numbers=True)

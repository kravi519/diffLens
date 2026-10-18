"""Comparison page: run each code base's tests on the shared input cases and compare the results."""

from __future__ import annotations

import html
import os
import random
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from comparator.compare import (
    CATEGORY_LABELS, CHANGED, FIXED, ONLY_LEGACY, ONLY_NEWGEN, OUTPUT_DIFF, REGRESSION, SAME, Comparison,
    category_counts, compare, difference_causes,
)
from comparator.history import save_run
from comparator.java_runner import ProjectConfig, RunResult, run_suite
from comparator.report import excel_report, html_report, report_name
from comparator.source import CACHED, FALLBACK, GITHUB, SourceResult, resolve_source

HERE = Path(__file__).resolve().parent.parent  # project root (this page lives in app_pages/)
SAMPLE = HERE / "sample"
SIDE_NAMES = {"legacy": "Legacy", "newgen": "New gen"}
# Default GitHub sources (repository URL, branch), shown in the left panel where they can be changed.
LEGACY_REPO = ("https://github.com/kravi519/LegacyCode", "main")
NEWGEN_REPO = ("https://github.com/kravi519/NewGenCode", "main")
# Bundled copies: used when no GitHub URL is given or GitHub cannot be reached.
LEGACY_ROOT = SAMPLE / "legacy"
NEWGEN_ROOT = SAMPLE / "newgen"

STATUS_ICONS = {
    "passed": "✅ passed",
    "failed": "❌ failed",
    "error": "💥 error",
    "skipped": "⏭️ skipped",
    "missing": "— missing",
}

# Donut slices name a role, and the run's palette (TILE_PALETTES) gives each role a colour, so the charts
# change colour with every run too. Roles keep some meaning in every palette: "bad" (failed, regression)
# is always a red tone and "good" (passed, fixed) the palette's main colour. Keys are in display order.
STATUS_SLICES = {
    "passed": ("Passed", "good"),
    "failed": ("Failed", "bad"),
    "error": ("Error", "warn"),
    "skipped": ("Skipped", "neutral"),
}
CATEGORY_SLICES = {
    REGRESSION: ("Regression", "bad"),
    FIXED: ("Fixed", "good"),
    CHANGED: ("Changed", "warn"),
    OUTPUT_DIFF: ("Output differs", "diff"),
    ONLY_LEGACY: ("Only in legacy", "alt1"),
    ONLY_NEWGEN: ("Only in new gen", "alt2"),
    SAME: ("Same", "neutral"),
}
DONUT_SIZE = 140


def slice_color(hex_color: str, dark: bool) -> str:
    """Slice colours are tuned for a light page; on a dark page they are mixed 30% toward white."""
    if not dark:
        return hex_color
    rgb = [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(c + (255 - c) * 0.3):02X}" for c in rgb)


def donut(counts: dict[str, int], slices: dict[str, tuple[str, str]], center: str, center_label: str,
          palette_index: int):
    """Ring of the non-zero counts with the headline in the hole. Returns (chart, legend) or None,
    where legend is a list of (colour, name, count)."""
    roles = TILE_PALETTES[palette_index][3]
    dark = st.context.theme.type == "dark"
    present = [(i, key, name, slice_color(roles[role], dark))
               for i, (key, (name, role)) in enumerate(slices.items()) if counts.get(key, 0)]
    if not present:
        return None
    total = sum(counts[key] for _, key, _, _ in present)
    ink = "#F1F5F9" if dark else "#0F172A"  # textColor from .streamlit/config.toml
    df = pd.DataFrame([
        {"Result": name, "Count": counts[key], "Share": counts[key] / total, "Order": i}
        for i, key, name, _ in present
    ])
    # Ring radius stays a few px inside the plot so the stroke is never clipped at the edges.
    arcs = alt.Chart(df).mark_arc(innerRadius=46, outerRadius=66, padAngle=0.025, cornerRadius=3).encode(
        theta=alt.Theta("Count:Q", stack=True),
        order=alt.Order("Order:Q"),
        color=alt.Color("Result:N", legend=None,
                        scale=alt.Scale(domain=[n for _, _, n, _ in present],
                                        range=[c for _, _, _, c in present])),
        tooltip=[alt.Tooltip("Result:N"), alt.Tooltip("Count:Q"),
                 alt.Tooltip("Share:Q", title="Share", format=".0%")],
    )
    middle = DONUT_SIZE / 2
    headline = alt.Chart(pd.DataFrame({"t": [center]})).mark_text(
        fontSize=18, fontWeight=600, dy=-6, color=ink).encode(text="t:N", x=alt.value(middle), y=alt.value(middle))
    sub = alt.Chart(pd.DataFrame({"t": [center_label]})).mark_text(
        fontSize=10, dy=10, opacity=0.65, color=ink).encode(text="t:N", x=alt.value(middle), y=alt.value(middle))
    chart = (arcs + headline + sub).properties(
        width=DONUT_SIZE, height=DONUT_SIZE, padding={"top": 4, "bottom": 4, "left": 4, "right": 4},
    ).configure_view(stroke=None).configure(background="transparent")  # let the card tint show through
    return chart, [(color, name, counts[key]) for _, key, name, color in present]


# Premium palettes for the KPI tiles, chart cards and donut slices; every run moves on to the next one.
# Each entry: (name, card accent, five tile gradients, donut slice colour per role). Each tile is a
# 135° gradient (start, end) carrying white text, so every start colour is dark enough for small labels
# and every end colour keeps white values readable, in both light and dark mode. Slice colours are 600
# shades for a light page (lightened for dark mode by slice_color); "bad" is a red tone in every palette.
TILE_PALETTES = [
    ("Royal", "#6366F1", [("#1E1B4B", "#4F46E5"), ("#2E1065", "#7C3AED"), ("#172554", "#2563EB"),
                          ("#042F2E", "#0F766E"), ("#0F172A", "#475569")],
     {"good": "#4F46E5", "bad": "#E11D48", "warn": "#D97706", "diff": "#0D9488",
      "alt1": "#0284C7", "alt2": "#9333EA", "neutral": "#64748B"}),
    ("Emerald & gold", "#059669", [("#022C22", "#047857"), ("#422006", "#A16207"), ("#052E16", "#15803D"),
                                   ("#451A03", "#B45309"), ("#042F2E", "#0F766E")],
     {"good": "#059669", "bad": "#DC2626", "warn": "#CA8A04", "diff": "#0E7490",
      "alt1": "#2563EB", "alt2": "#7C3AED", "neutral": "#78716C"}),
    ("Rose & plum", "#DB2777", [("#4A044E", "#A21CAF"), ("#4C0519", "#BE123C"), ("#3B0764", "#7E22CE"),
                                ("#500724", "#BE185D"), ("#1E1B4B", "#6D28D9")],
     {"good": "#7E22CE", "bad": "#E11D48", "warn": "#D97706", "diff": "#0D9488",
      "alt1": "#C026D3", "alt2": "#4F46E5", "neutral": "#78716C"}),
    ("Ocean", "#0284C7", [("#082F49", "#0369A1"), ("#083344", "#0E7490"), ("#042F2E", "#0F766E"),
                          ("#172554", "#1D4ED8"), ("#0C4A6E", "#0284C7")],
     {"good": "#0284C7", "bad": "#F43F5E", "warn": "#D97706", "diff": "#0D9488",
      "alt1": "#6366F1", "alt2": "#7C3AED", "neutral": "#64748B"}),
    ("Midnight & copper", "#EA580C", [("#0F172A", "#334155"), ("#431407", "#C2410C"), ("#1C1917", "#57534E"),
                                      ("#422006", "#B45309"), ("#18181B", "#52525B")],
     {"good": "#1E40AF", "bad": "#B91C1C", "warn": "#EA580C", "diff": "#CA8A04",
      "alt1": "#0E7490", "alt2": "#7C3AED", "neutral": "#57534E"}),
    ("Aurora", "#8B5CF6", [("#312E81", "#0E7490"), ("#4C1D95", "#BE185D"), ("#134E4A", "#4338CA"),
                           ("#831843", "#C2410C"), ("#0C4A6E", "#7C3AED")],
     {"good": "#0891B2", "bad": "#E11D48", "warn": "#D97706", "diff": "#8B5CF6",
      "alt1": "#4338CA", "alt2": "#DB2777", "neutral": "#64748B"}),
]


def next_palette() -> int:
    """Index of the palette for a new run: the one after the last run's (a random one for the first run)."""
    last = st.session_state.get("palette")
    return random.randrange(len(TILE_PALETTES)) if last is None else (last + 1) % len(TILE_PALETTES)


def tile_styles(index: int) -> str:
    """CSS for the keyed KPI tiles (kpi_0..kpi_4) and chart cards (card_0..card_2) in one palette."""
    _, accent, gradients, _ = TILE_PALETTES[index]
    css = [
        """[class*="st-key-kpi_"] { border-radius: 14px; padding: 16px 18px;
             border: 1px solid rgba(255,255,255,.10); transition: background .5s ease, box-shadow .5s ease; }
           [class*="st-key-kpi_"] [data-testid="stMetricLabel"],
           [class*="st-key-kpi_"] [data-testid="stMetricLabel"] p { color: rgba(255,255,255,.86) !important; }
           [class*="st-key-kpi_"] [data-testid="stMetricValue"] { color: #FFFFFF !important; }
           [class*="st-key-kpi_"] [data-testid="stMetricDelta"] { color: #FFFFFF !important;
             background: rgba(255,255,255,.16) !important; }
           [class*="st-key-kpi_"] svg { color: rgba(255,255,255,.86) !important; }""",
        f"""[class*="st-key-card_"] {{ border-top: 3px solid {accent} !important;
             background: linear-gradient(180deg, color-mix(in srgb, {accent} 10%, transparent) 0%, transparent 45%);
             transition: background .5s ease; }}""",
    ]
    for i, (start, end) in enumerate(gradients):
        css.append(f""".st-key-kpi_{i} {{ background: linear-gradient(135deg, {start} 0%, {end} 100%);
             box-shadow: 0 10px 24px -14px {end}; }}""")
    return "<style>" + "\n".join(css) + "</style>"


def donut_card(title: str, icon: str, donut_parts, alt_text: str, footnote: str, key: str) -> None:
    """Bordered card: heading, ring with a vertical legend beside it, one-line footnote.

    The legend is a column next to the ring rather than a row under it, so the card height does not
    depend on the number of slices and the footnotes line up across cards.
    """
    with st.container(border=True, height="stretch", gap="small", key=key):
        st.markdown(f"{icon} **{title}**")
        # Legend sits beside the ring; on narrow cards it wraps below instead of clipping.
        with st.container(horizontal=True, horizontal_alignment="center", vertical_alignment="center",
                          gap="medium"):
            if donut_parts is None:
                st.caption("No results to chart.")
            else:
                chart, legend = donut_parts
                st.altair_chart(chart, theme="streamlit", width="content", alt=alt_text)
                # Legend dots in the exact slice colours (Markdown colour names cannot show palette shades).
                st.html("<div style='display:flex;flex-direction:column;gap:6px;font-size:.875rem'>" + "".join(
                    f"<div><span style='color:{color};font-size:1rem'>&#9679;</span> {html.escape(name)} "
                    f"<b>{count}</b></div>" for color, name, count in legend) + "</div>", width="content")
        st.caption(footnote)


# ---------------------------------------------------------------- configuration

# Fixed build settings: both sides are compiled with javac from these folders inside the project.
SOURCE_DIRS = ["src/main/java"]
TEST_DIRS = ["src/test/java"]
JAVAC_RELEASE = {"legacy": "8", "newgen": ""}
LOCAL_ROOTS = {"legacy": LEGACY_ROOT, "newgen": NEWGEN_ROOT}
INPUTS_DIR = SAMPLE / "inputs"
TIMEOUT = 900  # seconds per suite


def github_form(label: str, title: str, default_repo: tuple[str, str]) -> tuple[dict, st.delta_generator.DeltaGenerator]:
    """Repository and branch/commit fields for one side, plus a slot that shows what the last run used."""
    default_url, default_ref = default_repo
    st.sidebar.subheader(f":material/cloud_download: {title}")
    form = {
        "gh_url": st.sidebar.text_input(
            "Repository", default_url, key=f"{label}_gh_url", placeholder="https://github.com/org/repo",
            help="The project folder is found automatically (the one with src/main/java). To pick one, use "
                 "https://github.com/org/repo/tree/<branch>/<folder>. If GitHub cannot be reached, the "
                 f"bundled copy in sample/{label} is used."),
        "gh_ref": st.sidebar.text_input("Branch, tag or commit", default_ref, key=f"{label}_gh_ref",
                                        placeholder="default branch"),
        "gh_dir": "",
    }
    return form, st.sidebar.container()


legacy_form, legacy_status = github_form("legacy", "Legacy source", LEGACY_REPO)
newgen_form, newgen_status = github_form("newgen", "New-gen source", NEWGEN_REPO)
SOURCE_STATUS = {"legacy": legacy_status, "newgen": newgen_status}


def fetch_source(label: str, form: dict) -> SourceResult:
    return resolve_source(label, form["gh_url"], form["gh_ref"], form["gh_dir"],
                          os.environ.get("GITHUB_TOKEN", ""), True, LOCAL_ROOTS[label])


def build_config(label: str, root: Path) -> ProjectConfig:
    return ProjectConfig(label=label, root=root, build_tool="javac", timeout=TIMEOUT,
                         source_dirs=[root / d for d in SOURCE_DIRS], test_dirs=[root / d for d in TEST_DIRS],
                         input_dirs=[INPUTS_DIR], release=JAVAC_RELEASE[label])


# ---------------------------------------------------------------- actions

st.title(":material/search_insights: DiffLens")
st.caption("Legacy vs new-gen behaviour, input by input: runs each code base's own tests on the same input "
           "cases and shows exactly where the results differ.")

run_clicked = st.button("Run tests", icon=":material/play_arrow:", type="primary")

if run_clicked:
    started = datetime.now()
    forms = {"legacy": legacy_form, "newgen": newgen_form}
    with ThreadPoolExecutor(max_workers=2) as pool:
        if any(f["gh_url"].strip() for f in forms.values()):
            with st.spinner("Getting the code from GitHub…"):
                sources = dict(zip(forms, pool.map(fetch_source, forms, forms.values())))
        else:
            sources = {label: fetch_source(label, form) for label, form in forms.items()}
        configs = [build_config(label, sources[label].root) for label in forms]
        with st.spinner("Building and testing both code bases in parallel…"):
            legacy_result, newgen_result = pool.map(run_suite, configs)
    st.session_state.sources = sources
    st.session_state.results = {"legacy": legacy_result, "newgen": newgen_result}
    st.session_state.comparison = compare(legacy_result, newgen_result)  # once per run, not on every rerun
    st.session_state.run_started = started
    st.session_state.palette = next_palette()  # a new premium tile palette for every run
    st.session_state.opened_run = None  # a fresh run, not one reopened from the history
    try:
        st.session_state.run_id = save_run(st.session_state.results, sources, st.session_state.comparison, started)
    except OSError as e:  # the run is still shown; it just won't appear in the history
        st.toast(f"Could not save this run to the history: {e}", icon=":material/warning:")


def show_source_status(source: SourceResult, slot) -> None:
    """Under a side's fields in the left panel: what the last run loaded (commit, folder) or why GitHub failed."""
    commit = re.search(r"commit ([0-9a-f]{7})", source.detail)
    folder = source.root.name
    with slot:
        if source.origin == GITHUB:
            st.caption(":material/cloud_done: Loaded from GitHub" + (f" · commit `{commit.group(1)}`" if commit else "")
                       + f" · folder `{folder}`")
        elif source.origin == CACHED:
            st.warning(source.detail, title="Using the last downloaded copy", icon=":material/cloud_sync:")
        elif source.origin == FALLBACK:
            st.warning(source.detail, title="GitHub could not be used", icon=":material/cloud_off:")
        else:
            st.caption(f":material/folder: Bundled copy `{source.root}`")


for source in st.session_state.get("sources", {}).values():
    show_source_status(source, SOURCE_STATUS[source.label])


# ---------------------------------------------------------------- results

results: dict[str, RunResult] | None = st.session_state.get("results")
def landing_page() -> None:
    """What the tool does, shown until the first run."""
    st.markdown(
        "Migrating Java code from a **legacy** code base to a **new-gen** one? DiffLens proves both "
        "behave the same. It feeds **the same input cases** to each code base's **own test suite**, "
        "records what the code actually returned for every input, and lines the two runs up case by "
        "case, so you see exactly which behaviour changed, got fixed or broke.")

    st.markdown("##### How it works")
    steps = [
        (":material/input:", "1. Shared input cases",
         "Every case lives once in a CSV file (`sample/inputs/`): a case id, the inputs and the expected "
         "result. Add a row and both sides test it on the next run."),
        (":material/play_circle:", "2. Both sides run",
         "Legacy and new gen are compiled and tested in parallel with their own JUnit suites, which may "
         "use different classes, names and Java versions. Each test records the actual output."),
        (":material/compare_arrows:", "3. Compare by input case",
         "Results are matched on the case id, not the test name, and compared on both pass/fail status "
         "and the actual output. Every difference gets a category."),
    ]
    for col, (icon, title, text) in zip(st.columns(3), steps):
        with col, st.container(border=True, height="stretch"):
            st.markdown(f"{icon} **{title}**")
            st.caption(text)

    st.markdown("##### What the results tell you")
    with st.container(horizontal=True, gap="small"):
        st.badge("Regression: passes on legacy, fails on new gen", icon=":material/arrow_downward:", color="red")
        st.badge("Fixed: fails on legacy, passes on new gen", icon=":material/arrow_upward:", color="green")
        st.badge("Changed: status changed, e.g. failed → error", icon=":material/swap_horiz:", color="yellow")
        st.badge("Output differs: same status, different output", icon=":material/difference:", color="orange")
        st.badge("Only in one run: case tested on one side only", icon=":material/remove:", color="blue")
        st.badge("Same: identical on both sides", icon=":material/check:", color="gray")
    st.caption("After a run you get headline numbers, pass-rate charts for each side, a table of every "
               "difference, side-by-side outputs and stack traces, and the raw build logs.")

    st.markdown("##### Try it with the bundled sample")
    with st.container(border=True):
        st.markdown(":material/account_balance: **pacs.008 payments (CBPR+ SR2025)**")
        st.caption("An MVC pipeline that maps ISO 20022 credit transfer XML, validates CBPR+ business rules, "
                   "converts to a DTO and saves it to an in-memory database. New gen adds SR2025 rules "
                   "and carries one deliberate migration bug.")

    st.info("Click **Run tests** above to compare the two code bases.", icon=":material/lightbulb:")
    st.page_link("app_pages/input_files.py", label="Browse all input cases and messages fed to both sides",
                 icon=":material/folder_open:")


if not results or len(results) < 2:
    landing_page()
    st.stop()

legacy, newgen = results["legacy"], results["newgen"]

for r in (legacy, newgen):
    if not r.ok:
        st.error(f"Stopped at stage `{r.stage}`: {r.error}", title=f"{r.label} did not run",
                 icon=":material/error:")

rows: list[Comparison] = st.session_state.get("comparison") or compare(legacy, newgen)
run_started: datetime = st.session_state.get("run_started") or datetime.now()
report_sources = {label: {"origin": s.origin, "detail": s.detail}
                  for label, s in st.session_state.get("sources", {}).items()}

with st.container(horizontal=True, gap="small", vertical_alignment="center"):
    if st.session_state.get("opened_run"):
        st.badge(f"Reopened from history: run of {run_started:%Y-%m-%d %H:%M:%S}", icon=":material/history:",
                 color="gray")
    # Built only when clicked (on a separate thread), so large reports never slow the page down.
    st.download_button("Excel report", lambda: excel_report(run_started, report_sources, results, rows),
                       report_name(run_started, "xlsx"), icon=":material/table_view:", on_click="ignore",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       help="Every case with both outputs, root causes, failures with stack traces, build logs")
    st.download_button("HTML report", lambda: html_report(run_started, report_sources, results, rows),
                       report_name(run_started, "html"), icon=":material/description:", on_click="ignore",
                       mime="text/html", help="The same report as one web page: open, print or email it")
    st.page_link("app_pages/run_history.py", label="Run history", icon=":material/history:")
counts = category_counts(rows)
lc, nc = legacy.counts(), newgen.counts()
diff_total = len(rows) - counts[SAME]


def bulk_note(c: dict[str, int]) -> str:
    """Bulk cases assert nothing, so they are left out of pass/fail and only mentioned."""
    return f" · +{c['bulk']} bulk compared" if c.get("bulk") else ""


def pass_rate(c: dict[str, int]) -> float:
    return c["passed"] / c["total"] * 100 if c["total"] else 0.0


# KPI row: every tile has the same parts (label, value, one pill) so the row lines up. Context pills
# are gray with no arrow; only the new-gen pass rate carries a real up/down change.
palette = st.session_state.get("palette")
if palette is None:  # e.g. the first page load after an app restart
    palette = st.session_state.palette = next_palette()
st.html(tile_styles(palette))
tiles = [
    ("Input cases", len(rows), f"{diff_total} differ", {}),
    ("Regressions", counts[REGRESSION], "pass → fail", {}),
    ("Fixed", counts[FIXED], "fail → pass", {}),
    ("Legacy pass rate", f"{pass_rate(lc):.1f}%", f"{lc['passed']} of {lc['total']}", {}),
    ("New gen pass rate", f"{pass_rate(nc):.1f}%", f"{pass_rate(nc) - pass_rate(lc):+.1f} pts",
     {"delta_arrow": "auto", "help": "Change in percentage points vs legacy"}),
]
for i, (column, (label, value, pill, extra)) in enumerate(zip(st.columns(5), tiles)):
    with column.container(key=f"kpi_{i}", height="stretch"):
        st.metric(label, value, pill, **{"delta_color": "off", "delta_arrow": "off", "height": "stretch", **extra})

# Donut cards
c1, c2, c3 = st.columns(3)
with c1:
    donut_card("Legacy", ":material/history:", donut(lc, STATUS_SLICES, f"{pass_rate(lc):.0f}%", "pass rate", palette),
               "Legacy test outcomes",
               f"{lc['passed']} of {lc['total']} passed{bulk_note(lc)} · run time {legacy.duration:.1f}s", "card_0")
with c2:
    donut_card("New gen", ":material/rocket_launch:",
               donut(nc, STATUS_SLICES, f"{pass_rate(nc):.0f}%", "pass rate", palette), "New-gen test outcomes",
               f"{nc['passed']} of {nc['total']} passed{bulk_note(nc)} · run time {newgen.duration:.1f}s", "card_1")
with c3:
    donut_card("Comparison", ":material/compare_arrows:",
               donut(counts, CATEGORY_SLICES, str(diff_total), "differ" if diff_total != 1 else "differs",
                     palette),
               "Comparison of results by input case", f"{diff_total} of {len(rows)} input cases differ", "card_2")


def to_frame(items: list[Comparison]) -> pd.DataFrame:
    def test_name(tc) -> str:
        return f"{tc.suite.rsplit('.', 1)[-1]}.{tc.name.split('(', 1)[0]}" if tc else ""

    return pd.DataFrame([
        {
            "Category": CATEGORY_LABELS[r.category],
            "Input case": (r.legacy or r.newgen).case_id,
            "Test": r.display_name,
            "Legacy": STATUS_ICONS[r.legacy_status],
            "New gen": STATUS_ICONS[r.newgen_status],
            "Legacy output": r.legacy_output,
            "New gen output": r.newgen_output,
            "Legacy test": test_name(r.legacy),
            "New gen test": test_name(r.newgen),
            "Legacy (s)": r.legacy.time if r.legacy else None,
            "New gen (s)": r.newgen.time if r.newgen else None,
            "Δ time (s)": r.time_delta,
            "Legacy message": r.legacy.message if r.legacy else "",
            "New gen message": r.newgen.message if r.newgen else "",
            "Test id": r.test_id,
        }
        for r in items
    ])


def show_table(df: pd.DataFrame) -> None:
    st.dataframe(
        df, width="stretch", hide_index=True,
        column_config={
            "Legacy (s)": st.column_config.NumberColumn(format="%.3f"),
            "New gen (s)": st.column_config.NumberColumn(format="%.3f"),
            "Δ time (s)": st.column_config.NumberColumn(format="%+.3f"),
        },
    )


tab_diff, tab_causes, tab_all, tab_detail, tab_logs = st.tabs([
    ":material/difference: Differences", ":material/troubleshoot: Root causes", ":material/table_rows: All tests",
    ":material/search: Failure details", ":material/terminal: Build logs"])

with tab_diff:
    diffs = [r for r in rows if r.category != SAME]
    if diffs:
        show_table(to_frame(diffs))
    else:
        st.success("No differences between the two runs.")

with tab_causes:
    causes = difference_causes(rows)
    if not causes:
        st.success("No output differences to explain.", icon=":material/check_circle:")
    else:
        st.caption("Each row is a word (for pacs.008, a result or rule code) that only one side's output contains, "
                   "with every differing case it explains. A few rows usually explain hundreds of bulk "
                   "differences; a case can appear under more than one row.")
        st.dataframe(pd.DataFrame([{
            "Output word": c.token,
            "Only in": c.side,
            "Cases": len(c.cases),
            "Categories": ", ".join(CATEGORY_LABELS[k] for k in CATEGORY_LABELS
                                    if any(r.category == k for r in c.cases)),
            "Example cases": ", ".join((r.legacy or r.newgen).case_id or r.display_name for r in c.cases[:5]),
        } for c in causes]), hide_index=True, width="stretch", alt="Root causes of the output differences",
            column_config={"Cases": st.column_config.ProgressColumn(
                format="%d", min_value=0, max_value=max(len(c.cases) for c in causes))})

with tab_all:
    f1, f2 = st.columns([2, 3])
    chosen = f1.multiselect("Category", list(CATEGORY_LABELS.values()), default=list(CATEGORY_LABELS.values()))
    query = f2.text_input("Search test name or class", "")
    df_all = to_frame(rows)
    if not df_all.empty:
        mask = df_all["Category"].isin(chosen)
        if query:
            q = query.lower()
            mask &= df_all["Test"].str.lower().str.contains(q, regex=False) | \
                    df_all["Test id"].str.lower().str.contains(q, regex=False)
        show_table(df_all[mask])
        st.download_button("Download CSV", df_all.to_csv(index=False).encode("utf-8"),
                           "test-comparison.csv", "text/csv", icon=":material/download:")

with tab_detail:
    interesting = [r for r in rows if r.category != SAME or r.legacy_status in ("failed", "error")]
    if not interesting:
        st.success("Nothing failed and nothing differs.")
    else:
        idx = st.selectbox(
            "Test", range(len(interesting)),
            format_func=lambda i: f"{CATEGORY_LABELS[interesting[i].category]} — {interesting[i].display_name}")
        pick = interesting[idx]
        st.caption(f"`{pick.test_id}`")
        dl, dn = st.columns(2)
        for col, title, tc in ((dl, ":material/history: Legacy", pick.legacy),
                               (dn, ":material/rocket_launch: New gen", pick.newgen)):
            with col:
                st.markdown(f"**{title}**")
                if tc is None:
                    st.info("Test not present in this run.")
                    continue
                st.markdown(f"**Test:** `{tc.suite.rsplit('.', 1)[-1]}.{tc.name}`")
                st.markdown(f"**Status:** {STATUS_ICONS[tc.status]} · **Time:** {tc.time:.3f}s")
                if tc.output is not None:
                    st.markdown("**Actual output**")
                    st.code(tc.output, language=None)
                if tc.message:
                    st.markdown("**Message**")
                    st.code(tc.message, language=None)
                if tc.details:
                    with st.expander("Stack trace", expanded=tc.status in ("failed", "error")):
                        st.code(tc.details, language="java")

with tab_logs:
    for res in (legacy, newgen):
        with st.expander(f"{res.label} — stage `{res.stage}`", expanded=not res.ok):
            st.code(res.log or "(no output)", language=None)

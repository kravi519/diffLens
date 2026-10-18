"""Comparison page: run each code base's tests on the shared input cases and compare the results."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from comparator.compare import (
    CATEGORY_LABELS, CHANGED, FIXED, ONLY_LEGACY, ONLY_NEWGEN, OUTPUT_DIFF, REGRESSION, SAME, Comparison,
    category_counts, compare,
)
from comparator.java_runner import BUILD_TOOLS, ProjectConfig, RunResult, run_suite
from comparator.source import CACHED, FALLBACK, GITHUB, SourceResult, resolve_source

HERE = Path(__file__).resolve().parent.parent  # project root (this page lives in app_pages/)
SAMPLE = HERE / "sample"
SIDE_NAMES = {"legacy": "Legacy", "newgen": "New gen"}
# Default GitHub sources: (repository URL, branch, project folder in the repo). Changeable in the sidebar.
LEGACY_REPO = ("https://github.com/kravi519/LegacyCode", "main", "legacy")
NEWGEN_REPO = ("https://github.com/kravi519/NewGenCode", "main", "newgen")
# Bundled copies: used when no GitHub URL is given or GitHub cannot be reached. Changeable in the sidebar.
LEGACY_ROOT = SAMPLE / "legacy"
NEWGEN_ROOT = SAMPLE / "newgen"

STATUS_ICONS = {
    "passed": "✅ passed",
    "failed": "❌ failed",
    "error": "💥 error",
    "skipped": "⏭️ skipped",
    "missing": "— missing",
}

# Donut slices carry meaning (good / bad), so they use the theme's semantic colors. Keys are in
# display order, and a key keeps its color whichever slices are present. The color names match
# Markdown color directives, so the legend dots under each donut are exactly the slice colors.
STATUS_SLICES = {
    "passed": ("Passed", "green"),
    "failed": ("Failed", "red"),
    "error": ("Error", "orange"),
    "skipped": ("Skipped", "gray"),
}
CATEGORY_SLICES = {
    REGRESSION: ("Regression", "red"),
    FIXED: ("Fixed", "green"),
    CHANGED: ("Changed", "yellow"),
    OUTPUT_DIFF: ("Output differs", "orange"),
    ONLY_LEGACY: ("Only in legacy", "blue"),
    ONLY_NEWGEN: ("Only in new gen", "violet"),
    SAME: ("Same", "gray"),
}
# Same values as greenColor, redColor, ... in .streamlit/config.toml.
THEME_COLORS = {
    "light": {"green": "#059669", "red": "#DC2626", "orange": "#EA580C", "yellow": "#D97706",
              "blue": "#1D4ED8", "violet": "#7C3AED", "gray": "#64748B"},
    "dark": {"green": "#34D399", "red": "#F87171", "orange": "#FB923C", "yellow": "#FBBF24",
             "blue": "#60A5FA", "violet": "#A78BFA", "gray": "#94A3B8"},
}
DONUT_SIZE = 140



def donut(counts: dict[str, int], slices: dict[str, tuple[str, str]], center: str, center_label: str):
    """Ring of the non-zero counts with the headline in the hole. Returns (chart, legend markdown) or None."""
    present = [(i, key, name, color) for i, (key, (name, color)) in enumerate(slices.items()) if counts.get(key, 0)]
    if not present:
        return None
    total = sum(counts[key] for _, key, _, _ in present)
    mode = "dark" if st.context.theme.type == "dark" else "light"
    palette = THEME_COLORS[mode]
    ink = "#F1F5F9" if mode == "dark" else "#0F172A"  # textColor from .streamlit/config.toml
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
                                        range=[palette[c] for _, _, _, c in present])),
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
    ).configure_view(stroke=None)
    legend = [f":small[:{color}[●] {name} **{counts[key]}**]" for _, key, name, color in present]
    return chart, legend


def donut_card(title: str, icon: str, donut_parts, alt_text: str, footnote: str) -> None:
    """Bordered card: heading, ring with a vertical legend beside it, one-line footnote.

    The legend is a column next to the ring rather than a row under it, so the card height does not
    depend on the number of slices and the footnotes line up across cards.
    """
    with st.container(border=True, height="stretch", gap="small"):
        st.markdown(f"{icon} **{title}**")
        # Legend sits beside the ring; on narrow cards it wraps below instead of clipping.
        with st.container(horizontal=True, horizontal_alignment="center", vertical_alignment="center",
                          gap="medium"):
            if donut_parts is None:
                st.caption("No results to chart.")
            else:
                chart, legend = donut_parts
                st.altair_chart(chart, theme="streamlit", width="content", alt=alt_text)
                with st.container(width="content", gap=None):
                    for item in legend:
                        st.markdown(item, width="content")
        st.caption(footnote)


# ---------------------------------------------------------------- sidebar configuration

def _paths(root: Path, text: str) -> list[Path]:
    out = []
    for line in text.replace(",", "\n").splitlines():
        if line.strip():
            p = Path(line.strip())
            out.append(p if p.is_absolute() else root / p)
    return out


def project_form(label: str, title: str, default_repo: tuple[str, str, str], default_root: Path,
                 default_release: str) -> dict:
    st.sidebar.subheader(title)
    default_url, default_ref, default_dir = default_repo
    with st.sidebar.expander(":material/cloud_download: GitHub source", expanded=True):
        url = st.text_input("Repository URL", default_url, key=f"{label}_gh_url",
                            placeholder="https://github.com/org/repo",
                            help="Leave blank to use the local folder. A /tree/<branch>/<path> URL also works.")
        ref = st.text_input("Branch, tag or commit", default_ref, key=f"{label}_gh_ref", placeholder="default branch")
        subdir = st.text_input("Project folder in the repo", default_dir, key=f"{label}_gh_dir",
                               placeholder="repository root")
    root = st.sidebar.text_input(
        "Local folder (prebuilt fallback)", str(default_root), key=f"{label}_root",
        help="Used when no GitHub URL is given, or when GitHub cannot be reached.")
    build_tool = st.sidebar.selectbox("Build tool", BUILD_TOOLS, key=f"{label}_build")
    cfg = {"root": root, "build_tool": build_tool, "gh_url": url, "gh_ref": ref, "gh_dir": subdir}
    if build_tool == "javac":
        cfg["sources"] = st.sidebar.text_input("Source dirs (relative to root)", "src/main/java", key=f"{label}_src")
        cfg["tests"] = st.sidebar.text_input("Test dirs (relative to root)", "src/test/java", key=f"{label}_tests")
        cfg["release"] = st.sidebar.text_input("javac --release", default_release, key=f"{label}_release")
    cfg["java_home"] = st.sidebar.text_input("JDK home (blank = PATH)", "", key=f"{label}_jdk")
    return cfg


st.sidebar.header(":material/settings: Configuration")
legacy_form = project_form("legacy", "Legacy code base", LEGACY_REPO, LEGACY_ROOT, "8")
newgen_form = project_form("newgen", "New-gen code base", NEWGEN_REPO, NEWGEN_ROOT, "")
st.sidebar.subheader("Shared")
shared_inputs = st.sidebar.text_input(
    "Shared input data dir", st.session_state.get("inputs_dir", str(SAMPLE / "inputs")),
    help="Both test suites read their input cases from here (added to the test classpath in javac mode).")
st.session_state.inputs_dir = shared_inputs  # read by the Input cases page
extra_cp = st.sidebar.text_area("Extra classpath jars/dirs (one per line)", "")
timeout = st.sidebar.number_input("Timeout per suite (s)", 60, 7200, 900, step=60)
github_token = st.sidebar.text_input(
    "GitHub access token", type="password",
    help="Only needed for private repositories. Falls back to the GITHUB_TOKEN environment variable.")
refresh_repos = st.sidebar.checkbox(
    "Download the latest code on every run", value=True,
    help="Off: reuse the last downloaded copy of each repository.")


def fetch_source(label: str, form: dict) -> SourceResult:
    return resolve_source(label, form["gh_url"], form["gh_ref"], form["gh_dir"],
                          github_token.strip() or os.environ.get("GITHUB_TOKEN", ""), refresh_repos,
                          Path(form["root"]).expanduser())


def build_config(label: str, form: dict, root: Path) -> ProjectConfig:
    cfg = ProjectConfig(label=label, root=root, build_tool=form["build_tool"],
                        java_home=form["java_home"].strip(), timeout=int(timeout))
    if cfg.build_tool == "javac":
        cfg.source_dirs = _paths(root, form["sources"])
        cfg.test_dirs = _paths(root, form["tests"])
        cfg.input_dirs = _paths(HERE, shared_inputs)
        cfg.release = form["release"].strip()
        cfg.classpath = _paths(HERE, extra_cp)
    return cfg


# ---------------------------------------------------------------- actions

st.title(":material/search_insights: DiffLens")
st.caption("Legacy vs new-gen behaviour, input by input: runs each code base's own tests on the same input "
           "cases and shows exactly where the results differ.")

run_clicked = st.button("Run tests", icon=":material/play_arrow:", type="primary")

if run_clicked:
    forms = {"legacy": legacy_form, "newgen": newgen_form}
    with ThreadPoolExecutor(max_workers=2) as pool:
        if any(f["gh_url"].strip() for f in forms.values()):
            with st.spinner("Getting the code from GitHub…"):
                sources = dict(zip(forms, pool.map(fetch_source, forms, forms.values())))
        else:
            sources = {label: fetch_source(label, form) for label, form in forms.items()}
        configs = [build_config(label, forms[label], sources[label].root) for label in forms]
        with st.spinner("Building and testing both code bases in parallel…"):
            legacy_result, newgen_result = pool.map(run_suite, configs)
    st.session_state.sources = sources
    st.session_state.results = {"legacy": legacy_result, "newgen": newgen_result}


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

    st.info("The sample is pre-filled in the sidebar: downloaded from GitHub, or taken from `sample/legacy` and "
            "`sample/newgen` when GitHub cannot be reached. Click **Run tests** above to compare, "
            "or point the sidebar at your own legacy and new-gen projects (javac, Maven or Gradle).",
            icon=":material/lightbulb:")
    st.page_link("app_pages/input_cases.py", label="Browse all input cases fed to both sides",
                 icon=":material/dataset:")


if not results or len(results) < 2:
    landing_page()
    st.stop()

legacy, newgen = results["legacy"], results["newgen"]

# Where each side's code came from: GitHub, a cached download, a local folder, or the fallback.
SOURCE_BADGES = {
    GITHUB: ("GitHub", ":material/cloud_done:", "green"),
    CACHED: ("GitHub (cached)", ":material/cloud_sync:", "blue"),
    FALLBACK: ("Prebuilt fallback", ":material/cloud_off:", "orange"),
}
for source in st.session_state.get("sources", {}).values():
    if source.origin == FALLBACK:
        st.warning(source.detail, title=f"{SIDE_NAMES[source.label]}: GitHub could not be used",
                   icon=":material/cloud_off:")
    elif source.origin == CACHED and "download failed" in source.detail:
        st.warning(source.detail, title=f"{SIDE_NAMES[source.label]}: using the last downloaded copy",
                   icon=":material/cloud_sync:")
with st.container(horizontal=True, gap="medium", vertical_alignment="center"):
    for source in st.session_state.get("sources", {}).values():
        text, icon, color = SOURCE_BADGES.get(source.origin, ("Local folder", ":material/folder:", "gray"))
        st.badge(f"{SIDE_NAMES[source.label]}: {text}", icon=icon, color=color)
        where = source.detail if source.origin in (GITHUB, CACHED) else str(source.root)
        st.caption(where.split(" (")[0] if source.origin == CACHED else where, width="content")

for r in (legacy, newgen):
    if not r.ok:
        st.error(f"Stopped at stage `{r.stage}`: {r.error}", title=f"{r.label} did not run",
                 icon=":material/error:")

rows = compare(legacy, newgen)
counts = category_counts(rows)
lc, nc = legacy.counts(), newgen.counts()
diff_total = len(rows) - counts[SAME]


def pass_rate(c: dict[str, int]) -> float:
    return c["passed"] / c["total"] * 100 if c["total"] else 0.0


# Verdict
if counts[REGRESSION]:
    st.error("Tests that pass on legacy fail on new gen. Review them in the differences table below.",
             title=f"{counts[REGRESSION]} regression{'s' if counts[REGRESSION] != 1 else ''} found",
             icon=":material/report:")
elif diff_total:
    st.warning("No regressions, but some results differ. Review them below.",
               title=f"{diff_total} input case{'s' if diff_total != 1 else ''} differ",
               icon=":material/warning:")
elif legacy.ok and newgen.ok:
    st.success("Both code bases return the same result for every input case.",
               title="No differences", icon=":material/check_circle:")

# KPI row: every tile has the same parts (label, value, one pill) so the row lines up. Context pills
# are gray with no arrow; only the new-gen pass rate carries a real up/down change.
k1, k2, k3, k4, k5 = st.columns(5)
context = {"border": True, "height": "stretch", "delta_color": "off", "delta_arrow": "off"}
k1.metric("Input cases", len(rows), f"{diff_total} differ", **context)
k2.metric("Regressions", counts[REGRESSION], "pass → fail", **context)
k3.metric("Fixed", counts[FIXED], "fail → pass", **context)
k4.metric("Legacy pass rate", f"{pass_rate(lc):.1f}%", f"{lc['passed']} of {lc['total']}", **context)
k5.metric("New gen pass rate", f"{pass_rate(nc):.1f}%", f"{pass_rate(nc) - pass_rate(lc):+.1f} pts",
          border=True, height="stretch", help="Change in percentage points vs legacy")

# Donut cards
c1, c2, c3 = st.columns(3)
with c1:
    donut_card("Legacy", ":material/history:", donut(lc, STATUS_SLICES, f"{pass_rate(lc):.0f}%", "pass rate"),
               "Legacy test outcomes",
               f"{lc['passed']} of {lc['total']} passed · run time {legacy.duration:.1f}s")
with c2:
    donut_card("New gen", ":material/rocket_launch:",
               donut(nc, STATUS_SLICES, f"{pass_rate(nc):.0f}%", "pass rate"), "New-gen test outcomes",
               f"{nc['passed']} of {nc['total']} passed · run time {newgen.duration:.1f}s")
with c3:
    donut_card("Comparison", ":material/compare_arrows:",
               donut(counts, CATEGORY_SLICES, str(diff_total), "differ" if diff_total != 1 else "differs"),
               "Comparison of results by input case", f"{diff_total} of {len(rows)} input cases differ")


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


tab_diff, tab_all, tab_detail, tab_logs = st.tabs([
    ":material/difference: Differences", ":material/table_rows: All tests",
    ":material/search: Failure details", ":material/terminal: Build logs"])

with tab_diff:
    diffs = [r for r in rows if r.category != SAME]
    if diffs:
        show_table(to_frame(diffs))
    else:
        st.success("No differences between the two runs.")

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

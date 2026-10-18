"""DiffLens: run each code base's own tests on the same input cases and compare the results.

Start with:  streamlit run app.py
"""

import importlib
import sys
from pathlib import Path

import streamlit as st

# Streamlit reruns the page scripts after a deploy but can keep the old comparator modules in memory, so
# a page importing a new name fails with ImportError until the app is rebooted. Reload every comparator
# module whose file changed since it was loaded (in dependency order) before the page imports it.
COMPARATOR_MODULES = ["comparator.java_runner", "comparator.source", "comparator.compare", "comparator.input_files",
                      "comparator.history", "comparator.report"]
for name in COMPARATOR_MODULES:
    module = sys.modules.get(name)
    if module is None:
        module = importlib.import_module(name)
    elif Path(module.__file__).stat().st_mtime != getattr(module, "__difflens_mtime__", None):
        module = importlib.reload(module)
    module.__difflens_mtime__ = Path(module.__file__).stat().st_mtime

st.set_page_config(page_title="DiffLens", page_icon=":material/search_insights:", layout="wide")

page = st.navigation([
    st.Page("app_pages/comparison.py", title="Comparison", icon=":material/compare_arrows:", default=True),
    st.Page("app_pages/input_files.py", title="Input files", icon=":material/folder_open:"),
    st.Page("app_pages/run_history.py", title="Run history", icon=":material/history:"),
])
page.run()

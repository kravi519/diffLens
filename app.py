"""DiffLens: run each code base's own tests on the same input cases and compare the results.

Start with:  streamlit run app.py
"""

import streamlit as st

st.set_page_config(page_title="DiffLens", page_icon=":material/search_insights:", layout="wide")

page = st.navigation([
    st.Page("app_pages/comparison.py", title="Comparison", icon=":material/compare_arrows:", default=True),
    st.Page("app_pages/input_files.py", title="Input files", icon=":material/folder_open:"),
])
page.run()

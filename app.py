"""BEACON — Behavioral Explainable AI for Cyber Operations Network.

Entry point. Owns the one-time st.set_page_config() call and the sidebar
navigation via st.navigation()/st.Page() -- every page's title and icon
are declared here, not via their own st.set_page_config, so Streamlit
doesn't raise on a second call.

The brand block is a full-width bar in the MAIN content area, not the
sidebar: st.navigation()'s menu renders at a fixed position -- the very
top of the sidebar -- no matter where in the script st.navigation() or a
surrounding `with st.sidebar:` block is called, so anything placed in the
sidebar to sit "above" the nav actually renders below it instead. This
sidesteps that constraint. Each page's own status footer (written via
pipeline.ui.sidebar_footer, inside that page's script) still lands below
the nav, since it runs as part of pg.run().

Run with: streamlit run app.py
"""
import streamlit as st

from pipeline.ui import inject_theme, render, top_bar

st.set_page_config(page_title="BEACON", page_icon="🏮", layout="wide")
render(inject_theme())
render(top_bar())

pages = [
    st.Page("pages/0_Dashboard.py", title="Dashboard", icon="🏠", default=True),
    st.Page("pages/1_Network_Detection.py", title="Network Detection", icon="🌐"),
    st.Page("pages/2_Memory_Detection.py", title="Memory Detection", icon="🧠"),
    st.Page("pages/3_Explainability.py", title="Explainability", icon="💡"),
    st.Page("pages/4_Methodology.py", title="Methodology", icon="📖"),
]
pg = st.navigation(pages, position="sidebar")
pg.run()

"""BEACON — Behavioral Explainable AI for Cyber Operations Network.

Entry point. Owns the one-time st.set_page_config() call, the sidebar
navigation via st.navigation()/st.Page(), and the dark/light theme toggle
-- every page's title and icon are declared here, not via their own
st.set_page_config, so Streamlit doesn't raise on a second call.

The sidebar brand bar and the hero banner are both called here (not once
per page) so they exist in exactly one place -- app.py runs on every
navigation, not just the first load. st.navigation()'s menu renders at a
fixed position at the very top of the sidebar no matter where in the
script st.navigation() or a surrounding `with st.sidebar:` block is
called, so sidebar_brand_bar() uses position:fixed CSS to sit above it
rather than relying on document order, which can't win that fight.

Run with: streamlit run app.py
"""
import os

import streamlit as st

from pipeline.ui import header_band, inject_theme, render, sidebar_brand_bar, theme_toggle

st.set_page_config(
    page_title="BEACON",
    page_icon=os.path.join("assets", "logo-mark.png"),
    layout="wide",
)
render(inject_theme())
render(header_band("Classifies malware from network and memory telemetry — and shows exactly why."))

with st.sidebar:
    render(sidebar_brand_bar())
    theme_toggle()

pages = [
    st.Page("pages/0_Dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
    st.Page("pages/1_Network_Detection.py", title="Network Detection", icon=":material/hub:"),
    st.Page("pages/2_Memory_Detection.py", title="Memory Detection", icon=":material/psychology:"),
    st.Page("pages/3_Explainability.py", title="Explainability", icon=":material/insights:"),
    st.Page("pages/4_Methodology.py", title="Methodology", icon=":material/menu_book:"),
]
pg = st.navigation(pages, position="sidebar")
pg.run()

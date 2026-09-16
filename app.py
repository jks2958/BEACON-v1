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

from pipeline.app_state import ANALYST_MODE, GENERAL_MODE, current_mode
from pipeline.ui import (header_band, inject_theme, mode_badge, render,
                         sidebar_brand_bar, theme_toggle)

st.set_page_config(
    page_title="BEACON",
    page_icon=os.path.join("assets", "logo-mark.png"),
    layout="wide",
)
render(inject_theme())

with st.sidebar:
    render(sidebar_brand_bar())
    st.session_state.setdefault("beacon_mode", GENERAL_MODE)
    st.segmented_control(
        "Choose experience", [GENERAL_MODE, ANALYST_MODE], key="beacon_mode",
        help="Switch presentation without rerunning or changing an analysis.",
    )
    render(mode_badge(current_mode(st.session_state)))
    theme_toggle()

mode = current_mode(st.session_state)
if mode == GENERAL_MODE:
    render(header_band("Analyze suspicious activity using explainable AI.", eyebrow="CYBER THREAT ANALYSIS"))
    pages = [
        st.Page("pages/general_home.py", title="Home", icon=":material/home:", default=True),
        st.Page("pages/general_analyze.py", title="Analyze", icon=":material/upload_file:"),
        st.Page("pages/general_results.py", title="Results", icon=":material/fact_check:"),
        st.Page("pages/about_beacon.py", title="About BEACON", icon=":material/info:"),
    ]
else:
    render(header_band("Classifies malware from network and memory telemetry — and shows exactly why."))
    pages = [
        st.Page("pages/0_Dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
        st.Page("pages/1_Network_Detection.py", title="Network Detection", icon=":material/hub:"),
        st.Page("pages/2_Memory_Detection.py", title="Memory Detection", icon=":material/psychology:"),
        st.Page("pages/3_Explainability.py", title="Explainability", icon=":material/insights:"),
        st.Page("pages/4_Methodology.py", title="Methodology", icon=":material/menu_book:"),
        st.Page("pages/about_beacon.py", title="About BEACON", icon=":material/info:"),
    ]
pg = st.navigation(pages, position="sidebar")
pg.run()

"""BEACON — Behavioral Explainable AI for Cyber Operations Network.

Console landing page. Run with: streamlit run app.py
"""
import streamlit as st

from pipeline.ui import engine_status, inject_theme, kpi_strip, render
from pipeline.viz import headline, load_metrics

st.set_page_config(page_title="BEACON Triage Console", page_icon="🛰️", layout="wide")
render(inject_theme())

net, mem = load_metrics("network"), load_metrics("memory")


def net_block(unit: str) -> dict | None:
    """headline() falls back to whatever block a metrics file has, which
    would label a flow-level figure as 'per capture' on a file written
    before sample-level scoring existed. Only report a unit the file has;
    a file with neither block predates that split and measured flow level."""
    if not net:
        return None
    if "sample_level" not in net and "flow_level" not in net:
        return headline(net) if unit == "flow" else None
    if f"{unit}_level" not in net:
        return None
    return headline(net, unit)


net_sample, net_flow, mem_head = net_block("sample"), net_block("flow"), headline(mem)

with st.sidebar:
    render('<div class="bx-label">Engine status</div>')
    render(engine_status("Network model", "loaded" if net else "not trained",
                              ok=bool(net)))
    render(engine_status("Memory model", "loaded" if mem else "not trained",
                              ok=bool(mem)))
    render('<div class="bx-label" style="margin-top:14px">Dataset</div>')
    render('<div class="bx-status"><div><div class="mt">BCCC-Mal-NetMem-2025<br>'
                '9 categories · 2 streams<br>local inference only</div></div></div>')

st.markdown("# BEACON Triage Console")
st.caption("Behavioral Explainable AI for Cyber Operations Network — classifies "
           "network-flow and memory-forensic telemetry into one of nine malware "
           "categories or benign, with a SHAP explanation behind every verdict.")

tiles = [{"label": "Categories", "value": "9", "sub": "8 malware + benign"},
         {"label": "Streams", "value": "2", "sub": "network + memory"}]
if net_sample:
    tiles.append({"label": "Network accuracy", "value": f"{net_sample['accuracy']:.1%}",
                  "sub": f"per capture · n={net_sample['n']:,}"})
if net_flow:
    tiles.append({"label": "Network, per flow", "value": f"{net_flow['accuracy']:.1%}",
                  "sub": f"n={net_flow['n']:,} flows"})
if not net:
    tiles.append({"label": "Network model", "value": "—", "sub": "not trained"})
if mem_head:
    tiles.append({"label": "Memory accuracy", "value": f"{mem_head['accuracy']:.1%}",
                  "sub": f"per sample · n={mem_head['n']:,}"})
else:
    tiles.append({"label": "Memory model", "value": "—", "sub": "not trained"})

render(kpi_strip(tiles))

if net_sample and net_flow:
    render('<div class="bx-note" style="margin-top:14px"><strong>Two units, two '
        "questions.</strong> Per capture is how the system is used — a capture's "
        "flows are combined into one verdict, so individual flow errors cancel out. "
        "Per flow is the harder underlying task. Neither is the 'real' number alone."
        "</div>")

render("<hr>")

c1, c2, c3, c4 = st.columns(4, gap="medium")
for col, (title, body) in zip((c1, c2, c3, c4), [
    ("Multiclass verdicts", "Nine malware families or benign — not a binary "
                            "malicious/not call."),
    ("Dual-source evidence", "Independent classifiers over network-flow and "
                             "memory-forensic behaviour."),
    ("Explained decisions", "Every verdict ships with the SHAP-ranked features "
                            "that produced it."),
    ("Analyst triage", "Severity, confidence against an action threshold, and a "
                       "session detections log."),
]):
    with col:
        st.markdown(f"##### {title}")
        st.caption(body)

render("<hr>")
st.page_link("pages/1_Network_Detection.py", label="Analyse network capture", icon="🌐")
st.page_link("pages/2_Memory_Detection.py", label="Analyse memory capture", icon="🧠")
st.page_link("pages/3_About_Methodology.py", label="Model card & methodology", icon="◈")

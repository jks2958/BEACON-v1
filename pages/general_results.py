"""Plain, evidence-grounded result view for General Mode."""
import pandas as pd
import streamlit as st

from pipeline.app_state import ANALYST_MODE, latest_analysis, set_mode
from pipeline.interpretation import interpret_analysis
from pipeline.ui import empty_state, page_header, render, section_header


render(page_header("Analysis result", "A clear summary of what the model found and why.",
                   eyebrow="GENERAL MODE"))
output = latest_analysis(st.session_state)
if output is None:
    render(empty_state("No analysis yet", "Upload evidence to generate an explainable result.",
                       "manage_search"))
    st.info("No analysis yet. Upload evidence to generate a result.")
    if st.button("Analyze Evidence", type="primary"):
        st.switch_page("pages/general_analyze.py")
    st.stop()

result = output.result
verdict, confidence = result["verdict"], result["confidence"]
interpretation = interpret_analysis(result, output.stream)

render(section_header("Result overview"))
if verdict == "Benign":
    st.success(interpretation.short_summary)
else:
    st.warning(interpretation.short_summary)

c1, c2, c3 = st.columns(3)
c1.metric("Potential malware family", verdict)
c2.metric("Model confidence", f"{confidence:.1%}")
c3.metric("Result status", "Result available")
st.caption("Model confidence is the model's highest class probability, not a guarantee of correctness.")
st.caption("Needs Review automation is pending validation; no arbitrary confidence cutoff is applied.")

render(section_header("What does this mean?"))
st.write(f"**{interpretation.category_display_name}.** {interpretation.malware_description}")
st.write(interpretation.risk_explanation)

render(section_header("Why was this flagged?", "Strongest evidence from the existing SHAP explanation"))
for item in interpretation.evidence_items:
    direction = ("Supported the result" if item.direction == "toward" else
                 "Reduced support" if item.direction == "away" else "Neutral")
    st.markdown(f"- **{item.display_name}** — {item.human_explanation} *{direction}.*")

render(section_header("What should I do?", "Precautionary guidance — no automated action is taken"))
for action in interpretation.recommended_actions:
    st.markdown(f"- {action}")

render(section_header("Limitations"))
for limitation in interpretation.limitations:
    st.caption(f"• {limitation}")
st.caption(interpretation.technical_disclaimer)

with st.expander("View technical details"):
    st.write(f"Evidence stream: **{output.stream.title()}**")
    st.write(f"Rows analyzed: **{result['n_rows']:,}**")
    st.write(f"Exact model class: **{interpretation.predicted_category}**")
    st.write(f"Exact model confidence: **{interpretation.confidence_value:.6f}**")
    probabilities = result["aggregate_probabilities"].sort_values(ascending=False)
    st.dataframe(
        pd.DataFrame({"Category": probabilities.index, "Probability": probabilities.values}),
        hide_index=True, use_container_width=True,
    )
    st.markdown("**Top SHAP feature evidence**")
    st.dataframe(result["top_features"], hide_index=True, use_container_width=True)
    if output.evidence is not None:
        metadata = {key: value for key, value in output.evidence.metadata.items()
                    if isinstance(value, (str, int, float, bool)) or value is None}
        if metadata:
            st.markdown("**Evidence metadata**")
            st.json(metadata)

if st.button("Open Analyst Mode"):
    set_mode(st.session_state, ANALYST_MODE)
    st.rerun()

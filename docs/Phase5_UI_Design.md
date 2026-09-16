# Phase 5 dual-mode interface

Phase 5 redesigns presentation only. General and Analyst Mode continue to read
the same stored `AnalysisOutput`; switching modes neither reruns inference nor
changes probabilities, confidence, SHAP, or session-state semantics.

## General Mode

Navigation is **Home → Analyze → Results → About**. Home presents supported
prepared Network and Memory CSV inputs separately from future work. Analyze is
a three-step, plain-language workflow. Results prioritize interpretation,
evidence-grounded reasons, precautionary actions, and limitations; exact
probabilities and SHAP values remain available in a collapsed technical view.

## Analyst Mode

Navigation is **Dashboard → Network Detection → Memory Detection →
Explainability → Methodology → About**. The dashboard summarizes only activity
recorded in the current session. Detection pages use a shared result hierarchy,
while Explainability separates current features pushing toward and away from a
prediction. Methodology retains the measured scientific claims and explicitly
states the PCAP compatibility gate.

## Design and validation

The shared Streamlit design system provides page and section headings, mode
badges, empty states, restrained dark/light tokens, responsive column wrapping,
and non-colour status labels. Upload errors retain their original details in an
expander in General Mode; Analyst Mode keeps direct technical errors.

Browser screenshot tooling was not available in the implementation environment.
The interface was validated with Streamlit AppTest page checks and a live
Streamlit health smoke test instead.

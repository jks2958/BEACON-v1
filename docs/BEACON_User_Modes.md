# BEACON User Modes

BEACON serves two audiences over one shared analysis core. Changing modes
changes presentation and navigation only; it does not select a different model
or alter preprocessing, prediction, probability aggregation, or SHAP.

## General Mode

General Mode is for non-technical users who need a short, approachable threat-
analysis workflow. It provides a simple upload screen and a result structure
covering the detected category, existing numeric model confidence, deterministic
plain-language interpretation, evidence translated from actual SHAP output,
limitations, and precautionary response guidance.

No external generative AI is used. Unknown technical features receive a generic
behavioral explanation rather than an invented claim. Users can expand
technical details or move to Analyst Mode to inspect the exact probabilities,
feature values, and SHAP evidence.

## Analyst Mode

Analyst Mode preserves BEACON's existing technical workflow: separate Network
and Memory analysis, nine-category output, model probabilities, SHAP feature
contributions, model metrics, methodology, and CSV verdict export. A compact
interpretation summary is additive and does not replace technical evidence.

## Shared core

Both modes send uploads through the framework-independent evidence-ingestion
layer. It captures immutable bytes, checks the currently supported format,
selects the explicit Network or Memory CSV parser, and returns `ParsedEvidence`.
`pipeline/application.py` then delegates to the same cached
`DashboardController` instances and their existing upload validation and
inference methods; no model, feature order, preprocessing rule, aggregation
rule, or SHAP calculation is duplicated in the UI.

```text
Upload → Ingestion → ParsedEvidence → Application Service
       → DashboardController → Model → SHAP → Result
```

Completed result data can be retained across a mode switch. Controllers and
model objects remain in Streamlit's resource cache and are never stored in
session state.

## Input support in Phase 2

The current application accepts **prepared CSV telemetry only**:

- Network feature CSVs
- Memory feature CSVs

It does not currently parse packet captures or raw memory images.

## Future roadmap — not implemented

Planned future evidence sources include:

- PCAP / PCAPNG
- Raw memory telemetry

These are roadmap items, not current application capabilities.

Phase 3 can parse PCAP and PCAPNG into diagnostic flows, but production upload
and inference remain disabled because the original 342-feature extraction
semantics cannot be empirically reproduced from the available repository. A
future raw-memory extractor is likewise not implemented.

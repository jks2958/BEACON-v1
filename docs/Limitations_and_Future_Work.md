# Limitations and future work

## Network

The Network model is validated on the prepared 342-feature CSV representation.
PCAP and PCAPNG parsing exists, but the original flow extractor and paired
capture/feature references are unavailable; 342-feature equivalence remains
unproven and native captures fail closed before inference.

## Memory

The Memory model is validated on the prepared 94-feature CSV representation.
Structured Volatility JSON can be inspected diagnostically, but the original
aggregation semantics and a paired reference are unavailable. Raw memory is not
processed. Memory family performance is weaker than Network capture-level
performance, particularly among behaviorally overlapping families.

## Evaluation

Reported results come from the existing held-out, sample-grouped evaluation.
The project retains the report's single-fold limitation; it does not invent
confidence intervals or claim broader generalization than the recorded study.
The strongest documented Network result is 99.1% per capture (68.2% per flow).
The Memory result is approximately 59% accuracy with macro F1 approximately
0.56. Units and coverage must accompany reported figures.

## Public interpretation

General Mode translates existing class, confidence, and SHAP evidence. It does
not generate new evidence, confirm infection, or replace professional incident
response. No validated operational abstention cutoff is stored, so an arbitrary
Needs Review threshold is not activated.

## Security assumptions

Uploads are handled as data: none are executed or unpickled. There is no
`archive` extraction, `shell=True`, user-controlled subprocess command, or raw
memory execution. Captures are limited to 100 MiB and 1,000,000 packets;
structured Volatility JSON is limited to 10 MiB. Resource limits reduce but do
not eliminate denial-of-service risk in a single-process Streamlit deployment.
Committed joblib artifacts are trusted project assets and must not be replaced
with untrusted files.

## Future research

Recover the original Network and Memory extractors; obtain paired raw and
prepared evidence; validate across capture/tool versions; use cross-validation;
investigate richer process, DLL, injected-region, string, hash, and Windows
event-log identity features; and retrain only as a separately validated future
research extension.

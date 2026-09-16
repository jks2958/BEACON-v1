# Supervisor demo guide (8–12 minutes)

## Before starting

```bash
python -m streamlit run app.py
```

Use `demo/network_sample.csv` and `demo/memory_sample.csv`. They are synthetic,
schema-valid plumbing fixtures—not malware evidence or benchmark samples.

## Sequence

1. **General Home (30 sec):** distinguish production CSV inputs from diagnostic/future formats.
2. **General Network analysis (90 sec):** choose Network telemetry, upload `demo/network_sample.csv`, and run the real model.
3. **General result (60 sec):** show category, exact model confidence, evidence-grounded “why”, actions, and limitations.
4. **Technical details (30 sec):** expand probabilities and the original SHAP table.
5. **Mode switch (30 sec):** switch to Analyst Mode and emphasize that the same result remains in shared state; no second inference occurs.
6. **Analyst evidence (60 sec):** open Explainability to separate features pushing toward and away from the current result.
7. **Memory analysis (90 sec):** upload `demo/memory_sample.csv` in Memory Detection; show probabilities, SHAP, and the visible reliability caution.
8. **PCAP boundary (45 sec):** explain that parsing and flow diagnostics exist, but the 342-feature gate blocks production inference because equivalence is unproven.
9. **Volatility boundary (45 sec):** open Structured Volatility compatibility diagnostics on Memory Detection; explain the 94-feature fail-closed gate. No raw-memory claim is made.
10. **Methodology (60 sec):** show measured results, units, known limitations, and why Network and Memory remain independent.
11. **Close (30 sec):** summarize the contribution: explainability, two audiences, shared validated core, and evidence compatibility safeguards.

Do not interpret the synthetic fixture's predicted family as a performance result.

# BEACON v1.0.0 release notes

BEACON v1.0.0 is the final FYP submission release.

## Included

- General and Analyst experiences over one shared analysis core
- prepared Network and Memory CSV production classification
- centralized, framework-independent ingestion
- unchanged XGBoost inference and SHAP technical evidence
- deterministic evidence-grounded public interpretation
- PCAP/PCAPNG parsing and Network compatibility diagnostics
- structured Volatility JSON and Memory compatibility diagnostics
- responsive shared design system, state preservation, regression tests, and auditable artifact baselines

## Safety boundaries

PCAP, PCAPNG, and Volatility JSON do not reach production inference because
exact feature equivalence is unproven. Raw memory, executables, archives, and
event logs are not supported. The application reports model evidence, not
certainty of infection.
